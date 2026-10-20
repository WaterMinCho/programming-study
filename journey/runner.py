# -*- coding: utf-8 -*-
"""여정 테스트 실행기. 테스트 하나를 자식 하네스로 돌리고 시간·메모리를 감시하며, 여러 개를 병렬·순차로 돌리고, 생성 입력을 캐시함.

테스트 하나(묶음 포함)마다 자식 프로세스 하나임. 피크 메모리가 프로세스 단위로만 보이고, 전역 상태가 다음 테스트로
새지 않으며, 시간 초과·충돌이 그 테스트만 실패시키기 때문임. 실행·채점 한 번에 임시 폴더 하나를 만들어 학생 코드와
하네스를 그 안에 복사하고, 테스트마다 그 아래 케이스 폴더에서 자식을 띄움. 자식의 명령줄과 작업 폴더에는 저장소
경로가 없음. 시간 제한은 묶음 전체가 아니라 호출 하나마다 적용함.
"""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import study
from journey import node as node_finder
from journey import values

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS_PY = os.path.join(HERE, "harness.py")
HARNESS_JS = os.path.join(HERE, "harness.js")
GENRUN_PY = os.path.join(HERE, "genrun.py")
STACK_MB = 64  # 하네스의 스레드 스택. Windows 는 확정 메모리로 잡혀서 끊는 검사에서 이만큼 뺌
START_LIMIT_S = 10  # 최상위 코드(모듈 실행)에 주는 시간. 묶음에서는 호출마다 새로 셈
RUN_LIMIT_MS = 10000  # [코드 실행]의 호출 하나 제한
RUN_KILL_MS = RUN_LIMIT_MS + 500
GRADE_KILL_RATIO = 1.5  # 채점은 제한 × 1.5 에서 끊음
MB = 1024 * 1024
CACHE_DIR = os.environ.get("STUDY_JOURNEY_CACHE") or os.path.join(os.path.expanduser("~"), ".rokey-study", "journey-cache")
CACHE_LIMIT_MB = 1024
GEN_VERSION = "1"  # 생성기 실행 방식이 바뀌어 캐시를 모두 버려야 할 때 올림
EXT = {"python": ".py", "javascript": ".js"}
START_NOTE = "solution 을 부르기 전에 멈췄습니다. 함수 밖의 코드에 끝나지 않는 반복이 없는지 확인하세요."
CRASH_NOTE = "프로그램이 비정상 종료했습니다(%s)."
HEAP_MARK = "heap out of memory"


class GenError(Exception):
    """입력 생성기가 실패함. 문구는 출제자에게 그대로 보여 줌."""


def workers():
    """정확성 묶음을 동시에 돌릴 수. 환경 변수 STUDY_JOURNEY_WORKERS 로 덮어씀."""
    forced = os.environ.get("STUDY_JOURNEY_WORKERS")
    if forced:
        try:
            return max(1, int(forced))
        except ValueError:
            pass
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def grade_kill_ms(limit_ms):
    return limit_ms * GRADE_KILL_RATIO


def child_memory(pid_path, lang):
    """자식이 지금 쓰는 메모리(바이트). Windows 의 Python 하네스는 64MB 스택이 확정 메모리에 처음부터 들어 있어 그만큼 뺌."""
    used = study.runner_memory(pid_path)
    if used and lang == "python" and sys.platform == "win32":
        used = max(0, used - STACK_MB * MB)
    return used


def empty_result():
    return {"status": "pass", "values": None, "elapsed_ms": None, "calls_ms": None, "peak_mb": None,
            "printed": "", "printed_cut": False, "error": "", "note": "", "fatal": None, "failed_call": None}


def workspace():
    """실행·채점 한 번에 쓰는 임시 폴더. with 로 열고 run_cases(..., workdir=) 에 넘기면 정확성·효율성 그룹이 같은 사본을 씀."""
    return tempfile.TemporaryDirectory(prefix="journey_", **study.TMP_OPTIONS)


def prepare(lang, source_path, workdir):
    """학생 코드와 하네스를 작업 폴더에 복사함. 도는 동안 편집해도 영향이 없고 명령줄에 저장소 경로가 남지 않음."""
    ext = EXT[lang]
    study.write_text(os.path.join(workdir, "solution" + ext), study.read_text(source_path))
    shutil.copyfile(HARNESS_PY if lang == "python" else HARNESS_JS, os.path.join(workdir, "harness" + ext))


