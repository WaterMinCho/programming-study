# -*- coding: utf-8 -*-
"""여정 문제 화면의 결과 칸에 넣을 HTML. 프로그래머스의 결과 화면과 같은 꼴임.
[코드 실행]은 테스트마다 입력값·기댓값·실행 결과를 보여 줌.
[제출 후 채점하기]는 그룹마다 "테스트 N 〉 통과 (0.42ms, 10.3MB)" 줄과 점수를 보여 줌.
색은 본문 CSS 의 클래스(.ok .wrong .muted)로 주어 테마가 바뀌면 HTML 을 다시 넣기만 하면 됨. PyQt 를 import 하지 않아서 화면 없이 시험할 수 있음.

결과가 다 오기 전에도 done=False 로 부르면 지금까지 온 줄만 그림. 진행 중에는 요약과 안내 줄을 붙이지 않음.
결과 카드는 run_body·grade_body 로 테스트 줄과 끝의 안내 줄만 그림. 합계와 통과 여부 같은 요약은 카드 머리(journey_text.result_head)가 말함."""
import html
import re

import study
from journey import grading, runner

BOSS_LINK = "journey:boss"  # [보스에 도전하기] 링크의 주소. 문제 화면이 이 주소를 받아 보스 문제를 엶
MEMORY_NOTE = "메모리에는 시작할 때 쓰는 양(Python 약 15MB, Node.js 약 35MB)이 들어 있습니다."
STOPPED_RUN = "실행을 중지했습니다. 코드 실행은 기록되지 않습니다."
STOPPED_GRADE = "중지했습니다. 이번 채점은 기록하지 않았습니다."
HIDDEN_NOTE = "숨은 테스트의 입력은 보이지 않습니다. [테스트 추가]로 비슷한 입력을 넣어 실행해 보세요."
EXAMPLE_ID = re.compile(r"ex\d+\Z")  # grading.example_tests 가 입출력 예에 붙이는 id. 나머지 채점 줄은 숨은 테스트임


def esc(text):
    return html.escape(str(text), quote=False)


def para(text, kind=""):
    """이미 HTML 로 만든 글 한 줄."""
    return "<p%s>%s</p>" % (' class="%s"' % kind if kind else "", text)


def code_box(text):
    """mdlite 의 코드 블록과 같은 상자. 오류 메시지와 출력을 담음."""
    return ('<table width="100%%" cellspacing="0" cellpadding="8" border="0" style="margin-top:2px; margin-bottom:6px;">'
            '<tr><td class="codebox"><pre>%s</pre></td></tr></table>' % esc(text))


def fatal_text(fatal):
    """"SyntaxError: invalid syntax (3번째 줄)" 꼴. 줄 번호를 모르면 메시지만."""
    message = fatal.get("message") or "코드를 불러오지 못했습니다."
    if fatal.get("line"):
        message += " (%d번째 줄)" % fatal["line"]
    return message


def note_line(note):
    return para('<span class="muted">참고 〉</span> %s' % esc(note)) if note else ""


def fatal_html(fatal):
    return para('<span class="wrong">%s</span>' % esc(fatal_text(fatal))) + note_line(fatal.get("note"))


# [코드 실행]

def run_verdict(case):
    """"실행 결과 〉" 뒤의 글과 그 아래에 붙는 HTML."""
    status = case["status"]
    if status == "pass":
        return '<span class="ok">테스트를 통과하였습니다.</span>', ""
    if status in ("wrong", "bad_return"):
        got = " 실행한 결괏값: <code>%s</code>" % esc(case["got_text"]) if case.get("got_text") else ""
        return '<span class="wrong">기댓값과 다릅니다.</span>' + got, note_line(case.get("note"))
    if status == "runtime":
        return '<span class="wrong">실행 중 오류가 발생했습니다.</span>', code_box(case.get("error") or "") + note_line(case.get("note"))
    if status == "timeout":
        seconds = runner.RUN_LIMIT_MS / 1000.0
        return '<span class="wrong">실행 시간이 %.1f초를 초과하여 실행이 중단되었습니다.</span>' % seconds, note_line(case.get("note"))
    if status == "memory":
        return '<span class="wrong">메모리를 %dMB 넘게 써서 실행이 중단되었습니다.</span>' % study.MEMORY_LIMIT_MB, ""
    if status == "cancelled":
        return '<span class="muted">중지했습니다.</span>', ""
    return '<span class="wrong">실행하지 못했습니다.</span>', note_line(case.get("note"))


def run_case_html(case):
    parts = [para("테스트 %d" % case["no"], "h3"),
             para("입력값 〉 <code>%s</code>" % esc(case["args_text"])),
             para("기댓값 〉 <code>%s</code>" % esc(case["want_text"]))]
    verdict, below = run_verdict(case)
    parts.append(para("실행 결과 〉 " + verdict))
    parts.append(below)
    if case["status"] in ("pass", "wrong", "bad_return"):
        shown = grading.measure(case.get("ms"), case.get("mb"))
        if shown:
            parts.append(para('<span class="muted">시간·메모리 〉 %s</span>' % shown))
    if case.get("printed"):
        parts.append(para("출력 〉"))
        parts.append(code_box(case["printed"].rstrip("\n")))
        if case.get("printed_cut"):
            parts.append(para("출력이 길어 앞부분만 보여 줍니다.", "muted"))
    return "".join(parts)


