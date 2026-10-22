# -*- coding: utf-8 -*-
"""웹 면접 준비 서비스. 화면과 명령은 WebSession 만 부름. 반환은 dict·list, 오류는 사용자에게 그대로 보여 줄 WebError.

기록은 submissions/<ID>/web/record.json 에 덧붙기만 하고, 미션 상태·단계·시계·복습 상자는 기록에서 그때그때 계산함.
local 로 표시한 주제(내 경력 사슬)의 drill·chain 기록은 ~/.rokey-study/web/record.json 에 두어 [제출]에 들어가지 않음.
Node 는 만들 때 찾지 않고 설치 상태나 검사를 물을 때 찾음(journey.node 가 minimum 별로 기억함).
"""
import datetime
import difflib
import os
import shutil
import threading

import adaptive
import session
import study
from webprep import bank, checks, dev, record, review, stack

PHASE_LABEL = {"none": "받기 전", "reading": "읽는 중", "live": "실전 중", "done": "끝남"}
RESULT_LABEL = {"pass": "통과", "partial": "부분", "stuck": "막힘", "done": "끝", "skip": "넘어감"}
AFTER_SECS = 30
HIDDEN_NO_STACK = "Node.js 나 검사 도구가 준비되지 않았습니다."  # 숨긴 검사를 돌리지 못한 까닭. 화면의 해설 탭에도 그대로 보임
MINUTES_PER_QUESTION = 1.5
SKIP_DIRS = ("node_modules", "dist", ".git")
now = adaptive.now  # 테스트가 바꿔 끼움


def today():
    return datetime.date.today()


class WebError(session.SessionError):
    """사용자에게 그대로 보여 줄 수 있는 웹 면접 준비 오류."""


class AlreadyReceived(WebError):
    """받은 코드가 있는 미션을 again 없이 다시 받으려 함. phase 는 기록의 상태(폴더만 남았으면 none). 화면은 이어서 할지 다시 받을지 묻고,
    터미널은 --again 을 안내함."""

    def __init__(self, phase):
        super().__init__("이미 받은 미션입니다(%s). 다시 받으면 지금 코드는 템플릿으로 덮어써집니다." % PHASE_LABEL[phase])
        self.phase = phase


def _seconds(start, end):
    a, b = record.parse_at(start), record.parse_at(end)
    if a is None or b is None:
        return None
    return int((b - a).total_seconds())


def _unified(name, before, after):
    lines = difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=name, tofile=name, lineterm="")
    return "\n".join(lines)


def read_tree(folder):
    """폴더의 글 파일을 {상대 경로: 글} 로. node_modules, dist, .git 은 건너뜀."""
    files = {}
    for here, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            if not name.endswith(bank.TEXT_EXTS):
                continue
            path = os.path.join(here, name)
            try:
                files[os.path.relpath(path, folder).replace(os.sep, "/")] = study.read_text(path)
            except (OSError, UnicodeDecodeError):
                continue
    return files


