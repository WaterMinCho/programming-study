# -*- coding: utf-8 -*-
"""여정 Python 하네스. 실행기가 임시 폴더에 복사해 자식 프로세스로만 띄우고, 저장소의 어떤 모듈도 import 하지 않음.

python -I -S -B -X utf8 harness.py job.json   (작업 폴더는 케이스 폴더)
job.json: {"source", "args", "calls", "pid", "calling", "result"}. 경로는 케이스 폴더 기준이고 args 는 절대 경로일 수 있음.

호출마다 모듈을 새로 실행하고(최상위 코드는 시간에 안 들어감) solution 호출만 잼. 부모는 calling 파일의 글이
"load k" 에서 "call k" 로 바뀐 때부터 그 호출의 시간을 재어 끊음. 결과는 result.json 에 씀.
"""
import builtins
import gc
import json
import os
import re
import sys
import threading
import time

STACK_MB = 64
BASE_LIMIT = 1000
RAISED_LIMIT = 10000
OUTPUT_LIMIT = 1000000
PRINT_KEEP = 20000
CACHE_DECORATOR = re.compile(r"^\s*@\s*(functools\s*\.\s*)?(cache|lru_cache)\b", re.MULTILINE)

# 학생 코드가 모듈 속성을 바꿔도 시간 재기와 결과 쓰기가 흔들리지 않게 함수를 지역 이름으로 잡아 둠
perf = time.perf_counter_ns
dumps = json.dumps
loads = json.loads
replace = os.replace
opener = builtins.open
getrecursionlimit = sys.getrecursionlimit
setrecursionlimit = sys.setrecursionlimit
hard_exit = os._exit
sleep = time.sleep

NONE_NOTE = "None 을 반환했습니다. return 을 빠뜨렸는지 확인하세요."
TUPLE_NOTE = "튜플을 반환했습니다. 리스트로 바꿔 반환하세요."
SET_NOTE = "집합을 반환했습니다. 리스트로 바꿔 반환하세요."
DICT_NOTE = "딕셔너리를 반환했습니다. 리스트로 바꿔 반환하세요."
GENERATOR_NOTE = "제너레이터를 반환했습니다. list(...) 로 감싸 반환하세요."
FLOAT_NOTE = "유한하지 않은 실수(%s)를 반환했습니다."
OTHER_NOTE = "%s 타입은 반환할 수 없습니다. 정수·문자열·불리언이나 그 리스트로 반환하세요."
OUTPUT_NOTE = "출력이 1,000,000자를 넘었습니다."
INPUT_NOTE = "이 문제는 input() 으로 읽지 않고 solution 의 매개변수로 받습니다."
LIMIT_LOW_NOTE = ("sys.setrecursionlimit 으로 한도를 늘리거나 반복문으로 바꾸세요. "
                  "이 채점기는 1,000보다 큰 한도를 모두 10,000으로 맞춥니다.")
LIMIT_HIGH_NOTE = "이 채점기는 1,000보다 큰 한도를 모두 10,000으로 맞추므로 더 깊이 내려가야 하면 반복문과 직접 만든 스택으로 바꾸세요."
CACHE_NOTE = "@cache·@lru_cache 로 감싼 재귀는 Python 3.12·3.13 에서 한도와 상관없이 약 3,300단계에서 멈춥니다."
ENCODE_NOTE = "반환값을 채점용 JSON 으로 바꾸지 못했습니다(%s)."


class OutputLimit(Exception):
    pass


class Collector(object):
    """sys.stdout·sys.stderr 자리에 들어가 출력을 모음. 1,000,000자를 넘으면 OutputLimit."""
    encoding = "utf-8"

    def __init__(self):
        self.parts = []
        self.size = 0

    def write(self, text):
        if not isinstance(text, str):
            text = str(text)
        self.size += len(text)
        if self.size > OUTPUT_LIMIT:
            raise OutputLimit(OUTPUT_NOTE)
        self.parts.append(text)
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False

    def text(self):
        return "".join(self.parts)


def capped_setrecursionlimit(n):
    """학생 코드의 sys.setrecursionlimit. 1000 보다 크면 모두 10,000 으로 맞춰 판마다 판정이 갈리지 않게 함."""
    setrecursionlimit(RAISED_LIMIT if n > BASE_LIMIT else n)