def run_lines(result):
    """[코드 실행]의 fatal 줄과 테스트 줄."""
    parts = [fatal_html(result["fatal"])] if result.get("fatal") else []
    parts.extend(run_case_html(case) for case in result.get("cases") or [])
    return parts


def runtime_line(result):
    return [para("실행 환경 %s" % esc(result["runtime"]), "muted")] if result.get("runtime") else []


def run_body(result, done=True):
    """결과 카드의 [코드 실행] 본문. run_html 에서 요약 줄(테스트 결과, 중지 안내, 시간 제한)을 빼고 끝에 실행 환경을 붙임."""
    return "<body>%s</body>" % "".join(run_lines(result) + (runtime_line(result) if done else []))


def run_html(result, done=True):
    """[코드 실행] 결과(명세 4.1 의 dict). done=False 면 지금까지 끝난 테스트 줄만."""
    parts = run_lines(result)
    if done:
        if result.get("cancelled"):
            parts.append(para(STOPPED_RUN, "muted"))
        elif not result.get("fatal"):
            parts.append(para("테스트 결과 %d개 중 %d개 성공" % (result.get("total", 0), result.get("passed", 0)), "h3"))
        if result.get("limit_note"):
            parts.append(para(esc(result["limit_note"]), "muted"))
    return "<body>%s</body>" % "".join(parts)


# [제출 후 채점하기]

def grade_line(case):
    mark = "ok" if case["status"] == "pass" else ("muted" if case["status"] == "cancelled" else "wrong")
    text = '테스트 %d 〉 <span class="%s">%s</span>' % (case["no"], mark, esc(case["label"]))
    if case.get("name"):
        text += ' <span class="muted">· %s</span>' % esc(case["name"])
    return para(text)


def grade_lines(result):
    """[제출 후 채점하기]의 fatal 줄, 또는 그룹마다 이름과 테스트 줄."""
    if result.get("fatal"):
        return [fatal_html(result["fatal"])]
    parts = []
    for group in result.get("groups") or []:
        parts.append(para("%s 테스트" % esc(group["name"]), "h3"))
        parts.extend(grade_line(case) for case in group["cases"])
    return parts


def hidden_failed(result):
    """입출력 예가 아닌 채점 줄 가운데 통과하지 못한 줄이 있는지. 취소된 줄은 세지 않음."""
    return any(case["status"] not in ("pass", "cancelled") and not EXAMPLE_ID.match(str(case.get("id") or ""))
               for group in result.get("groups") or [] for case in group["cases"])


def grade_body(result, done=True):
    """결과 카드의 [채점하기] 본문. grade_html 에서 요약 줄(채점 결과, 합계, 처음 통과, 보스 링크, 중지 안내)을 뺌.
    끝까지 돈 채점이면 끝에 숨은 테스트 안내(숨은 테스트가 틀렸을 때), 실행 환경, 메모리 안내를 붙임."""
    parts = grade_lines(result)
    if done and not result.get("cancelled"):
        if not result.get("fatal") and hidden_failed(result):
            parts.append(para(HIDDEN_NOTE, "muted"))
        parts.extend(runtime_line(result))
        if not result.get("fatal"):
            parts.append(para(MEMORY_NOTE, "muted"))
    return "<body>%s</body>" % "".join(parts)


def grade_html(result, done=True):
    """[제출 후 채점하기] 결과(명세 4.2 의 dict). done=False 면 지금까지 끝난 그룹과 줄만."""
    parts = grade_lines(result)
    if not done:
        return "<body>%s</body>" % "".join(parts)
    if result.get("cancelled"):
        parts.append(para(STOPPED_GRADE, "muted"))
        return "<body>%s</body>" % "".join(parts)
    parts.append(para("채점 결과", "h3"))
    if not result.get("fatal"):
        for group in result.get("groups") or []:
            parts.append(para("%s: %.1f" % (esc(group["name"]), group["earned"])))
    parts.append(para("<b>합계: %.1f / 100.0</b>" % (result.get("score") or 0.0)))
    if result.get("first_pass"):
        parts.append(para('<span class="ok">처음으로 통과했습니다. 해설을 볼 수 있습니다.</span>'))
    if result.get("boss_opened"):
        parts.append(para('<span class="ok">보스 문제가 열렸습니다.</span> <a href="%s">보스에 도전하기</a>' % BOSS_LINK))
    if result.get("runtime"):
        parts.append(para("%s로 실행했습니다." % esc(result["runtime"]), "muted"))
    if not result.get("fatal"):
        parts.append(para(MEMORY_NOTE, "muted"))
    return "<body>%s</body>" % "".join(parts)