def command(lang, workdir, node=None, python=None):
    """자식 명령과 환경 변수. node 는 find() 의 결과나 경로, python 은 --timing 이 판마다 잴 때 주는 실행 파일."""
    if lang == "python":
        return ([python or study.console_python(), "-I", "-S", "-B", "-X", "utf8",
                 os.path.join(workdir, "harness.py"), "job.json"], None)
    if isinstance(node, dict):
        node = node.get("path")
    if not node:
        found = node_finder.find()
        node = found["path"] if found else None
    if not node:
        raise RuntimeError("Node.js 를 찾지 못했습니다.")
    env = {key: value for key, value in os.environ.items() if key not in ("NODE_OPTIONS", "NODE_PATH")}
    return ([node, "--max-old-space-size=%d" % study.MEMORY_LIMIT_MB, os.path.join(workdir, "harness.js"), "job.json"], env)


def _relative(path, folder):
    try:
        return os.path.relpath(path, folder)
    except ValueError:  # Windows 에서 드라이브가 다름
        return os.path.abspath(path)


def _read_small(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def stop(proc, pid_path):
    """자식을 끊음. pid 파일의 pid 가 다르면(가상 환경 실행기, Volta 심) 그것도 끊음."""
    try:
        proc.kill()
    except OSError:
        pass
    pid = None
    text = _read_small(pid_path)
    if text:
        try:
            pid = int(text.strip())
        except ValueError:
            pid = None
    if pid and pid != proc.pid:
        try:
            os.kill(pid, signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL)
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def watch(proc, case_dir, lang, kill_ms, cancel):
    """자식이 끝날 때까지 MEMORY_POLL 마다 봄. (끊은 이유 | None, 끊은 호출 번호 | None)."""
    pid_path = os.path.join(case_dir, "pid")
    calling_path = os.path.join(case_dir, "calling")
    limit = study.MEMORY_LIMIT_MB * MB
    state, since = None, time.monotonic()
    while True:
        try:
            proc.wait(timeout=study.MEMORY_POLL)
            return None, None
        except subprocess.TimeoutExpired:
            pass
        if cancel is not None and cancel.is_set():
            stop(proc, pid_path)
            return "cancelled", None
        if child_memory(pid_path, lang) > limit:
            stop(proc, pid_path)
            return "memory", None
        text = _read_small(calling_path)
        now = time.monotonic()
        if text and text != state:
            state, since = text, now
        if state is None or state.startswith("load"):
            if now - since > START_LIMIT_S:
                stop(proc, pid_path)
                return "start", None
        elif (now - since) * 1000 > kill_ms:
            stop(proc, pid_path)
            try:
                return "timeout", int(state.split()[1])
            except (IndexError, ValueError):
                return "timeout", None


def _describe_exit(code):
    if code is None:
        return "끝나지 않음"
    if code < 0:
        return "신호 %d" % -code
    return "코드 0x%X" % (code & 0xFFFFFFFF)


def _last_line(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def compose(lang, case_dir, case, reason, killed_call, exit_code):
    """자식의 result.json 과 감시 결과로 3.9 의 결과를 만듦. 판정 순서는 cancelled, memory, timeout, crash, fatal, runtime, bad_return, 값 비교."""
    result = empty_result()
    calls = case.get("calls") or 1
    limit_ms = case["limit_ms"]
    child = None
    try:
        child = study.read_json(os.path.join(case_dir, "result.json"))
    except (OSError, ValueError):
        child = None
    stderr_text = ""
    try:
        with open(os.path.join(case_dir, "stderr.txt"), "rb") as f:
            stderr_text = f.read()[-8000:].decode("utf-8", "replace")
    except OSError:
        pass
    if child:
        times = child.get("times_ns") or []
        result["calls_ms"] = [t / 1e6 for t in times]
        result["elapsed_ms"] = max(result["calls_ms"]) if times else None
        result["peak_mb"] = (child.get("peak") or 0) / MB
        result["printed"] = child.get("printed") or ""
        result["printed_cut"] = bool(child.get("printed_cut"))
        result["error"] = child.get("error") or ""
        result["note"] = child.get("note") or ""
        result["fatal"] = child.get("fatal")
        result["failed_call"] = child.get("failed_call")
    child_status = child.get("status") if child else None
    over = [index for index, ms in enumerate(result["calls_ms"] or []) if ms > limit_ms]

    if reason == "cancelled":
        result["status"] = "cancelled"
    elif (reason == "memory" or child_status == "memory" or HEAP_MARK in stderr_text
          or (child and (child.get("peak") or 0) > study.MEMORY_LIMIT_MB * MB)):
        result["status"] = "memory"
    elif reason in ("start", "timeout") or over:
        result["status"] = "timeout"
        result["failed_call"] = killed_call if reason == "timeout" else (over[0] if over else None)
        if reason == "start":
            result["note"] = START_NOTE
    elif child is None or child_status == "crash":
        result["status"] = "runtime"
        result["note"] = CRASH_NOTE % _describe_exit(exit_code)
        if not result["error"]:
            result["error"] = _last_line(stderr_text)
    elif child_status == "fatal":
        result["status"] = "fatal"
    elif child_status == "runtime":
        result["status"] = "runtime"
    elif child_status == "bad_return":
        result["status"] = "bad_return"
    else:
        raw = child.get("values") or []
        if len(raw) != calls:
            result["status"] = "runtime"
            result["note"] = CRASH_NOTE % _describe_exit(exit_code)
        else:
            try:
                normalized = [values.canonical(json.loads(text)) for text in raw]
            except (ValueError, RecursionError, MemoryError):  # 하네스가 64겹 넘는 리스트를 막아서 깨진 result.json 에서만 남
                normalized = None
            if normalized is None:
                result["status"] = "runtime"
                result["note"] = CRASH_NOTE % _describe_exit(exit_code)
            else:
                result["values"] = normalized
                text = values.result_text(normalized, case.get("bundle", calls > 1))
                ok = values.matches(text, case.get("expected"), case.get("expected_sha"))
                result["status"] = "pass" if ok else "wrong"
    return result


def run_case(lang, source_path, case, workdir, cancel=None, node=None, python=None):
    """테스트 하나를 자식 하네스로 돌림.

    case = {"args_path" | "args", "calls", "limit_ms", "kill_ms", "expected" | "expected_sha", "bundle"}.
    args 는 [[인자…], …] 꼴(묶음이 아니면 길이 1), expected 는 정규 JSON 글, bundle 은 결과를 목록으로 비교할지(기본은 calls > 1).
    workdir 에 solution 과 하네스가 아직 없으면 복사함. 결과 모양은 3.9."""
    if cancel is not None and cancel.is_set():
        result = empty_result()
        result["status"] = "cancelled"
        return result
    ext = EXT[lang]
    if not os.path.isfile(os.path.join(workdir, "solution" + ext)):
        prepare(lang, source_path, workdir)
    case_dir = tempfile.mkdtemp(prefix="c", dir=workdir)
    args_path = case.get("args_path")
    if not args_path:
        args_path = os.path.join(case_dir, "args.json")
        study.write_text(args_path, json.dumps(case["args"], ensure_ascii=False, separators=(",", ":")))
    calls = case.get("calls") or 1
    kill_ms = case.get("kill_ms") or grade_kill_ms(case["limit_ms"])
    job = {"source": os.path.join("..", "solution" + ext), "args": _relative(args_path, case_dir), "calls": calls,
           "pid": "pid", "calling": "calling", "result": "result.json"}
    study.write_text(os.path.join(case_dir, "job.json"), json.dumps(job, ensure_ascii=False))
    cmd, env = command(lang, workdir, node, python)
    with open(os.path.join(case_dir, "stderr.txt"), "wb") as stderr:
        proc = subprocess.Popen(cmd, cwd=case_dir, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr,
                                env=env, creationflags=study.NO_WINDOW)
        reason, killed_call = watch(proc, case_dir, lang, kill_ms, cancel)
    return compose(lang, case_dir, case, reason, killed_call, proc.returncode)


def run_cases(lang, source_path, cases, workers=1, on_case=None, cancel=None, node=None, python=None, workdir=None):
    """여러 테스트를 돌려 결과 목록을 돌려줌. 첫 테스트를 혼자 먼저 돌려 fatal 이면 나머지는 돌리지 않고 같은 fatal 로 채움.
    나머지는 workers 개씩 동시에 돌리고, on_case(번호, 결과) 는 번호 순서대로 부름.

    workdir(workspace() 로 연 폴더)을 주면 그 폴더에 처음 복사한 학생 코드를 계속 씀. 채점의 두 그룹에 같은 workdir 을
    넘기면 그 사이에 편집기가 저장해도 같은 코드로 돎. 없으면 이번 호출만의 임시 폴더를 만듦."""
    results = [None] * len(cases)
    if not cases:
        return results
    if workdir is None:
        with workspace() as own:
            prepare(lang, source_path, own)
            return run_cases(lang, source_path, cases, workers, on_case, cancel, node, python, own)

    def deliver(index, result):
        results[index] = result
        if on_case:
            on_case(index, result)

    first = run_case(lang, source_path, cases[0], workdir, cancel, node, python)
    deliver(0, first)
    if first["status"] == "fatal":
        for index in range(1, len(cases)):
            deliver(index, dict(first))
        return results
    rest = list(range(1, len(cases)))
    if workers <= 1 or len(rest) <= 1:
        for index in rest:
            deliver(index, run_case(lang, source_path, cases[index], workdir, cancel, node, python))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_case, lang, source_path, cases[index], workdir, cancel, node, python)
                       for index in rest]
            for index, future in zip(rest, futures):
                deliver(index, future.result())
    return results


