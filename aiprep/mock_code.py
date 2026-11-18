# -*- coding: utf-8 -*-
"""모의고사 코드 작성 문항을 알고리즘 여행 실행기(journey/runner.py, harness.py)로 채점함.

채울 줄 목록을 시작 코드의 `____` 줄에 넣어 solution.py 를 만들고, 끝에 `solution = <entry>` 를 붙여 하네스가 부르게 함.
grade 는 숨은 테스트(tests)를 첫 실패에서 멈추지 않고 모두 돌려 통과 수를 셈. 숨은 테스트 결과에는 상태와 틀린 이유만
남기고 입력·기대값·실제 값, 자식이 낸 오류 글·출력·참고 문구·실패 호출 번호는 버림. try_code 는 [코드 실행]용이라
공개 예시만 인자로 받고 숨은 테스트는 받지 않음.

기대값에 실수가 없으면 정규 JSON 글을 실행기에 넘겨 실행기의 pass/wrong 을 씀. 실수가 있으면 기대값 없이 돌리고
실행기의 pass 는 쓰지 않으며, 돌려받은 값을 부모가 허용 오차로 비교함.

실행 환경 실패: 임시 폴더·Popen 의 OSError, 또는 학습자 결과가 충돌 꼴이고 그 뒤 새 임시 폴더에서 모범 답안을 공개 예시
하나로 돌려도 충돌 꼴인 경우임. 모범 답안 폴더는 학습자 코드를 다 돌리고 그 폴더를 지운 뒤에 만들고, 모범 답안을 다 돌린 뒤 지움.

Windows 에서 다를 수 있는 곳
- 경로: 임시 폴더는 %TEMP% 아래에 생기고, 자식의 명령줄과 job.json 에는 작업 폴더 기준 상대 경로만 들어감(runner.command,
  runner.run_case). 드라이브가 다르면 runner._relative 가 절대 경로로 바꿈.
- 인코딩: solution.py 는 study.write_text 로 UTF-8·LF 로 쓰고 자식은 -X utf8 로 띄움. 한글 주석·문자열이 든 답도 같게 읽힘.
- 프로세스 정리: 시간 초과면 runner.stop 이 자식을 끊고 5초 기다림. 그 안에 끝나지 않으면 TemporaryDirectory 가
  케이스 폴더를 지우지 못하고 남길 수 있음(ignore_cleanup_errors). 남는 파일에는 숨은 입력(args.json)이 있을 수 있으나
  기대값은 디스크에 쓰지 않음.
- 창 숨김: 자식은 runner 의 creationflags=study.NO_WINDOW 로 띄우고, 창 모드(pythonw)에서는 study.console_python 이
  같은 폴더의 python.exe 를 고름.
- 첫 실행이 백신 검사로 늦어 START_LIMIT_S(10초)를 넘으면 충돌 꼴로 보고 모범 답안을 돌려 봄.
"""
import functools
import hashlib
import json
import os

import study
from journey import runner, values

FILL = "____"
RUNTIME_FILES = ("aiprep/mock_code.py", "journey/runner.py", "journey/harness.py", "journey/values.py")
LANG = "python"
LIMIT_MS = 2000
TOL = 1e-6
PASS, STUCK, ENV = "pass", "stuck", "env"
CRASH_PREFIX = runner.CRASH_NOTE.split("%s")[0]

REASONS = {
    "runtime": "실행 중 오류가 났습니다.",
    "fatal": "코드를 실행하지 못했습니다. 문법과 들여쓰기를 확인하세요.",
    "timeout": "시간 제한 안에 끝나지 않았습니다.",
    "memory": "메모리 제한을 넘었습니다.",
    "bad_return": "돌려줄 수 없는 값입니다. 정수·실수·문자열·불리언이나 그 리스트로 돌려주세요.",
}
ENV_REASON = "이 기기에서 코드를 실행하지 못했습니다."
WRONG_REASON = "돌려준 값이 다릅니다."