class WebSession:
    def __init__(self, user, repo=None, home=None, node_path=None):
        """은행과 record.json 을 읽음. index.json 이나 기록이 깨졌으면 WebError."""
        if not session.valid_user(user):
            raise WebError("ID 가 올바르지 않습니다: %r" % (user,))
        self.user = user
        self.repo = repo or study.ROOT
        self.home = home or stack.home_dir()
        self.node_path = node_path or None
        self._lock = threading.RLock()
        self._secrets = {}
        self.server, self.server_mid = None, None  # [화면 띄우기]로 띄운 dev.DevServer 와 그 미션
        self.folder = os.path.join(study.SUBMISSIONS_DIR, user, "web")
        self.root = bank.BANK_DIR
        try:
            self.record = record.Record(os.path.join(self.folder, "record.json"), user)
            self.local = record.Record(os.path.join(self.home, "record.json"), user, "로컬 웹 기록(~/.rokey-study/web/record.json)")
        except record.RecordError as error:
            raise WebError(str(error))
        try:
            self.index = bank.read_index(self.root)
        except bank.BankError as error:
            raise WebError("웹 면접 준비 목록을 읽을 수 없습니다. %s" % error)
        self.missions, self.topics, self.pages = {}, {}, {}
        self.errors, self.bank_errors = {}, []
        loaders = (("mission", self.index["missions"], bank.load_mission, self.missions),
                   ("topic", self.index["topics"], bank.load_topic, self.topics),
                   ("page", self.index["pages"], bank.load_page, self.pages))
        for kind, entries, load, store in loaders:
            for entry in entries:
                if not bank.is_ready(kind, entry["id"], self.root):
                    continue
                try:
                    store[entry["id"]] = load(entry, self.root)
                except bank.BankError as error:
                    self.errors[entry["id"]] = str(error)
                    self.bank_errors.append("%s: %s" % (entry["id"], error))
        self.chains = {}
        for topic in self.topics.values():
            for chain in topic["chains"]:
                self.chains[chain["id"]] = dict(chain, mission=None, local=topic["local"], page=topic["page"])
        for mission in self.missions.values():
            cid = mission["id"] + "-F"
            self.chains.setdefault(cid, {"id": cid, "title": "%s 꼬리 질문" % mission["title"], "goal": "", "secs": 60,
                                         "missions": [mission["id"]], "section": "", "defines_inline": [], "topic": None,
                                         "mission": mission["id"], "local": False,
                                         "page": mission["pages"][0] if mission["pages"] else ""})

    # 은행

    def _entry(self, kind, iid):
        key = {"mission": "missions", "topic": "topics", "page": "pages"}[kind]
        entry = next((e for e in self.index[key] if e["id"] == iid), None)
        if entry is None:
            raise WebError("%s 을 찾을 수 없습니다: %s" % ({"mission": "미션", "topic": "주제", "page": "학습 페이지"}[kind], iid))
        return entry

    def _mission(self, mid):
        self._entry("mission", mid)
        if mid in self.errors:
            raise WebError("미션 %s 을 읽을 수 없습니다. %s" % (mid, self.errors[mid]))
        if mid not in self.missions:
            raise WebError("아직 출제되지 않은 미션입니다: %s" % mid)
        return self.missions[mid]

    def _page(self, pid):
        self._entry("page", pid)
        if pid in self.errors:
            raise WebError("학습 페이지 %s 을 읽을 수 없습니다. %s" % (pid, self.errors[pid]))
        if pid not in self.pages:
            raise WebError("아직 준비되지 않은 학습 페이지입니다: %s" % pid)
        return self.pages[pid]

    def _secrets_of(self, kind, iid):
        with self._lock:
            key = (kind, iid)
            if key not in self._secrets:
                folder = self._mission(iid)["dir"] if kind == "mission" else self.topics[iid]["dir"]
                try:
                    self._secrets[key] = bank.load_secrets(folder)
                except bank.BankError as error:
                    raise WebError("%s 의 봉인 파일을 풀 수 없습니다. %s" % (iid, error))
            return self._secrets[key]

    def _steps(self, mid):
        text = self._secrets_of("mission", mid).get("steps.md")
        if text is None:
            raise WebError("미션 %s 의 단계 파일(steps.md)이 봉인 안에 없습니다." % mid)
        steps = bank.parse_steps(text)
        mission = self._mission(mid)
        if [s["no"] for s in steps] != list(range(len(mission["steps"]))):
            raise WebError("미션 %s 의 steps.md 단계 번호가 meta.json 의 steps 와 맞지 않습니다." % mid)
        return steps

    def _chain_meta(self, cid):
        chain = self.chains.get(cid)
        if chain is None:
            raise WebError("사슬을 찾을 수 없습니다: %s" % cid)
        return chain

    def _locked(self, cid, found=None):
        """미션 꼬리 질문 사슬은 그 미션을 끝내기 전에는 잠김. 모범 답안이 담긴 질문이 실전 전에 보이지 않게 함."""
        mission = self._chain_meta(cid)["mission"]
        return bool(mission) and self._state(mission, found)["phase"] != "done"

    def _chain_content(self, cid):
        meta = self._chain_meta(cid)
        if meta["mission"]:
            if self._locked(cid):
                raise WebError("꼬리 질문은 미션을 끝낸 뒤에 풉니다.")
            text = self._secrets_of("mission", meta["mission"]).get("followups.md")
        else:
            text = self._secrets_of("topic", meta["topic"]).get("chains.md")
        chains = bank.parse_chains(text or "")
        if cid not in chains:
            raise WebError("사슬 %s 의 본문이 봉인 안에 없습니다." % cid)
        content = chains[cid]
        if not content["questions"]:
            raise WebError("사슬 %s 에 질문이 없습니다." % cid)
        return content

    def _rec(self, cid):
        return self.local if self._chain_meta(cid)["local"] else self.record

    def _all_log(self):
        return list(self.record.log) + list(self.local.log)

    # 기록

    def _append(self, entry, rec=None):
        try:
            return (rec or self.record).append(entry, at=now())
        except record.RecordError as error:
            raise WebError(str(error))

    def _states(self):
        self.record.reload()
        return record.mission_states(self.record.log)

    def _state(self, mid, found=None):
        found = self._states() if found is None else found
        return found.get(mid) or record.blank_mission()

    def learner_dir(self, mid):
        return os.path.join(self.folder, "missions", mid)

    # 설치

    def node(self, probe=False):
        return stack.find_node(self.node_path, probe)

    def stack_state(self):
        return stack.state(self.repo, self.node())

    def consent(self):
        return stack.consent_text(self.repo, self.node())

    def install(self, report=None):
        """검사 도구를 설치함. Node 가 없으면 WebError, 실패하면 message 에 이유와 로그 위치."""
        node = self.node()
        if node is None:
            raise WebError(stack.state(self.repo, None)["problem"])
        result = stack.install(self.repo, node, report)
        if not result["ok"]:
            raise WebError(result["message"])
        return dict(result, state=self.stack_state())

    def uninstall(self):
        return stack.uninstall(self.repo)

    def _require_stack(self):
        node = self.node()
        state = stack.state(self.repo, node)
        if node is None or not state["installed"] or not state["lock"]:
            raise WebError(state["problem"])
        return node, state

    # 미션 읽기

    def _timers(self, mission, state, at=None):
        """읽기·실전·단계 시계(초). 넘긴 시간은 over 에 따로 둠."""
        at = at or now()
        out = {"reading_left": None, "live_elapsed": None, "live_over": None, "step_elapsed": None,
               "step_target": None, "step_over": None, "can_skip": False}
        if state["phase"] == "reading" and state["received_at"]:
            out["reading_left"] = mission["prep_min"] * 60 - (_seconds(state["received_at"], at) or 0)
        if state["phase"] in ("live", "done") and state["live_at"]:
            end = state["finished_at"] if state["phase"] == "done" else at
            elapsed = _seconds(state["live_at"], end) or 0
            out["live_elapsed"] = elapsed
            out["live_over"] = max(0, elapsed - mission["live_min"] * 60)
        if state["phase"] == "live" and state["current"] is not None and state["current"] < len(mission["steps"]):
            target = mission["steps"][state["current"]] * 60
            elapsed = _seconds(state["step_open_at"], at) or 0
            out.update(step_elapsed=elapsed, step_target=target, step_over=max(0, elapsed - target), can_skip=elapsed >= target)
        return out

    def _step_view(self, mid, steps, state, k):
        step = steps[k]
        view = {"no": k, "title": step["title"], "request": step["request"], "note": step["note"], "checks": list(step["checks"]),
                "self": list(step["self"]), "target_min": self._mission(mid)["steps"][k], "hint_total": len(step["hints"]),
                "hints": step["hints"][:state["hints"].get(k, 0)], "has_after": step["after"] is not None}
        return view

    def _progress(self, mission, steps, state):
        rows = []
        for k in range(len(mission["steps"])):
            done = state["steps"].get(k)
            opened = state["phase"] == "live" and state["current"] == k
            rows.append({"no": k, "title": steps[k]["title"] if (done or opened or state["phase"] == "done") else "",
                         "result": done["result"] if done else ("open" if opened else "locked"),
                         "label": RESULT_LABEL.get(done["result"], done["result"]) if done else ("진행 중" if opened else "잠김"),
                         "target_min": mission["steps"][k], "hints": state["hints"].get(k, 0)})
        return rows

    def mission(self, mid):
        """미션 화면이 쓰는 모든 것. 요구 글은 실전 중 지금 단계까지만 들어감."""
        mission = self._mission(mid)
        state = self._state(mid)
        steps = self._steps(mid)
        view = {"id": mid, "no": mission["no"], "title": mission["title"], "level": mission["level"],
                "prep_min": mission["prep_min"], "live_min": mission["live_min"], "targets": list(mission["steps"]),
                "phase": state["phase"], "phase_label": PHASE_LABEL[state["phase"]], "try": state["try"],
                "brief": mission["brief"], "dir": self.learner_dir(mid), "pages": list(mission["pages"]),
                "chains": list(mission["chains"]), "timers": self._timers(mission, state), "no_ai": state["no_ai"],
                "steps": self._progress(mission, steps, state), "current": None, "hint_count": state["hint_count"],
                "skips": list(state["skips"]), "last_check": state["last_check"]}
        if state["phase"] == "live" and state["current"] is not None and state["current"] < len(steps):
            view["current"] = self._step_view(mid, steps, state, state["current"])
        return view

    # 미션 쓰기

    def received(self, mid):
        """받은 코드가 있는지. 기록에 받은 것으로 남았거나(진행 중이든 끝났든) 미션 폴더가 남아 있으면 참."""
        return self._state(mid)["phase"] != "none" or os.path.isdir(self.learner_dir(mid))

    def get(self, mid, again=False):
        """[미션 받기]. 템플릿을 submissions/<ID>/web/missions/<id>/ 로 복사하고 receive 를 기록함.
        이미 받은 코드가 있으면(진행 중이든 끝났든) again 일 때만 새 try 로 덮어쓰고, 아니면 AlreadyReceived."""
        mission = self._mission(mid)
        self._steps(mid)
        state = self._state(mid)
        dest = self.learner_dir(mid)
        if self.received(mid) and not again:
            raise AlreadyReceived(state["phase"])
        try:
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            shutil.copytree(mission["app_dir"], dest, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        except OSError as error:
            raise WebError("과제 코드를 복사하지 못했습니다: %s" % error)
        self._append({"kind": "receive", "item": mid, "try": state["try"] + 1})
        return self.mission(mid)

    def resume(self, mid):
        """[이어서 하기]. 폴더에 남은 코드를 그대로 두고 받은 것으로 기록함. 기록에 이미 받은 것으로 남아 있으면 그대로 둠.
        폴더가 없으면 WebError."""
        self._mission(mid)
        self._steps(mid)
        state = self._state(mid)
        if state["phase"] != "none":
            return self.mission(mid)
        if not os.path.isdir(self.learner_dir(mid)):
            raise WebError("미션 폴더가 없습니다: %s. 미션을 받아 주세요." % study.shown_path(self.learner_dir(mid)))
        self._append({"kind": "receive", "item": mid, "try": state["try"] + 1})
        return self.mission(mid)

    def start(self, mid, no_ai=None):
        """[실전 시작]. 읽는 중일 때만. no_ai 는 "에디터의 AI 자동완성을 껐나요?" 의 답(기록만 함)."""
        self._mission(mid)
        state = self._state(mid)
        if state["phase"] != "reading":
            raise WebError("실전은 과제를 받고 읽는 중일 때 시작할 수 있습니다(지금 %s)." % PHASE_LABEL[state["phase"]])
        self._append({"kind": "live", "item": mid, "try": state["try"], "no_ai": None if no_ai is None else bool(no_ai)})
        return self.mission(mid)

    def _live(self, mid):
        state = self._state(mid)
        if state["phase"] != "live":
            raise WebError("실전 중이 아닙니다(지금 %s)." % PHASE_LABEL[state["phase"]])
        return state

    def explain_done(self, mid, said):
        """[설명 끝내기]. 0단계 점검 항목에 표시한 것(0/1 목록)을 기록하고 1단계를 엶."""
        mission = self._mission(mid)
        state = self._live(mid)
        if state["current"] != 0:
            raise WebError("0단계는 이미 끝났습니다(지금 %d단계)." % state["current"])
        steps = self._steps(mid)
        total = len(steps[0]["self"])
        marks = [1 if v else 0 for v in list(said)[:total]] + [0] * max(0, total - len(said))
        self._append({"kind": "step", "item": mid, "try": state["try"], "step": 0, "result": "done", "said": marks})
        return self._after_step(mid, mission, steps, 0)

    def _after_step(self, mid, mission, steps, k):
        """k단계를 끝낸 뒤의 안내. 다음 단계가 있으면 그 요구, 없으면 끝남 기록."""
        if k + 1 >= len(mission["steps"]):
            self._finish_record(mid)
            return {"finished": True, "next": None}
        state = self._state(mid)
        return {"finished": False, "next": self._step_view(mid, steps, state, k + 1)}

    def check(self, mid):
        """[검사하기]. 1~지금 단계의 검사를 모두 돌리고 check 를 기록함. 지금 단계가 모두 통과하면 step 통과를 기록하고
        다음 요구(또는 끝남)와 통과 뒤 질문을 돌려줌. 앞 단계가 깨졌으면 broken 에 적되 진행은 막지 않음."""
        mission = self._mission(mid)
        state = self._live(mid)
        current = state["current"]
        if current == 0:
            raise WebError("0단계(코드 설명)에는 자동 검사가 없습니다. 설명을 마쳤으면 점검 항목에 표시해 주세요.")
        steps = self._steps(mid)
        node, _ = self._require_stack()
        app_src = os.path.join(self.learner_dir(mid), "src")
        if not os.path.isdir(app_src):
            raise WebError("미션 폴더가 없습니다: %s. 과제를 다시 받아 주세요." % study.shown_path(self.learner_dir(mid)))
        try:
            result = checks.run_steps(node["path"], self.repo, mid, self._secrets_of("mission", mid), bank.kit_files(self.root),
                                      list(range(1, current + 1)), app_src)
        except checks.CheckError as error:
            raise WebError(str(error))
        self._append({"kind": "check", "item": mid, "try": state["try"], "open": current, "pass": result["pass"],
                      "fail": result["fail"], "ms": result["ms"]})
        passed = result["by_step"].get(current, {}).get("ok", False)
        out = {"open": current, "tests": result["tests"], "pass": result["pass"], "fail": result["fail"], "ms": result["ms"],
               "warnings": result["warnings"], "passed": passed, "after": None, "finished": False, "next": None,
               "broken": [k for k in range(1, current) if not result["by_step"].get(k, {}).get("ok", False)]}
        if passed:
            self._append({"kind": "step", "item": mid, "try": state["try"], "step": current, "result": "pass"})
            after = steps[current]["after"]
            if after:
                out["after"] = dict(after, step=current, secs=AFTER_SECS)
            out.update(self._after_step(mid, mission, steps, current))
        return out

    def after_answer(self, mid, step, need, extra, secs):
        """통과 뒤 질문에 표시한 것을 기록함. need·extra 는 [필수]·[보충] 항목마다 0/1. secs 는 답 시간(초)이고, 나중에 번호만
        적어 기록하면 None."""
        self._mission(mid)
        state = self._state(mid)
        if state["phase"] not in ("live", "done"):
            raise WebError("실전 중이나 끝난 미션에만 기록할 수 있습니다.")
        self._append({"kind": "after", "item": mid, "try": state["try"], "step": int(step), "secs": None if secs is None else int(secs),
                      "need": [1 if v else 0 for v in need], "extra": [1 if v else 0 for v in extra]})
        return {"result": review.question_result(need)}

    def pending_after(self, mid):
        """이번 시도에서 통과했지만 답을 기록하지 않은 통과 뒤 질문을 단계 순서대로. 항목 꼴은 check() 의 after 와 같음.
        실전 전이면 빈 목록."""
        self._mission(mid)
        state = self._state(mid)
        if state["phase"] not in ("live", "done"):
            return []
        steps = self._steps(mid)
        return [dict(steps[k]["after"], step=k, secs=AFTER_SECS) for k in sorted(state["steps"])
                if k < len(steps) and state["steps"][k]["result"] == "pass" and steps[k]["after"] and k not in state["after"]]

    def hint(self, mid):
        """[힌트 듣기]. 지금 단계의 다음 힌트를 열고 기록함. {"n", "text", "left"}."""
        self._mission(mid)
        state = self._live(mid)
        steps = self._steps(mid)
        hints = steps[state["current"]]["hints"]
        n = state["hints"].get(state["current"], 0)
        if not hints:
            raise WebError("이 단계에는 힌트가 없습니다.")
        if n >= len(hints):
            raise WebError("이 단계의 힌트를 모두 들었습니다.")
        self._append({"kind": "hint", "item": mid, "try": state["try"], "step": state["current"], "n": n + 1})
        return {"n": n + 1, "text": hints[n], "left": len(hints) - n - 1}

    def skip(self, mid):
        """[이 단계 건너뛰기]. 목표 시간이 지난 뒤에만. skip 을 기록하고 다음 요구(또는 끝남)를 돌려줌."""
        mission = self._mission(mid)
        state = self._live(mid)
        if state["current"] == 0:
            raise WebError("0단계는 설명을 마치고 점검 항목에 표시하면 넘어갑니다.")
        timers = self._timers(mission, state)
        if not timers["can_skip"]:
            left = (timers["step_target"] - timers["step_elapsed"] + 59) // 60
            raise WebError("목표 시간 %d분이 지나야 넘어갈 수 있습니다(%d분 남음)." % (mission["steps"][state["current"]], left))
        steps = self._steps(mid)
        self._append({"kind": "skip", "item": mid, "try": state["try"], "step": state["current"]})
        return dict(self._after_step(mid, mission, steps, state["current"]), skipped=state["current"])

    def _finish_record(self, mid):
        """끝남 기록. 숨긴 검사가 있으면 이때 한 번 돌림(실패해도 끝남은 기록함). 돌리지 못한 까닭은 기록에 남고 화면과 터미널이
        같이 보이므로, 터미널 명령이 든 설치 안내 대신 HIDDEN_NO_STACK 을 남김."""
        mission = self._mission(mid)
        state = self._state(mid)
        hidden = None
        secrets = self._secrets_of("mission", mid)
        if mission["hidden"] and "hidden" in bank.check_files(secrets):
            try:
                node, _ = self._require_stack()
                result = checks.run_steps(node["path"], self.repo, mid, secrets, bank.kit_files(self.root), [],
                                          os.path.join(self.learner_dir(mid), "src"), hidden=True)
                hidden = {"pass": result["pass"], "fail": result["fail"]}
            except WebError:
                hidden = {"error": HIDDEN_NO_STACK}
            except checks.CheckError as error:
                hidden = {"error": str(error)}
        self._append({"kind": "finish", "item": mid, "try": state["try"], "hidden": hidden})

    def finish(self, mid):
        """[실전 끝내기]. 실전 중이면 끝남을 기록하고, 해설·모범 답안 비교·꼬리 질문·점검 항목을 돌려줌. 끝난 미션은 기록
        없이 같은 것을 돌려줌."""
        mission = self._mission(mid)
        state = self._state(mid)
        if state["phase"] == "live":
            self._finish_record(mid)
            state = self._state(mid)
        elif state["phase"] != "done":
            raise WebError("실전을 시작한 뒤에 끝낼 수 있습니다(지금 %s)." % PHASE_LABEL[state["phase"]])
        secrets = self._secrets_of("mission", mid)
        steps = self._steps(mid)
        template = read_tree(mission["app_dir"])
        model = dict(template)
        model.update(bank.solution_files(secrets, len(mission["steps"]) - 1))
        mine = read_tree(self.learner_dir(mid)) if os.path.isdir(self.learner_dir(mid)) else {}
        template_diff, mine_diff = [], []
        for name in sorted(set(template) | set(model)):
            if template.get(name, "") != model.get(name, ""):
                template_diff.append({"file": name, "diff": _unified(name, template.get(name, ""), model.get(name, ""))})
        for name in sorted(set(mine) | set(model)):
            if mine.get(name, "") != model.get(name, ""):
                mine_diff.append({"file": name, "diff": _unified(name, mine.get(name, ""), model.get(name, ""))})
        cid = mid + "-F"
        followups = None
        if "followups.md" in secrets and cid in bank.parse_chains(secrets["followups.md"]):
            followups = cid
        self_items = [{"key": "c%d" % (n + 1), "text": t} for n, t in enumerate(bank.self_check(self.root))]
        self_items += [{"key": "m%d" % (n + 1), "text": t} for n, t in enumerate(bank.parse_bullets(secrets.get("check.md", "")))]
        return {"id": mid, "title": mission["title"], "explain": secrets.get("explain.md", ""), "hidden": state["hidden"],
                "template_diff": template_diff, "mine_diff": mine_diff, "followups": followups, "self_items": self_items,
                "self_ticks": state["self"], "timers": self._timers(mission, state), "steps": self._progress(mission, steps, state),
                "pages": list(mission["pages"]), "chains": list(mission["chains"]), "try": state["try"]}

    def self_check(self, mid, ticks):
        """스스로 점검에 표시한 것 {"c1": 1, "m1": 0} 을 기록함. 끝난 미션에만."""
        self._mission(mid)
        state = self._state(mid)
        if state["phase"] != "done":
            raise WebError("스스로 점검은 미션을 끝낸 뒤에 표시합니다.")
        clean = {str(k): (1 if v else 0) for k, v in dict(ticks).items()}
        self._append({"kind": "self", "item": mid, "try": state["try"], "ticks": clean})
        return clean

    # 화면 띄우기 · 내 테스트

    def _received(self, mid):
        """받은 미션 폴더. 아직 받지 않았으면 WebError."""
        self._mission(mid)
        folder = self.learner_dir(mid)
        if not os.path.isfile(os.path.join(folder, "package.json")):
            raise WebError("미션 폴더가 없습니다: %s. 과제를 먼저 받아 주세요." % study.shown_path(folder))
        return folder

    def serve(self, mid):
        """[화면 띄우기]. 미션 폴더에서 vite 개발 서버를 띄우고 {"mid", "url"} 을 돌려줌. 켜 둔 서버가 있으면 먼저 끔."""
        folder = self._received(mid)
        node, _ = self._require_stack()
        self.stop_serving()
        server = dev.DevServer(node["path"], self.repo, folder)
        try:
            url = server.start()
        except dev.DevError as error:
            raise WebError(str(error))
        self.server, self.server_mid = server, mid
        return {"mid": mid, "url": url}

    def stop_serving(self, wait=True):
        """켜 둔 화면 서버를 끔. 없으면 아무것도 하지 않음. wait 가 거짓이면 끊기를 기다리지 않음(dev.DevServer.stop)."""
        if self.server is not None:
            self.server.stop(wait)
            self.server, self.server_mid = None, None

    def serving(self):
        """켜 둔 화면 서버 {"mid", "url", "running"}. 없으면 None. running 이 거짓이면 서버가 스스로 멈춘 것이고, 마지막 출력은
        self.server.tail() 로 읽음. 화면이 1초마다 부르므로 출력을 기다리지 않음."""
        server = self.server
        if server is None:
            return None
        return {"mid": self.server_mid, "url": server.url, "running": server.running}

    def own_tests(self, mid, cancel=None):
        """[테스트 돌리기]. 미션 폴더의 내 테스트를 npm test 처럼 돌리고 dev.run_tests 의 값을 돌려줌. 기록하지 않음.
        cancel(threading.Event)이 서면 vitest 를 끊고 None."""
        folder = self._received(mid)
        node, _ = self._require_stack()
        try:
            return dev.run_tests(node["path"], self.repo, folder, cancel=cancel)
        except dev.DevError as error:
            raise WebError(str(error))

    # 학습 페이지

    def show(self, pid):
        """학습 페이지 글. learn 을 기록함. text 는 figure 블록을 캡션 한 줄로 바꾼 터미널용 글."""
        page = self._page(pid)
        self._append({"kind": "learn", "page": pid})
        return {"id": pid, "title": page["title"], "markdown": page["markdown"], "text": bank.strip_figures(page["markdown"]),
                "sections": dict(page["sections"]), "dir": page["dir"]}

    # 드릴

    def _schedules(self):
        results = record.chain_results(self._all_log())
        return {cid: review.schedule(items) for cid, items in results.items() if cid in self.chains}

    def chain(self, cid):
        """드릴 화면이 쓰는 사슬 하나. 질문마다 지난 답(last)이 붙음."""
        meta = self._chain_meta(cid)
        content = self._chain_content(cid)
        rec = self._rec(cid)
        rec.reload()
        last = record.last_answers(rec.log, cid)
        questions = []
        for q in content["questions"]:
            row = dict(q, last=None)
            if q["no"] in last:
                entry = last[q["no"]]
                row["last"] = {"need": list(entry.get("need") or []), "extra": list(entry.get("extra") or []),
                               "note": entry.get("note") or "", "secs": entry.get("secs"), "at": entry.get("at")}
            questions.append(row)
        plan = self._schedules().get(cid)
        return {"id": cid, "title": meta["title"], "goal": meta["goal"], "secs": meta["secs"], "topic": meta["topic"],
                "mission": meta["mission"], "page": meta["page"], "section": meta["section"], "local": meta["local"],
                "intro": content["intro"], "code": content["code"], "questions": questions, "weak": content["weak"],
                "follow": content["follow"], "box": plan["box"] if plan else None, "due": plan["due"].isoformat() if plan else None,
                "times": plan["times"] if plan else 0}

    def answer(self, cid, q, secs, need, extra, talked=None, note=""):
        """질문 하나의 답 표시를 기록함. need·extra 는 [필수]·[보충] 항목마다 0/1, talked 는 [필수]를 빠뜨렸을 때만 0/1."""
        content = self._chain_content(cid)
        question = next((item for item in content["questions"] if item["no"] == int(q)), None)
        if question is None:
            raise WebError("사슬 %s 에 Q%s 가 없습니다." % (cid, q))
        needs = [i for i in question["items"] if i["need"]]
        extras = [i for i in question["items"] if not i["need"]]
        need = ([1 if v else 0 for v in list(need)[:len(needs)]] + [0] * len(needs))[:len(needs)]
        extra = ([1 if v else 0 for v in list(extra)[:len(extras)]] + [0] * len(extras))[:len(extras)]
        result = review.question_result(need)
        entry = {"kind": "drill", "chain": cid, "q": int(q), "secs": int(secs), "need": need, "extra": extra,
                 "talked": (None if result == "pass" or talked is None else (1 if talked else 0)), "note": record.clip_note(note)}
        self._append(entry, self._rec(cid))
        return {"result": result, "label": RESULT_LABEL[result], "stuck": question["stuck"] if result != "pass" else ""}

    def finish_chain(self, cid):
        """사슬 끝. 이번 회차의 질문 판정을 모아 chain 을 기록하고 상자·다음 복습 날짜를 돌려줌."""
        content = self._chain_content(cid)
        rec = self._rec(cid)
        rec.reload()
        _, current = record.drill_answers(rec.log, cid)
        answered = {int(e.get("q") or 0): e for e in current}
        per_question = []
        for q in content["questions"]:
            entry = answered.get(q["no"])
            per_question.append(review.question_result(entry.get("need") or [0]) if entry else "stuck")
        result = review.chain_result(per_question)
        self._append({"kind": "chain", "chain": cid, "result": result}, rec)
        plan = self._schedules()[cid]
        meta = self._chain_meta(cid)
        return {"id": cid, "result": result, "label": RESULT_LABEL[result], "per_question": per_question, "box": plan["box"],
                "due": plan["due"].isoformat(), "weak": content["weak"], "follow": content["follow"], "page": meta["page"],
                "section": meta["section"]}

    def today_list(self, when=None):
        """오늘 복습 목록 {"chains": [...], "missions": [...], "minutes"}. 새 사슬은 권장 순서(index.order)대로 하루 2개."""
        when = when or today()
        schedules = self._schedules()
        found = self._states()
        new_order = []
        for iid in self.index["order"]:
            if iid in self.topics:
                new_order += [c["id"] for c in self.topics[iid]["chains"]]
            elif iid in self.missions and (found.get(iid) or {}).get("phase") == "done" and iid + "-F" in self.chains:
                new_order.append(iid + "-F")
        rows = [r for r in review.due_list(schedules, new_order, when, self.new_per_day()) if not self._locked(r["chain"], found)]
        for row in rows:
            row["title"] = self.chains[row["chain"]]["title"]
        minutes = 0.0
        for row in rows:
            try:
                minutes += len(self._chain_content(row["chain"])["questions"]) * MINUTES_PER_QUESTION
            except WebError:
                minutes += 3 * MINUTES_PER_QUESTION
        return {"chains": rows, "missions": review.retry_missions(found, self.missions, when), "minutes": int(round(minutes))}

    def new_per_day(self):
        """하루에 더하는 새 사슬 수. ~/.rokey-study/web/settings.json 의 new_per_day, 없으면 2."""
        try:
            return max(0, int(study.read_json(os.path.join(self.home, "settings.json"))["new_per_day"]))
        except (OSError, ValueError, KeyError, TypeError):
            return review.NEW_PER_DAY

    # 현황

    def _next(self, found, schedules, learned, today=None):
        """이어서 할 일 하나. 읽는 중·실전 중인 미션이 먼저, 그다음 오늘 복습할 사슬, 그다음 권장 순서(index.order)에서 아직 안 한 것.
        {"kind", "id", "title", "phase"(미션만), "chain"(복습 사슬의 주제 kind 일 때 사슬 id)}."""
        for iid in self.index["order"]:
            if iid in self.missions and (found.get(iid) or {}).get("phase") in ("reading", "live"):
                return {"kind": "mission", "id": iid, "title": self.missions[iid]["title"], "phase": found[iid]["phase"]}
        due = [row for row in (today or self.today_list())["chains"] if not row["new"]]  # 한 번 푼 사슬의 복습만. 새 사슬은 권장 순서로 돎
        if due:
            return {"kind": "chain", "id": due[0]["chain"], "title": due[0]["title"]}
        for iid in self.index["order"]:
            if iid in self.pages and iid not in learned:
                return {"kind": "page", "id": iid, "title": self.pages[iid]["title"]}
            if iid in self.missions and (found.get(iid) or {}).get("phase") != "done":
                return {"kind": "mission", "id": iid, "title": self.missions[iid]["title"], "phase": (found.get(iid) or {}).get("phase", "none")}
            if iid in self.topics and any(c["id"] not in schedules for c in self.topics[iid]["chains"]):
                chain = next(c for c in self.topics[iid]["chains"] if c["id"] not in schedules)
                return {"kind": "topic", "id": iid, "title": self.topics[iid]["title"], "chain": chain["id"], "chain_title": chain["title"]}
        return None

    def overview(self):
        """허브 카드와 웹 홈이 쓰는 현황. Node 를 찾고 설치 상태를 봄."""
        found = self._states()
        self.local.reload()
        schedules = self._schedules()
        learned = record.learned(self.record.log)
        missions = []
        for entry in self.index["missions"]:
            mission = self.missions.get(entry["id"])
            state = found.get(entry["id"]) or record.blank_mission()
            row = dict(entry, ready=bool(mission), error=self.errors.get(entry["id"], ""), phase=state["phase"],
                       phase_label=PHASE_LABEL[state["phase"]], try_no=state["try"], current=state["current"],
                       total_steps=len(mission["steps"]) if mission else 0, live_min=mission["live_min"] if mission else 0,
                       done_steps=sum(1 for k, s in state["steps"].items() if k >= 1 and s["result"] == "pass"),
                       skips=len(state["skips"]), timers=self._timers(mission, state) if mission else {})
            missions.append(row)
        topics = []
        for entry in self.index["topics"]:
            topic = self.topics.get(entry["id"])
            chains = []
            for chain in (topic["chains"] if topic else []):
                plan = schedules.get(chain["id"])
                chains.append({"id": chain["id"], "title": chain["title"], "goal": chain["goal"], "box": plan["box"] if plan else None,
                               "due": plan["due"].isoformat() if plan else None, "times": plan["times"] if plan else 0})
            topics.append(dict(entry, ready=bool(topic), error=self.errors.get(entry["id"], ""), chains=chains,
                               done=sum(1 for c in chains if c["times"]), total=len(chains)))
        pages = [dict(entry, ready=entry["id"] in self.pages, error=self.errors.get(entry["id"], ""),
                      learned_at=learned.get(entry["id"])) for entry in self.index["pages"]]
        talked, stuck = record.talked_ratio(self._all_log())
        today = self.today_list()
        return {"stack": self.stack_state(), "missions": missions, "topics": topics, "pages": pages,
                "done_missions": sum(1 for m in missions if m["phase"] == "done"), "ready_missions": sum(1 for m in missions if m["ready"]),
                "today": today, "next": self._next(found, schedules, learned, today), "talked": talked, "stuck": stuck,
                "activity": sorted(record.activity_days(self._all_log())), "activity_counts": record.activity_counts(self._all_log()),
                "bank_errors": list(self.bank_errors)}