# 생성 입력과 캐시

def cache_dir():
    return CACHE_DIR


def cache_key(gen_source, spec):
    """sha256(gen.py 원문 + "\\0" + 명세 JSON + "\\0" + GEN_VERSION). 생성기가 바뀌면 키가 바뀌어 저절로 새로 만듦."""
    normalized = {"gen": spec.get("gen"), "seed": spec.get("seed"), "params": spec.get("params") or {},
                  "count": spec.get("count")}
    raw = gen_source + "\0" + json.dumps(normalized, sort_keys=True, ensure_ascii=False) + "\0" + GEN_VERSION
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def genrun_command(gen_path, spec_path, out_path, validate_path=None):
    """-I 를 쓰지 않음. -I 는 PYTHONHASHSEED 를 무시해서 집합 순서에 기댄 생성기가 프로세스마다 다른 입력을 내기 때문임."""
    cmd = [study.console_python(), "-S", "-B", "-X", "utf8", GENRUN_PY, study.ROOT, gen_path, spec_path, out_path]
    if validate_path:
        cmd += ["--validate", validate_path]
    return cmd


def genrun_env():
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    env["PYTHONHASHSEED"] = "0"
    return env


def generate_to(gen_source, spec, out_path, validate_source=None):
    """생성기를 자식 프로세스로 돌려 out_path 에 [[인자…], …] 를 씀. 돌려주는 값은 {"invalid": None | {"index", "message"}}
    (validate 를 줬을 때만 채워짐). 생성기가 실패하면 GenError."""
    with tempfile.TemporaryDirectory(prefix="journey_gen_", **study.TMP_OPTIONS) as tmp:
        gen_path = os.path.join(tmp, "gen.py")
        spec_path = os.path.join(tmp, "spec.json")
        study.write_text(gen_path, gen_source)
        study.write_text(spec_path, json.dumps(spec, ensure_ascii=False))
        validate_path = None
        if validate_source is not None:
            validate_path = os.path.join(tmp, "validate.py")
            study.write_text(validate_path, validate_source)
        proc = subprocess.run(genrun_command(gen_path, spec_path, out_path, validate_path), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=genrun_env(),
                              creationflags=study.NO_WINDOW)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[-3000:]
        raise GenError("입력 생성기 %s 가 실패했습니다.\n%s" % (spec.get("gen"), detail))
    output = proc.stdout.decode("utf-8", "replace").strip()
    report = {"invalid": None}
    if output:
        try:
            report.update(json.loads(output.splitlines()[-1]))
        except ValueError:
            pass
    return report