def fill_count(starter):
    return sum(1 for row in starter.split("\n") if row.strip() == FILL)


@functools.lru_cache(maxsize=1)
def runtime_revision():
    """코드 채점에 쓰는 RUNTIME_FILES 의 해시. code 문항의 수집 문항 버전에만 넣음."""
    folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hashes = {}
    for name in RUNTIME_FILES:
        with open(os.path.join(folder, name), "rb") as stream:
            hashes[name] = hashlib.sha256(stream.read()).hexdigest()
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode("utf-8")).hexdigest()


def source(starter, entry, lines):
    """채울 줄을 시작 코드에 넣은 solution.py 원문. 들여쓰기는 시작 코드의 `____` 줄이 정하므로 채울 줄 앞 공백은 버림."""
    rows = starter.split("\n")
    slots = [index for index, row in enumerate(rows) if row.strip() == FILL]
    if len(lines) != len(slots):
        raise ValueError("채울 줄 수가 시작 코드와 다릅니다.")
    for index, text in zip(slots, lines):
        row = rows[index]
        rows[index] = row[:len(row) - len(row.lstrip())] + text.lstrip()
    return "\n".join(rows).rstrip("\n") + "\n\n\nsolution = %s\n" % entry


def _has_float(value):
    if isinstance(value, list):
        return any(_has_float(item) for item in value)
    return isinstance(value, float)


