# -*- coding: utf-8 -*-
"""여정 문제의 [코드 실행]과 [제출 후 채점하기]. 테스트를 실행기 케이스로 바꾸고, 판정 문구와 점수를 매김.

화면과 검증 도구가 같은 판정을 쓰도록 실행은 모두 runner 를 거침. 기록은 하지 않음(service 가 함).
report 를 주면 진행을 dict 로 알림.
  {"kind": "status", "text": 문구}                          진행 문구(입력 만들기 등)
  {"kind": "case", "group": 그룹 이름, "case": 줄}          채점 줄 하나가 끝남(그룹 안 번호 순서)
  {"kind": "case", "case": 줄}                               코드 실행 케이스 하나가 끝남
"""
import json
import math
import os

from journey import bank, runner, values

ACCURACY = "정확성"
EFFICIENCY = "효율성"
ROLE_POINTS = {"basic": (70, 30), "mid": (60, 40), "side": (60, 40), "boss": (50, 50)}  # problem.json 에 score 가 없을 때
PRINT_LINES, PRINT_CHARS = 200, 20000  # 코드 실행의 "출력 〉" 을 자르는 곳
GEN_TEXT = "효율성 테스트 입력을 만드는 중입니다(처음 한 번만 오래 걸립니다)."
ACC_TEXT = "정확성 테스트를 채점하는 중입니다."
EFF_TEXT = "효율성 테스트를 채점하는 중입니다."
LIMIT_NOTE = "채점에서는 Python %s초, JavaScript %s초 안에 끝나야 합니다."
FAILED = {"timeout": "실패 (시간 초과)", "memory": "실패 (메모리 초과)"}  # 그 밖의 실패(runtime, fatal)는 런타임 에러


def round1(x):
    """소수 첫째 자리 반올림(0.05 는 올림). 화면과 기록이 같은 값을 씀."""
    return math.floor(x * 10 + 0.5 + 1e-9) / 10


def seconds(ms):
    """3000 → "3", 3500 → "3.5"."""
    return ("%.1f" % (ms / 1000.0)).rstrip("0").rstrip(".")


def limit_note(problem):
    limits = problem["time_limit_ms"]
    return LIMIT_NOTE % (seconds(limits["python"]), seconds(limits["javascript"]))


def points(problem, role, has_efficiency):
    """(정확성 배점, 효율성 배점). 고른 언어에서 도는 효율성 테스트가 없으면 정확성 100."""
    if not has_efficiency:
        return 100.0, 0.0
    score = problem.get("score")
    if score:
        return float(score["accuracy"]), float(score["efficiency"])
    acc, eff = ROLE_POINTS[role]
    return float(acc), float(eff)


def example_tests(problem):
    return [{"id": "ex%d" % (index + 1), "name": "입출력 예 %d" % (index + 1), "args": ex["args"], "expected": ex["expected"]}
            for index, ex in enumerate(problem["examples"])]


def accuracy_tests(problem, tests):
    """정확성 그룹 = examples(id ex1, ex2, …) + tests.json 의 accuracy."""
    return example_tests(problem) + list(tests.get("accuracy") or [])


def efficiency_tests(tests, lang):
    """고른 언어에서 도는 효율성 테스트(langs 가 없으면 두 언어)."""
    return [test for test in tests.get("efficiency") or [] if lang in (test.get("langs") or values.LANGS)]


def gen_spec(test):
    return {"gen": test["gen"], "seed": test["seed"], "params": test.get("params") or {}, "count": test.get("count")}


def is_cached(gen_source, test):
    path = os.path.join(runner.cache_dir(), runner.cache_key(gen_source, gen_spec(test)) + ".json")
    return os.path.isfile(path)


def check_expected(test):
    """expected 도 expected_sha 도 없는 테스트는 어떤 답이든 통과시키므로 bank.BankError 로 막음."""
    if "expected" not in test and not test.get("expected_sha"):
        raise bank.BankError("tests.json 의 %s 에 expected 도 expected_sha 도 없습니다." % test.get("id"))