def _looks_complete(path):
    try:
        size = os.path.getsize(path)
        if size < 2:
            return False
        with open(path, "rb") as f:
            head = f.read(1)
            f.seek(-1, os.SEEK_END)
            tail = f.read(1)
        return head == b"[" and tail == b"]"
    except OSError:
        return False


def generated_args(gen_source, spec):
    """캐시된 입력 파일의 경로. 없거나 깨졌으면 만들고, 한도를 넘으면 가장 오래 안 쓴 것부터 지움."""
    folder = cache_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, cache_key(gen_source, spec) + ".json")
    if _looks_complete(path):
        try:
            os.utime(path, None)
        except OSError:
            pass
        return path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    generate_to(gen_source, spec, path)
    trim_cache()
    return path


def _cache_files():
    folder = cache_dir()
    entries = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.endswith(".json"):
                info = entry.stat()
                entries.append((entry.path, info.st_size, info.st_mtime))
    except OSError:
        pass
    return entries


def trim_cache():
    """합계가 CACHE_LIMIT_MB 를 넘으면 수정 시각이 오래된 것(가장 오래 안 쓴 것)부터 지움."""
    entries = _cache_files()
    total = sum(size for _, size, _ in entries)
    limit = int(CACHE_LIMIT_MB * MB)
    for path, size, _ in sorted(entries, key=lambda item: item[2]):
        if total <= limit:
            break
        try:
            os.remove(path)
            total -= size
        except OSError:
            pass


def cache_info():
    entries = _cache_files()
    return {"bytes": sum(size for _, size, _ in entries), "files": len(entries)}


def clear_cache():
    for path, _, _ in _cache_files():
        try:
            os.remove(path)
        except OSError:
            pass
    return cache_info()