def _kind(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    return "other"


def _where(path):
    return "돌려준 값에서 " + " 안의 ".join("%d번째 원소" % (index + 1) for index in path) + "의 " if path else "돌려준 값의 "


def _difference(actual, expected, tol, path=()):
    """처음 다른 곳의 이유 글. 같으면 None. 자료형, 길이, 값 순서로 보고 이유 글에 값은 넣지 않음.

    실수 기대값 자리에는 같은 값의 정수도 맞음. 정수 기대값 자리의 실수와 숫자 자리의 불리언은 자료형이 다름."""
    want, got = _kind(expected), _kind(actual)
    if not (got == want or (want == "float" and got == "int")):
        return _where(path) + "자료형이 다릅니다."
    if want == "list":
        if len(actual) != len(expected):
            return _where(path) + "길이가 다릅니다."
        for index, (one, other) in enumerate(zip(actual, expected)):
            found = _difference(one, other, tol, path + (index,))
            if found:
                return found
        return None
    if want == "float":
        try:
            same = abs(actual - expected) <= tol + tol * abs(expected)
        except OverflowError:
            # 실수로 바꿀 수 없을 만큼 큰 정수는 기대값과 다른 값으로 봄
            same = False
    else:
        same = actual == expected
    if same:
        return None
    return _where(path) + "값이 다릅니다." if path else WRONG_REASON


def _case(test, limit_ms):
    case = {"args": [test["args"]], "calls": 1, "limit_ms": limit_ms, "bundle": False}
    if not _has_float(test["expected"]):
        case["expected"] = values.canonical(test["expected"])
    return case


def _judge(result, expected, tol):
    """실행기 결과 하나를 (상태, 이유)로 바꿈. 기대값에 실수가 있으면 실행기의 pass 를 쓰지 않음."""
    status = result["status"]
    if status not in ("pass", "wrong"):
        return status, REASONS.get(status, REASONS["runtime"])
    actual = json.loads(result["values"][0])
    if _has_float(expected):
        reason = _difference(actual, expected, tol)
    elif status == "pass":
        reason = None
    else:
        reason = _difference(actual, expected, tol) or WRONG_REASON
    return ("wrong", reason) if reason else ("pass", "")


def _crashed(result):
    """자식이 결과를 남기지 못하고 끝났거나 solution 을 부르기 전에 멈춘 꼴(runner.compose 의 CRASH_NOTE·START_NOTE)."""
    note = result.get("note") or ""
    return ((result["status"] == "runtime" and note.startswith(CRASH_PREFIX))
            or (result["status"] == "timeout" and note == runner.START_NOTE))


def _run(text, cases, workers):
    """새 임시 폴더에 solution.py 와 하네스를 두고 돌림. 돌려줄 때는 폴더가 지워져 있음."""
    with runner.workspace() as workdir:
        path = os.path.join(workdir, "solution.py")
        study.write_text(path, text)
        runner.prepare(LANG, path, workdir)
        return runner.run_cases(LANG, path, cases, workers=workers, workdir=workdir)


def _tol(tol):
    return TOL if tol is None else tol


def _env(total):
    return {"result": ENV, "passed": 0, "total": total, "reason": ENV_REASON, "cases": []}


def _solution_runs(item):
    """학습자 결과가 충돌 꼴일 때만 부름. 모범 답안을 공개 예시 하나로 돌려 충돌 꼴이나 OSError 가 아니면 참."""
    code = item["code"]
    text = source(code["starter"], code["entry"], item["solution"])
    try:
        result = _run(text, [_case(code["examples"][0], code.get("limit_ms") or LIMIT_MS)], 1)[0]
    except OSError:
        return False
    return not _crashed(result)


def grade(item, lines, workers=None):
    """제출 채점. 숨은 테스트를 모두 돌려 {"result", "passed", "total", "reason", "cases"} 를 돌려줌.

    result 는 pass(모두 통과), stuck(하나라도 실패), env(실행 환경 실패). cases 는 테스트마다 {"status", "reason"} 만 담음."""
    code = item["code"]
    tests = code["tests"]
    tol = _tol(code.get("tol"))
    limit_ms = code.get("limit_ms") or LIMIT_MS
    try:
        raw = _run(source(code["starter"], code["entry"], lines), [_case(test, limit_ms) for test in tests],
                   runner.workers() if workers is None else workers)
    except OSError:
        return _env(len(tests))
    if any(_crashed(result) for result in raw) and not _solution_runs(item):
        return _env(len(tests))
    cases = [dict(zip(("status", "reason"), _judge(result, test["expected"], tol))) for result, test in zip(raw, tests)]
    failed = [index for index, case in enumerate(cases) if case["status"] != "pass"]
    reason = "숨은 테스트 %d번: %s" % (failed[0] + 1, cases[failed[0]]["reason"]) if failed else ""
    return {"result": STUCK if failed else PASS, "passed": len(cases) - len(failed), "total": len(cases),
            "reason": reason, "cases": cases}


def try_code(starter, entry, examples, lines, limit_ms=None, tol=None, workers=None):
    """[코드 실행]. 공개 예시만 돌리고 기록하지 않음. 숨은 테스트는 인자로 받지 않음.

    예시 결과는 입력·기대값·돌려준 값·출력·오류 글을 그대로 담음. 결과 모양은 grade 와 같고 cases 항목마다 칸이 더 많음."""
    tol = _tol(tol)
    try:
        raw = _run(source(starter, entry, lines), [_case(example, limit_ms or LIMIT_MS) for example in examples],
                   runner.workers() if workers is None else workers)
    except OSError:
        return _env(len(examples))
    cases = []
    for result, example in zip(raw, examples):
        status, reason = _judge(result, example["expected"], tol)
        actual = json.loads(result["values"][0]) if result["values"] else None
        cases.append({"status": status, "reason": reason, "args": example["args"], "expected": example["expected"],
                      "actual": actual, "printed": result["printed"], "error": result["error"],
                      "note": result["note"]})
    failed = [index for index, case in enumerate(cases) if case["status"] != "pass"]
    reason = "예시 %d번: %s" % (failed[0] + 1, cases[failed[0]]["reason"]) if failed else ""
    return {"result": STUCK if failed else PASS, "passed": len(cases) - len(failed), "total": len(cases),
            "reason": reason, "cases": cases}