def make_case(test, gen_source, limit_ms, kill_ms):
    """tests.json 의 테스트 하나를 runner.run_case 의 case 로. 생성 테스트는 캐시된 입력 파일을 씀(없으면 만듦).
    기댓값이 없으면 bank.BankError."""
    check_expected(test)
    case = {"calls": test.get("count") or 1, "bundle": bool(test.get("count")), "limit_ms": limit_ms, "kill_ms": kill_ms}
    if "gen" in test:
        if gen_source is None:
            raise runner.GenError("gen.py 가 없어 %s 의 입력을 만들 수 없습니다." % test.get("id"))
        case["args_path"] = runner.generated_args(gen_source, gen_spec(test))
    else:
        case["args"] = [test["args"]]
    if "expected" in test:
        case["expected"] = values.canonical(test["expected"])
    else:
        case["expected_sha"] = test["expected_sha"]
    return case


def measure(ms, mb):
    parts = []
    if ms is not None:
        parts.append("%.2fms" % ms)
    if mb is not None:
        parts.append("%.1fMB" % mb)
    return ", ".join(parts)


def label(status, ms=None, mb=None, count=None):
    """채점 줄의 판정 문구. 묶음은 끝에 " · 50건" 을 붙임."""
    if status == "cancelled":
        return "취소됨"
    if status in ("pass", "wrong", "bad_return"):
        shown = measure(ms, mb)
        text = ("통과" if status == "pass" else "실패") + (" (%s)" % shown if shown else "")
    else:
        text = FAILED.get(status, "실패 (런타임 에러)")
    if count:
        text += " · %d건" % count
    return text


def _fatal(raw):
    fatal = dict(raw.get("fatal") or {"kind": "load", "message": raw.get("error") or "", "line": None})
    fatal["note"] = raw.get("note") or ""
    return fatal


def _as_runtime(raw):
    """첫 케이스는 돌았는데 뒤 케이스가 fatal 이면(최상위 코드가 일부 프로세스에서만 실패) 그 줄만 런타임 에러로 봄."""
    if raw["status"] != "fatal":
        return raw
    raw = dict(raw, status="runtime")
    raw["error"] = raw["error"] or (raw.get("fatal") or {}).get("message") or ""
    return raw


def _clip(text):
    """코드 실행의 출력을 200줄·20,000자에서 자름. (글, 잘렸는지)."""
    lines = text.split("\n")
    cut = False
    if len(lines) > PRINT_LINES:
        text, cut = "\n".join(lines[:PRINT_LINES]), True
    if len(text) > PRINT_CHARS:
        text, cut = text[:PRINT_CHARS], True
    return text, cut


def run(problem, lang, source_path, mine=(), report=None, cancel=None, node=None):
    """[코드 실행]: examples 와 내가 추가한 케이스를 하나씩, 호출마다 10초 제한으로 돌림. 결과 모양은 명세 4.1(runtime 은 service 가 채움)."""
    items = [("example", ex["args"], ex["expected"]) for ex in problem["examples"]]
    items += [("mine", case["args"], case["expected"]) for case in mine]
    cases = [{"args": [args], "calls": 1, "limit_ms": runner.RUN_LIMIT_MS, "kill_ms": runner.RUN_KILL_MS,
              "expected": values.canonical(expected)} for _, args, expected in items]
    lines = []

    def on_case(index, raw):
        if raw["status"] == "fatal" and not lines:  # 첫 케이스의 fatal 과 그 복사본은 줄 없이 fatal 하나로 보임
            return
        raw = _as_runtime(raw)
        source, args, expected = items[index]
        got = ""
        if raw["values"]:
            got = values.show(json.loads(raw["values"][0]), lang)
        printed, cut = _clip(raw["printed"])
        line = {"no": index + 1, "source": source, "args_text": values.show_args(args, lang),
                "want_text": values.show(expected, lang), "got_text": got, "status": raw["status"],
                "ok": raw["status"] == "pass", "ms": raw["elapsed_ms"], "mb": raw["peak_mb"], "printed": printed,
                "printed_cut": cut or raw["printed_cut"], "error": raw["error"], "note": raw["note"]}
        lines.append(line)
        if report:
            report({"kind": "case", "case": line})

    raws = runner.run_cases(lang, source_path, cases, 1, on_case, cancel, node)
    fatal = _fatal(raws[0]) if raws and raws[0]["status"] == "fatal" else None
    return {"lang": lang, "fatal": fatal, "cases": [] if fatal else lines,
            "passed": sum(1 for line in lines if line["ok"]) if not fatal else 0, "total": len(items),
            "cancelled": any(raw["status"] == "cancelled" for raw in raws), "limit_note": limit_note(problem)}


