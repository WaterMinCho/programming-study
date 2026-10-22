# -*- coding: utf-8 -*-
"""웹 면접 준비 터미널 명령. `python study.py web <명령>` 으로 들어옴(study.main 이 넘김).

화면 없이 미션 하나를 [미션 받기]부터 해설까지, 사슬 하나를 답 시간·자기 채점·다음 복습 날짜까지 끝낼 수 있음.
출력·입력·시계는 main(argv, out, ask, clock) 으로 바꿔 끼울 수 있어 테스트가 터미널 없이 돌림. 창이나 편집기, 브라우저를 열지 않음.
`dev` 는 Ctrl+C 를 누를 때까지 화면 서버를 켜 두고, 테스트는 time.sleep 을 바꿔 끼워 Ctrl+C 를 흉내 냄.
표준 입력이 터미널이 아니면(파이프, 파일) PipeAsk 로 묻고, 한 줄이 PIPE_WAIT_S 안에 오지 않으면 입력이 끝난 것으로 봄.
열려 있지만 아무것도 쓰지 않는 파이프에서 영영 기다리지 않게 하려는 것이고, 파이프로 미리 넣은 답은 그대로 읽음.
"""
import argparse
import os
import queue
import sys
import threading
import time

import session
import study
from webprep import dev, service
from webprep.service import WebError

USAGE = """웹 면접 준비 (터미널)

  python study.py web status                 Node·설치 상태, 미션·사슬·학습 노트 현황, 오늘 복습
  python study.py web install [--yes]        검사 도구 설치 (처음 한 번, 인터넷 필요)
  python study.py web uninstall              검사 도구 지우기
  python study.py web get <미션> [--again]    [미션 받기] 코드를 내 폴더로 복사하고 읽기 시간 시작
  python study.py web start <미션>            [실전 시작] 0단계(코드 설명)가 열립니다
  python study.py web check <미션>            [검사하기] 0단계면 점검 항목 표시, 그 뒤는 단계 검사
  python study.py web answer <미션>           통과 뒤 질문에 답하지 못하고 넘어갔으면 그 질문에 다시 답하기
  python study.py web hint <미션>             [힌트 듣기]
  python study.py web skip <미션>             [이 단계 건너뛰기] 목표 시간이 지난 뒤
  python study.py web finish <미션>           [실전 끝내기] 해설, 모범 답안 비교, 스스로 점검
  python study.py web dev <미션>              [화면 띄우기] 미션 폴더에서 화면 서버 띄우기, Ctrl+C 로 끄기
  python study.py web test <미션>             [테스트 돌리기] 미션 폴더에서 npm test 와 같은 테스트 돌리기
  python study.py web show <페이지>           학습 페이지 읽기
  python study.py web drill [<사슬>]          꼬리 질문 사슬 풀기 (사슬을 비우면 오늘 복습의 첫 사슬)

--user <ID> 로 다른 ID 의 기록을 씁니다. 기본은 .study_user 나 STUDY_USER 의 ID 입니다.
"""