def write_file(path, text):
    """임시 이름에 쓴 뒤 바꿔치기함. Windows 는 부모가 읽는 순간 바꿔치기가 거부될 수 있어 몇 번 다시 함."""
    tmp = path + ".tmp"
    with opener(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    for attempt in range(20):
        try:
            replace(tmp, path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            sleep(0.005)


def reject(value):
    """허용하지 않는 반환값의 이유. 허용하면 빈 글. values.reject_py 와 같은 규칙임."""
    if value is None or isinstance(value, (bool, int, str)):
        return ""
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return FLOAT_NOTE % repr(value)
        return ""
    if isinstance(value, list):
        for item in value:
            bad = reject(item)
            if bad:
                return bad
        return ""
    if isinstance(value, tuple):
        return TUPLE_NOTE
    if isinstance(value, (set, frozenset)):
        return SET_NOTE
    if isinstance(value, dict):
        return DICT_NOTE
    if hasattr(value, "__next__"):
        return GENERATOR_NOTE
    return OTHER_NOTE % type(value).__name__


def encode(value):
    """(정규 JSON, 참고 문구). 허용하지 않는 값이면 (None, 이유)."""
    if value is None:
        return None, NONE_NOTE
    bad = reject(value)
    if bad:
        return None, bad
    return dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False), ""


def short_error(error, limit=300):
    message = "%s: %s" % (type(error).__name__, error)
    return message[:limit] + "…" if len(message) > limit else message


def line_of(error):
    """트레이스백에서 파일 이름이 solution.py 인 마지막 프레임의 줄 번호. 깊은 재귀의 트레이스백도 소스 파일을 찾지 않고 걸음."""
    line = None
    tb = error.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "solution.py":
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def error_text(error, line):
    message = str(error)
    if len(message) > 2000:
        message = message[:2000] + "…"
    text = "%s: %s" % (type(error).__name__, message)
    if line:
        text += " (%d번째 줄)" % line
    return text


def recursion_note(error, source):
    limit = getrecursionlimit()
    note = "재귀가 멈췄습니다(%s, 지금 한도 %d). " % (error, limit)
    if limit <= BASE_LIMIT:
        return note + LIMIT_LOW_NOTE
    note += LIMIT_HIGH_NOTE
    if CACHE_DECORATOR.search(source):
        note += " " + CACHE_NOTE
    return note


def peak_memory():
    """피크 메모리(바이트). POSIX 는 ru_maxrss(macOS 바이트, Linux KB), Windows 는 PeakWorkingSetSize."""
    if sys.platform == "win32":
        import ctypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_uint32), ("page_faults", ctypes.c_uint32)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak_working_set", "working_set", "peak_paged_pool", "paged_pool",
                    "peak_nonpaged_pool", "nonpaged_pool", "commit", "peak_commit")]

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        info = Counters()
        handle = ctypes.c_void_p(kernel32.GetCurrentProcess())
        if kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(info), ctypes.c_uint32(ctypes.sizeof(info))):
            return info.peak_working_set
        return 0
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def main(job_path):
    with opener(job_path, encoding="utf-8") as f:
        job = loads(f.read())
    write_file(job["pid"], str(os.getpid()))
    sys.setrecursionlimit = capped_setrecursionlimit

    out = Collector()
    sys.stdout = out
    sys.stderr = out
    result = {"status": "done", "values": [], "times_ns": [], "peak": 0, "printed": "", "printed_cut": False,
              "error": "", "note": "", "fatal": None, "failed_call": None}

    def finish():
        result["peak"] = peak_memory()
        printed = out.text()
        if len(printed) > PRINT_KEEP:
            result["printed"], result["printed_cut"] = printed[:PRINT_KEEP], True
        else:
            result["printed"] = printed
        write_file(job["result"], dumps(result))  # ASCII 로 써서 짝 없는 서로게이트가 든 반환값·출력도 쓰기에서 막히지 않음
        hard_exit(0)

    with opener(job["source"], encoding="utf-8") as f:
        source = f.read()
    try:
        code = compile(source, "solution.py", "exec")
    except SyntaxError as error:
        result["status"] = "fatal"
        result["fatal"] = {"kind": "syntax", "message": "%s: %s" % (type(error).__name__, error.msg), "line": error.lineno}
        finish()

    with opener(job["args"], encoding="utf-8") as f:
        all_args = loads(f.read())
    gc.collect()
    gc.freeze()

    def fail(k, status, error, note=""):
        result["status"] = status
        result["failed_call"] = k
        result["error"] = error_text(error, line_of(error))
        result["note"] = note

    def work():
        for k, args in enumerate(all_args):
            setrecursionlimit(BASE_LIMIT)
            write_file(job["calling"], "load %d" % k)
            namespace = {"__name__": "solution", "__builtins__": builtins}
            try:
                exec(code, namespace)
            except BaseException as error:
                note = OUTPUT_NOTE if isinstance(error, OutputLimit) else ""
                if k == 0:
                    result["status"] = "fatal"
                    result["fatal"] = {"kind": "load", "message": "%s: %s" % (type(error).__name__, error),
                                       "line": line_of(error)}
                    result["note"] = note
                else:
                    fail(k, "runtime", error, note)
                return
            function = namespace.get("solution")
            if not callable(function):
                result["status"] = "fatal"
                result["fatal"] = {"kind": "no_solution", "message": "solution 함수가 없습니다.", "line": None}
                return
            write_file(job["calling"], "call %d" % k)
            t0 = perf()
            try:
                value = function(*args)
                t1 = perf()
            except RecursionError as error:
                result["times_ns"].append(perf() - t0)
                fail(k, "runtime", error, recursion_note(error, source))
                return
            except MemoryError as error:
                result["times_ns"].append(perf() - t0)
                fail(k, "memory", error)
                return
            except OutputLimit as error:
                result["times_ns"].append(perf() - t0)
                fail(k, "runtime", error, OUTPUT_NOTE)
                return
            except EOFError as error:
                result["times_ns"].append(perf() - t0)
                fail(k, "runtime", error, INPUT_NOTE)
                return
            except BaseException as error:
                result["times_ns"].append(perf() - t0)
                fail(k, "runtime", error)
                return
            result["times_ns"].append(t1 - t0)
            try:
                text, note = encode(value)
            except MemoryError as error:
                fail(k, "memory", error)
                return
            except Exception as error:  # 4300자를 넘는 정수, 너무 깊게 겹친 리스트, 속성 접근에서 예외를 내는 객체
                text, note = None, ENCODE_NOTE % short_error(error)
            if text is None:
                result["status"] = "bad_return"
                result["failed_call"] = k
                result["note"] = note
                return
            result["values"].append(text)

    def run():
        try:
            work()
        except BaseException as error:  # 하네스 자체의 오류. 부모가 비정상 종료로 보여 줌
            result["status"] = "crash"
            result["error"] = "%s: %s" % (type(error).__name__, error)

    try:
        threading.stack_size(STACK_MB * 2 ** 20)
    except (ValueError, RuntimeError):
        pass
    worker = threading.Thread(target=run)
    worker.start()
    worker.join()
    finish()


if __name__ == "__main__":
    main(sys.argv[1])