def _prepare_cases(group, tests, gen_source, limit_ms, report, cancel):
    """그룹의 테스트를 case 로. 효율성 입력을 처음 만들 때는 진행 문구를 알림. 만드는 사이에 취소되면 None."""
    if group == EFFICIENCY and report and any("gen" in t and not is_cached(gen_source, t) for t in tests):
        report({"kind": "status", "text": GEN_TEXT})
    cases = []
    for test in tests:
        if cancel is not None and cancel.is_set():
            return None
        cases.append(make_case(test, gen_source, limit_ms, runner.grade_kill_ms(limit_ms)))
    return cases


def grade(problem, role, tests, gen_source, lang, source_path, report=None, cancel=None, node=None, reveal=False):
    """[제출 후 채점하기]. 정확성 그룹은 동시에, 효율성 그룹은 하나씩 돌림. 결과 모양은 명세 4.2(runtime 과
    first_pass·boss_opened·cleared 는 service 가 채움). tests 는 tests.json 의 내용, gen_source 는 gen.py 원문.
    reveal 이면 실패한 정확성 줄에 테스트 이름을 붙임. 입력 생성이 실패하면 runner.GenError, 기댓값이 없는 테스트가
    있으면 돌리기 전에 bank.BankError. fatal 은 채점의 첫 케이스에서 났을 때만 결과 전체의 fatal 로 봄."""
    limit_ms = problem["time_limit_ms"][lang]
    acc_tests, eff_tests = accuracy_tests(problem, tests), efficiency_tests(tests, lang)
    for test in acc_tests + eff_tests:
        check_expected(test)
    acc_points, eff_points = points(problem, role, bool(eff_tests))
    plan = [(ACCURACY, acc_points, acc_tests, runner.workers(), ACC_TEXT)]
    if eff_tests:
        plan.append((EFFICIENCY, eff_points, eff_tests, 1, EFF_TEXT))
    result = {"lang": lang, "fatal": None, "cancelled": False, "groups": [], "acc": 0.0, "eff": 0.0, "score": 0.0,
              "passed": False, "tests": [0, len(acc_tests), 0, len(eff_tests)]}
    with runner.workspace() as folder:
        # 캐시 입력 파일을 케이스 폴더 기준 상대 경로로 넘기므로 실제 경로로 바꿈(macOS 의 /var 는 /private/var 의 링크임)
        workdir = os.path.realpath(folder)
        runner.prepare(lang, source_path, workdir)
        for name, group_points, group_tests, workers, text in plan:
            cases = _prepare_cases(name, group_tests, gen_source, limit_ms, report, cancel)
            if cases is None:
                result["cancelled"] = True
                break
            if report:
                report({"kind": "status", "text": text})
            lines = []

            def on_case(index, raw, name=name, group_tests=group_tests, lines=lines):
                if raw["status"] == "fatal" and not lines and not result["groups"]:
                    return
                test = group_tests[index]
                status = _as_runtime(raw)["status"]
                shown = reveal and name == ACCURACY and status not in ("pass", "cancelled")
                line = {"no": index + 1, "id": test["id"], "status": status,
                        "label": label(status, raw["elapsed_ms"], raw["peak_mb"], test.get("count")),
                        "ms": raw["elapsed_ms"], "mb": raw["peak_mb"], "count": test.get("count"),
                        "name": test.get("name") if shown else None}
                lines.append(line)
                if report:
                    report({"kind": "case", "group": name, "case": line})

            raws = runner.run_cases(lang, source_path, cases, workers, on_case, cancel, node, workdir=workdir)
            if raws and raws[0]["status"] == "fatal" and not lines:
                result["fatal"] = _fatal(raws[0])
                result["groups"] = []
                break
            passed = sum(1 for line in lines if line["status"] == "pass")
            earned = round1(group_points * passed / len(lines)) if lines else 0.0
            result["groups"].append({"name": name, "points": group_points, "earned": earned, "cases": lines})
            if any(line["status"] == "cancelled" for line in lines):
                result["cancelled"] = True
                break
    if result["fatal"] or result["cancelled"]:
        return result
    groups = result["groups"]
    result["acc"] = groups[0]["earned"]
    result["eff"] = groups[1]["earned"] if len(groups) > 1 else 0.0
    result["score"] = round1(result["acc"] + result["eff"])
    counts = [sum(1 for line in group["cases"] if line["status"] == "pass") for group in groups]
    result["tests"] = [counts[0], len(acc_tests), counts[1] if len(counts) > 1 else 0, len(eff_tests)]
    result["passed"] = all(line["status"] == "pass" for group in groups for line in group["cases"])
    return result