def _secs(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    return "%d:%02d" % (seconds // 60, seconds % 60)


def _marks(text, total):
    """"1 3" 같은 입력을 항목마다 0/1 로. 번호가 아닌 글자는 무시함."""
    marks = [0] * total
    for token in (text or "").replace(",", " ").split():
        if token.isdigit() and 1 <= int(token) <= total:
            marks[int(token) - 1] = 1
    return marks


def _yes(text):
    return (text or "").strip().lower() in ("y", "yes", "네", "예", "ㅇ")


PIPE_WAIT_S = 60  # 터미널이 아닌 입력에서 한 줄을 기다리는 최대 초. 통과 뒤 질문의 답 시간(30초)에 여유를 더함


class PipeAsk(object):
    """터미널이 아닌 표준 입력에서 한 줄씩 읽는 ask. 줄이 wait 초 안에 오지 않거나 입력이 끝나면 EOFError 이고, 그 뒤로는 바로 EOFError.
    읽기는 데몬 스레드가 os.read 로 함. 파이썬의 입력 잠금을 쥐지 않으므로 기다리던 스레드가 남아도 프로그램이 끝날 때 걸리지 않음."""

    def __init__(self, fd, out, wait=PIPE_WAIT_S, encoding="utf-8"):
        self.fd, self.out, self.wait, self.encoding = fd, out, wait, encoding
        self.lines = queue.Queue()
        self.thread = None
        self.closed = False

    def _pump(self):
        rest = b""
        while True:
            try:
                chunk = os.read(self.fd, 4096)
            except OSError:
                chunk = b""
            if not chunk:
                if rest:
                    self.lines.put(rest)
                self.lines.put(None)
                return
            rest += chunk
            while b"\n" in rest:
                line, rest = rest.split(b"\n", 1)
                self.lines.put(line)

    def __call__(self, prompt):
        self.out(prompt)
        if self.closed:
            raise EOFError
        if self.thread is None:
            self.thread = threading.Thread(target=self._pump, daemon=True)
            self.thread.start()
        try:
            line = self.lines.get(timeout=self.wait)
        except queue.Empty:
            line = None
        if line is None:
            self.closed = True
            raise EOFError
        return line.decode(self.encoding, "replace").rstrip("\r")


def default_ask(out):
    """표준 입력이 터미널이면 input, 아니면 PipeAsk. 표준 입력이 없으면(pythonw) 묻는 즉시 EOFError."""
    stdin = sys.stdin
    try:
        if stdin is None:
            raise ValueError
        if stdin.isatty():
            return input
        return PipeAsk(stdin.fileno(), out, encoding=stdin.encoding or "utf-8")
    except (ValueError, OSError, AttributeError):
        def closed(prompt):
            out(prompt)
            raise EOFError
        return closed


class Cli:
    def __init__(self, out, ask, clock):
        self.out = out
        self.ask = ask
        self.clock = clock

    def say(self, text=""):
        self.out(text)

    def timed_ask(self, prompt):
        """묻고 (답, 걸린 초)."""
        started = self.clock()
        answer = self.ask(prompt)
        return answer, int(self.clock() - started)

    # 현황

    def status(self, web):
        view = web.overview()
        stack = view["stack"]
        node = stack["node"]
        self.say("Node.js %s" % node["version"] if node else "Node.js 없음")
        if stack["installed"]:
            note = " · 설치 표시 없음" if stack["no_marker"] else (" · 패키지 목록이 바뀜" if stack["stale"] else "")
            self.say("검사 도구 설치됨 (%s)%s" % (stack["dir"], note))
        if stack["problem"]:
            self.say(stack["problem"])
        self.say()
        self.say("라이브 코딩 미션")
        for row in view["missions"]:
            if not row["ready"]:
                state = "준비 중" if not row["error"] else "읽을 수 없음: " + row["error"]
            elif row["phase"] == "live":
                state = "실전 %s / %d:00, %d단계" % (_secs(row["timers"]["live_elapsed"]), row["live_min"], row["current"])
            elif row["phase"] == "done":
                state = "끝남 %d/%d" % (row["done_steps"], max(0, row["total_steps"] - 1))
            else:
                state = row["phase_label"]
            self.say("  %-4s %-24s %s" % (row["id"], row["title"], state))
        self.say()
        self.say("꼬리 질문 주제")
        for row in view["topics"]:
            if not row["ready"]:
                self.say("  %-4s %-24s %s" % (row["id"], row["title"], "준비 중" if not row["error"] else "읽을 수 없음: " + row["error"]))
                continue
            self.say("  %-4s %-24s %d/%d" % (row["id"], row["title"], row["done"], row["total"]))
            for chain in row["chains"]:
                plan = "새 사슬" if chain["box"] is None else "상자 %d, 다음 복습 %s" % (chain["box"], chain["due"])
                self.say("       %-6s %-28s %s" % (chain["id"], chain["title"], plan))
        self.say()
        self.say("학습 노트")
        for row in view["pages"]:
            mark = "읽음 %s" % row["learned_at"][:10] if row["learned_at"] else ("" if row["ready"] else "준비 중")
            self.say(("  %-4s %-40s %s" % (row["id"], row["title"], mark)).rstrip())
        self.say()
        today = view["today"]
        self.say("오늘 복습 (약 %d분)" % today["minutes"])
        for row in today["chains"]:
            self.say("  %-6s %-28s %s" % (row["chain"], row["title"], "새 사슬" if row["new"] else "상자 %d" % row["box"]))
        for row in today["missions"]:
            self.say("  %-6s %-28s 다시 해 볼 미션: %s" % (row["mission"], row["title"], row["why"]))
        if not today["chains"] and not today["missions"]:
            self.say("  없음")
        if view["next"]:
            self.say("다음 추천: %s %s" % (view["next"]["id"], view["next"]["title"]))
        if view["stuck"]:
            self.say("막힌 질문에서 아는 데까지 말한 비율 %d / %d" % (view["talked"], view["stuck"]))
        for line in view["bank_errors"]:
            self.say("은행 오류: " + line)
        return 0

    def install(self, web, yes):
        self.say(web.consent())
        self.say()
        if not yes and not _yes(self.ask("설치할까요? (y/n) ")):
            self.say("설치하지 않았습니다.")
            return 1
        result = web.install(report=self.say)
        self.say(result["message"])
        return 0

    def uninstall(self, web):
        result = web.uninstall()
        self.say("지웠습니다: %s" % ", ".join(result["removed"]) if result["removed"] else "지울 것이 없습니다.")
        return 0

    # 미션

    def _request(self, step):
        self.say("%d단계. %s (목표 %d분)" % (step["no"], step["title"], step["target_min"]))
        self.say(step["request"])
        if step["note"]:
            self.say()
            self.say(step["note"])
        if step["checks"]:
            self.say()
            self.say("검사는 아래 내용을 확인합니다.")
            for line in step["checks"]:
                self.say("- " + line)
        if step["self"]:  # 자동 검사가 없는 단계. 요구 글이 '아래 항목'이라고 가리키므로 여기서 항목을 보여 줌
            self.say()
            for i, text in enumerate(step["self"], 1):
                self.say("%d. %s" % (i, text))
            self.say("설명을 마치면 `check` 로 말한 것에 표시하세요.")
        for text in step["hints"]:
            self.say("면접관 힌트: " + text)

    def _after_step(self, web, mid, result):
        if result.get("finished"):
            self.say()
            self.say("모든 단계를 끝냈습니다. `python study.py web finish %s` 로 해설을 보세요." % mid)
        elif result.get("next"):
            self.say()
            self._request(result["next"])

    def get(self, web, mid, again):
        try:
            view = web.get(mid, again)
        except service.AlreadyReceived as error:
            raise WebError("%s 처음부터 다시 하려면 --again 을 붙이세요." % error)
        self.say("과제를 받았습니다: %s" % study.shown_path(view["dir"]))
        self.say("읽기 시간 %d분이 시작되었습니다. 읽기 안내를 읽고 준비되면 `python study.py web start %s` 를 실행하세요."
                 % (view["prep_min"], mid))
        self.say()
        self.say(view["brief"])
        return 0

    def start(self, web, mid, no_ai):
        if no_ai is None:
            no_ai = _yes(self.ask("에디터의 AI 자동완성을 껐나요? (y/n) "))
        view = web.start(mid, no_ai)
        self.say("실전 시간 %d분이 시작되었습니다." % view["live_min"])
        self.say()
        self._request(view["current"])
        return 0

    def _ask_items(self, items, prompt):
        for n, item in enumerate(items, 1):
            label = ("[필수] " if item.get("need") else "[보충] ") if "need" in item else ""
            self.say("  %d. %s%s" % (n, label, item["text"] if isinstance(item, dict) else item))
        return _marks(self.ask(prompt), len(items))

    def _after_question(self, web, mid, after, head=True):
        """통과 뒤 질문을 묻고 표시한 항목을 기록함. 답을 받지 못하면(입력 끝, 시간 넘김, Ctrl+C) 기록하지 않고 나중에 답하는 법을
        알린 뒤 돌아감. 부른 쪽은 그다음 단계 요구를 이어서 보임. 기록했으면 True."""
        self.say()
        if head:
            self.say("통과하면 면접관이 이어서 묻습니다. %d초 안에 소리 내어 답하세요." % after["secs"])
        else:
            self.say("%d단계를 통과한 뒤의 질문입니다. %d초 안에 소리 내어 답하세요." % (after["step"], after["secs"]))
        self.say(after["ask"])
        try:
            _, secs = self.timed_ask("답한 뒤 Enter 를 누르세요. ")
            self.say("답 시간: %s" % self._time_note(secs, after["secs"]))
            marks = self._ask_items(after["items"], "말한 항목 번호를 띄어쓰기로 적으세요(없으면 Enter): ")
        except (EOFError, KeyboardInterrupt):
            self.say()
            self.say("답을 받지 못해 이 질문은 기록하지 않았습니다. 나중에 `python study.py web answer %s` 로 답할 수 있습니다." % mid)
            return False
        self._record_after(web, mid, after, marks, secs)
        return True

    def _record_after(self, web, mid, after, marks, secs):
        need = [m for m, item in zip(marks, after["items"]) if item["need"]]
        extra = [m for m, item in zip(marks, after["items"]) if not item["need"]]
        result = web.after_answer(mid, after["step"], need, extra, secs)
        self.say("판정: %s" % service.RESULT_LABEL[result["result"]])

    def _time_note(self, secs, limit):
        if secs <= limit:
            return "%d초 (%d초 안)" % (secs, limit)
        return "%d초 (%d초 넘김)" % (secs, secs - limit)

    def check(self, web, mid, said):
        view = web.mission(mid)
        if view["phase"] != "live":
            raise WebError("실전 중이 아닙니다(지금 %s)." % view["phase_label"])
        if view["current"] and view["current"]["no"] == 0:
            step = view["current"]
            self.say("0단계에는 자동 검사가 없습니다. 아래 항목 가운데 말한 것에 표시하세요.")
            if said is None:
                marks = self._ask_items([{"text": t} for t in step["self"]], "말한 항목 번호를 띄어쓰기로 적으세요(없으면 Enter): ")
            else:
                marks = _marks(said, len(step["self"]))
            result = web.explain_done(mid, marks)
            self.say("0단계를 끝냈습니다.")
            self._after_step(web, mid, result)
            return 0
        result = web.check(mid)
        for line in result["warnings"]:
            self.say("주의: " + line)
        for test in result["tests"]:
            mark = "통과" if test["status"] == "pass" else "실패"
            self.say("%-3s %s  %s" % (test["id"], mark, test["title"]))
            if test["status"] != "pass" and test["message"]:
                self.say(study.indent(test["message"]))
        self.say("검사 %d개 가운데 %d개 통과 (%.1f초)" % (len(result["tests"]), len(result["pass"]), result["ms"] / 1000.0))
        if result["broken"]:
            self.say("앞 단계 검사가 깨졌습니다: %s단계" % ", ".join(str(k) for k in result["broken"]))
        if result["passed"]:
            self.say("%d단계를 통과했습니다." % result["open"])
            if result["after"]:
                self._after_question(web, mid, result["after"])
            self._after_step(web, mid, result)
        else:
            self.say("%d단계 검사가 아직 통과하지 않았습니다. 고친 뒤 다시 `check` 하세요." % result["open"])
        return 0

    def answer(self, web, mid, said):
        """답하지 못하고 넘어간 통과 뒤 질문에 답함. said 를 주면 묻지 않고 첫 질문에 그 번호를 표시함(답 시간은 남기지 않음)."""
        pending = web.pending_after(mid)
        if not pending:
            self.say("답하지 않은 통과 뒤 질문이 없습니다.")
            return 0
        if said is not None:
            after = pending[0]
            self.say("%d단계를 통과한 뒤의 질문입니다." % after["step"])
            self.say(after["ask"])
            self._record_after(web, mid, after, _marks(said, len(after["items"])), None)
            return 0
        for after in pending:
            if not self._after_question(web, mid, after, head=False):
                return 1
        return 0

    def hint(self, web, mid):
        result = web.hint(mid)
        self.say("면접관 힌트 %d: %s" % (result["n"], result["text"]))
        if result["left"]:
            self.say("힌트가 %d개 더 있습니다." % result["left"])
        return 0

    def skip(self, web, mid):
        result = web.skip(mid)
        self.say("%d단계를 넘어갔습니다. 기록에 남습니다." % result["skipped"])
        self._after_step(web, mid, result)
        return 0

    def finish(self, web, mid, self_marks):
        result = web.finish(mid)
        timers = result["timers"]
        self.say("%s %s 끝남 (%d번째 시도). 실전 %s%s" % (mid, result["title"], result["try"], _secs(timers["live_elapsed"]),
                                                   ", %s 넘김" % _secs(timers["live_over"]) if timers["live_over"] else ""))
        for row in result["steps"]:
            self.say("  %d단계 %-20s %s%s" % (row["no"], row["title"], row["label"], " (힌트 %d)" % row["hints"] if row["hints"] else ""))
        if result["hidden"]:
            if "error" in result["hidden"]:
                self.say("숨긴 검사를 돌리지 못했습니다: %s" % result["hidden"]["error"])
            else:
                self.say("숨긴 검사: 통과 %d, 실패 %d" % (len(result["hidden"]["pass"]), len(result["hidden"]["fail"])))
        self.say()
        self.say(result["explain"])
        self.say()
        self.say("내 코드와 모범 답안의 차이")
        if not result["mine_diff"]:
            self.say("  (같습니다)")
        for row in result["mine_diff"]:
            self.say(row["diff"])
        self.say()
        self.say("템플릿에서 모범 답안까지 바뀐 파일: %s" % (", ".join(r["file"] for r in result["template_diff"]) or "없음"))
        if result["self_items"]:
            self.say()
            self.say("스스로 점검. 해당하는 항목에 표시하세요.")
            if self_marks is None:
                marks = self._ask_items([{"text": i["text"]} for i in result["self_items"]], "해당 항목 번호를 띄어쓰기로 적으세요(없으면 Enter): ")
            else:
                marks = _marks(self_marks, len(result["self_items"]))
                for n, (item, mark) in enumerate(zip(result["self_items"], marks), 1):
                    self.say("  %d. [%s] %s" % (n, "v" if mark else " ", item["text"]))
            web.self_check(mid, {item["key"]: m for item, m in zip(result["self_items"], marks)})
        if result["followups"]:
            self.say()
            self.say("꼬리 질문: `python study.py web drill %s`" % result["followups"])
        if result["pages"]:
            self.say("학습 페이지: %s" % ", ".join("`python study.py web show %s`" % p for p in result["pages"]))
        return 0

    def dev(self, web, mid):
        """화면 서버를 띄우고 Ctrl+C 까지 기다림. 브라우저는 열지 않고 주소만 알림. 터미널 창을 닫아도 서버를 끊음."""
        dev.stop_on_hangup()
        info = web.serve(mid)
        self.say("화면을 띄웠습니다: %s" % info["url"])
        self.say("브라우저에서 이 주소를 여세요. 코드를 저장하면 화면이 바로 바뀝니다. 끄려면 Ctrl+C 를 누르세요.")
        try:
            while web.serving()["running"]:
                time.sleep(0.5)
            self.say("화면 서버가 멈췄습니다.")
            self.say(web.server.tail())
            return 1
        except KeyboardInterrupt:
            self.say()
            self.say("화면을 껐습니다.")
            return 0
        finally:
            web.stop_serving()

    def test(self, web, mid):
        dev.stop_on_hangup()
        result = web.own_tests(mid)
        for fail in result["fails"]:
            self.say(dev.failure_text(fail))
            self.say()
        self.say(dev.summary(result))
        return 0 if result["ok"] else 1

    def show(self, web, pid):
        page = web.show(pid)
        self.say(page["text"])
        return 0

    # 드릴

    def drill(self, web, cid):
        if not cid:
            today = web.today_list()
            if not today["chains"]:
                self.say("오늘 복습할 사슬이 없습니다. `python study.py web status` 에서 사슬 id 를 골라 `drill <사슬>` 로 풀 수 있습니다.")
                return 0
            cid = today["chains"][0]["chain"]
        chain = web.chain(cid)
        self.say("사슬 %s. %s" % (chain["id"], chain["title"]))
        if chain["goal"]:
            self.say(chain["goal"])
        if chain["box"]:
            self.say("상자 %d, %d번째 복습" % (chain["box"], chain["times"] + 1))
        self.say()
        if chain["intro"]:
            self.say(chain["intro"])
        if chain["code"]:
            self.say()
            self.say(chain["code"])
        for question in chain["questions"]:
            self.say()
            self.say("Q%d. %s" % (question["no"], question["ask"]))
            answer, secs = self.timed_ask("%d초 안에 소리 내어 답한 뒤 Enter 를 누르세요. 모르겠으면 m 을 치고 Enter: " % chain["secs"])
            self.say("답 시간: %s" % self._time_note(secs, chain["secs"]))
            gave_up = (answer or "").strip().lower() in ("m", "모르겠어요")
            self.say("짚을 내용입니다. 말한 항목에 표시하세요.")
            if question["last"]:
                self.say("(지난 답: %s)" % (question["last"]["note"] or "적은 내용 없음"))
            marks = [0] * len(question["items"])
            if gave_up:
                for n, item in enumerate(question["items"], 1):
                    self.say("  %d. %s%s" % (n, "[필수] " if item["need"] else "[보충] ", item["text"]))
            else:
                marks = self._ask_items(question["items"], "말한 항목 번호를 띄어쓰기로 적으세요(없으면 Enter): ")
            need = [m for m, item in zip(marks, question["items"]) if item["need"]]
            extra = [m for m, item in zip(marks, question["items"]) if not item["need"]]
            talked = None
            if not all(need):
                if question["stuck"]:
                    self.say("막히면: " + question["stuck"])
                talked = _yes(self.ask("막힌 곳에서 아는 데까지 말했나요? (y/n) "))
            note = self.ask("말한 내용을 한두 줄 적어 두려면 적고, 아니면 Enter: ")
            result = web.answer(cid, question["no"], secs, need, extra, talked, note)
            self.say("판정: %s" % result["label"])
        done = web.finish_chain(cid)
        self.say()
        if done["weak"]:
            self.say("약한 답")
            self.say("> " + done["weak"]["quote"])
            if done["weak"]["why"]:
                self.say(done["weak"]["why"])
        if done["follow"]:
            self.say()
            self.say("이어 말하기")
            self.say("> " + done["follow"])
        self.say()
        self.say("사슬 결과: %s (질문별 %s)" % (done["label"], ", ".join(service.RESULT_LABEL[r] for r in done["per_question"])))
        self.say("상자 %d, 다음 복습 %s" % (done["box"], done["due"]))
        if done["page"]:
            self.say("학습 페이지: `python study.py web show %s`%s" % (done["page"], " (%s 절)" % done["section"] if done["section"] else ""))
        return 0


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--user", default=argparse.SUPPRESS, help="다른 ID 의 기록을 씁니다")  # 하위 명령의 기본값이 앞의 값을 덮지 않게 함
    parser = argparse.ArgumentParser(prog="study.py web", description=USAGE, parents=[common],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", parents=[common])
    p = sub.add_parser("install", parents=[common])
    p.add_argument("--yes", action="store_true")
    sub.add_parser("uninstall", parents=[common])
    p = sub.add_parser("get", parents=[common])
    p.add_argument("mission")
    p.add_argument("--again", action="store_true")
    p = sub.add_parser("start", parents=[common])
    p.add_argument("mission")
    p.add_argument("--no-ai", dest="no_ai", choices=("yes", "no"))
    p = sub.add_parser("check", parents=[common])
    p.add_argument("mission")
    p.add_argument("--said", help="0단계 점검 항목 가운데 말한 번호 (예: 1,3)")
    p = sub.add_parser("answer", parents=[common])
    p.add_argument("mission")
    p.add_argument("--said", help="통과 뒤 질문의 짚을 내용 가운데 말한 번호 (예: 1,2)")
    for name in ("hint", "skip", "dev", "test"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("mission")
    p = sub.add_parser("finish", parents=[common])
    p.add_argument("mission")
    p.add_argument("--self", dest="self_marks", help="스스로 점검에 표시할 번호 (예: 1,2,5)")
    p = sub.add_parser("show", parents=[common])
    p.add_argument("page")
    p = sub.add_parser("drill", parents=[common])
    p.add_argument("chain", nargs="?")
    return parser


def resolve_user(name):
    user = name or session.saved_user()
    if not user:
        raise WebError("내 ID 를 모릅니다. `python study.py init <내 깃허브 ID>` 로 풀이 폴더를 먼저 만들거나 --user 를 적어 주세요.")
    if not session.valid_user(user):
        raise WebError("ID 는 영문·숫자·-·_ 만 쓸 수 있습니다: %r" % (user,))
    return session.user_folder(user)


def main(argv=None, out=None, ask=None, clock=None, repo=None, home=None):
    """명령을 실행하고 종료 코드를 돌려줌. out·ask·clock 은 테스트가 바꿔 끼움."""
    argv = sys.argv[1:] if argv is None else list(argv)
    out = out or print
    ask = ask or default_ask(out)
    clock = clock or time.monotonic
    if not argv or argv[0] in ("-h", "--help", "help"):
        out(USAGE)
        return 0
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    if not args.command:
        out(USAGE)
        return 2
    cli = Cli(out, ask, clock)
    try:
        web = service.WebSession(resolve_user(getattr(args, "user", None)), repo=repo, home=home)
        if args.command == "status":
            return cli.status(web)
        if args.command == "install":
            return cli.install(web, args.yes)
        if args.command == "uninstall":
            return cli.uninstall(web)
        if args.command == "get":
            return cli.get(web, args.mission, args.again)
        if args.command == "start":
            return cli.start(web, args.mission, None if args.no_ai is None else args.no_ai == "yes")
        if args.command == "check":
            return cli.check(web, args.mission, args.said)
        if args.command == "answer":
            return cli.answer(web, args.mission, args.said)
        if args.command == "hint":
            return cli.hint(web, args.mission)
        if args.command == "skip":
            return cli.skip(web, args.mission)
        if args.command == "finish":
            return cli.finish(web, args.mission, args.self_marks)
        if args.command == "dev":
            return cli.dev(web, args.mission)
        if args.command == "test":
            return cli.test(web, args.mission)
        if args.command == "show":
            return cli.show(web, args.page)
        if args.command == "drill":
            return cli.drill(web, args.chain)
    except WebError as error:
        out("오류: %s" % error)
        return 1
    except (EOFError, KeyboardInterrupt):
        out("")
        out("중단했습니다. 기록은 여기까지 남아 있습니다.")
        return 130
    return 2


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
