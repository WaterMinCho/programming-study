# -*- coding: utf-8 -*-
"""AI 비전 개론 서비스(설계 2.7~2.13). 화면은 AiSession 과 PracticeSet 만 부름. 반환은 dict·list, 오류는 사용자에게
그대로 보여 줄 AiError 임.

기록은 submissions/<ID>/ai/record.json 에 덧붙기만 하고(AiRecord), 상자·날짜·오늘 목표·오답 갈래는 기록에서 그때그때
계산해 (파일 mtime_ns, 크기, 줄 수, 학습일) 키로 캐시함. 학습 단원의 중간 자리(at_step)는 ~/.rokey-study/ai/<ID>/state.json
(STUDY_AI_HOME 으로 바꿈)에 둬서 제출에 들어가지 않음. 묶음은 secrets.randbelow 로 고른 시드 하나의 random.Random 으로 만들고
set 기록에 시드를 남겨 같은 기록·같은 시드면 같은 묶음이 나옴. 모의고사(PR5)와 뼈대 카드(PR2)는 아직 없음.
"""
import datetime
import json
import os
import random
import secrets
import threading

import adaptive
import session
import study
from aiprep import bank, gen, grade, notes, plan, review
from webprep import record

SET_SIZE = 20
SET_MIN = 8
UNIT_NEW = 8
UNIT_REVIEW = 10
UNIT_OTHER_SHARE = 0.3
GAP_WRONG = 3
GAP_CONFIRM = 5
MAX_FAIL = 4
REVIEW_FIRST = plan.REVIEW_FIRST
BACKLOG_HALF = plan.BACKLOG_HALF
# 2026-11-03 사용자 답(설계 14.4 질문 1): 하루 시간 예산을 두지 않고 문제집을 원하는 만큼 풂. 그래서 비핵심 새 카드 하루 상한과
# 오늘 목표 단원은 기본으로 끔. 설계 1.4 대로 켜려면 NEW_PER_DAY = plan.NEW_PER_DAY, DAILY_GOAL = True.
NEW_PER_DAY = None
DAILY_GOAL = False
GEN_SHARE = 0.15
DEEP_SHARE = 0.1
BLANK_MIN = 0.5
MEMORISED_BOX = review.MEMORISED_BOX
NOTE_MAX = 10
REVISIT_LEAD = 4
CHOICE_RUN = 3
MODES = ("unit", "review", "mixed", "lesson", "sweep", "note")
MODE_TITLE = {"review": "복습", "mixed": "섞어 풀기", "sweep": "시험 전 훑기", "note": "오답 다시 풀기"}
LABEL = "AI 비전 개론 기록(ai/record.json)"
now = adaptive.now  # 테스트가 바꿔 끼움


def home_dir():
    """저장소에 올리지 않는 로컬 값(at_step, 모의고사 초안)을 두는 폴더. STUDY_AI_HOME 으로 바꿀 수 있음."""
    return os.environ.get("STUDY_AI_HOME") or os.path.join(os.path.expanduser("~"), ".rokey-study", "ai")


class AiError(session.SessionError):
    """사용자에게 그대로 보여 줄 수 있는 AI 비전 개론 오류."""


class AiRecord(record.Record):
    """record.Record 와 같은 파일 꼴. 자기가 마지막으로 읽거나 쓴 파일의 (mtime_ns, 크기)가 그대로면 다시 읽지 않고
    메모리의 기록에 덧붙여 씀(4주 기록 1MB 안팎을 답마다 다시 읽지 않으려는 것). 다른 창이나 문제 받기로 파일이 바뀌면
    지금처럼 다시 읽음."""

    def __init__(self, path, user, label=LABEL):
        self._data, self._key, self.reads = None, None, 0
        super().__init__(path, user, label)

    def stamp(self):
        try:
            info = os.stat(self.path)
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size)

    def load(self):
        key = self.stamp()
        if key is not None and key == self._key and self._data is not None:
            return self._data
        data = super().load()
        self.reads += 1
        self._data, self._key = data, key
        return data

    def append(self, entry, at=None):
        with self._lock:
            try:
                row = super().append(entry, at)
            except record.RecordError:
                self._data, self._key = None, None
                raise
            if self._data is None or self._data.get("log") is not self.log:
                self._data, self._key = None, None
            else:
                self._key = self.stamp()
            return row

    @property
    def version(self):
        return (self._key, len(self.log))


def _today():
    return review.study_day(now())


def _md(day):
    return "%d월 %d일" % (day.month, day.day)


class AiSession(object):
    def __init__(self, user, home=None, root=None):
        """은행과 record.json 을 읽음. index.json·terms.json 이나 기록이 깨졌으면 AiError. 차시 하나가 깨지면 그 차시만 빼고
        errors 에 이유를 둠."""
        if not session.valid_user(user):
            raise AiError("ID 가 올바르지 않습니다: %r" % (user,))
        self.user = user
        self.root = root or bank.AI_DIR
        self.folder = os.path.join(study.SUBMISSIONS_DIR, user, "ai")
        self.home = os.path.join(home or home_dir(), user)
        self._lock = threading.RLock()
        try:
            self.record = AiRecord(os.path.join(self.folder, "record.json"), user)
        except record.RecordError as error:
            raise AiError(str(error))
        try:
            self.index = bank.read_index(self.root)
            self.terms = bank.read_terms(self.root)
        except bank.AiBankError as error:
            raise AiError("AI 비전 개론 목록을 읽을 수 없습니다. %s" % error)
        self.exam = review.exam_dates(self.index["exam"])
        self.term_map = grade.term_map(self.terms)
        self.lessons = {e["id"]: e for e in self.index["lessons"]}
        self.mocks = {e["id"]: e for e in self.index["mocks"]}
        self.notes, self.items, self.cards, self.errors = {}, {}, {}, {}
        try:
            bank.load_common(self.root)
        except bank.AiBankError as error:
            self.errors["common"] = str(error)
        for entry in self.index["lessons"]:
            if not bank.is_ready(entry, self.root):
                continue
            try:
                note = bank.load_note({"id": entry["page"], "title": entry["title"]}, self.root)
                data = bank.load_items(entry, self.root)
            except bank.AiBankError as error:
                self.errors[entry["id"]] = str(error)
                continue
            self.notes[entry["id"]], self.items[entry["id"]] = note, data
            for card in bank.cards_of(entry, data):
                if card["unit"] in note["visible"]:
                    self.cards[card["id"]] = card
        self._cache_key, self._cache = None, None
        self._index, self._index_log = None, None
        self._gen_kind = {}

    # 날짜와 캐시

    def today(self):
        return _today()

    def _state(self):
        """기록에서 계산한 값 묶음. 기록과 학습일이 바뀌지 않았으면 다시 계산하지 않음."""
        with self._lock:
            try:
                self.record.reload()
            except record.RecordError as error:
                raise AiError(str(error))
            log = self.record.log
            if self._index is None or self._index_log is not log or self._index.n > len(log):
                self._index, self._index_log = _LogIndex(), log  # 파일을 다시 읽었으면 처음부터
            self._index.feed(log[self._index.n:])
            key = (self.record.version, self.today())
            if key == self._cache_key and self._cache is not None:
                return self._cache
            state = _State(self, self._index, key[1])
            self._cache_key, self._cache = key, state
            return state

    # 학습 단원

    def _lesson(self, lid):
        if lid not in self.lessons:
            raise AiError("차시를 찾을 수 없습니다: %s" % lid)
        if lid in self.errors:
            raise AiError("%d차시를 읽을 수 없습니다. %s" % (self.lessons[lid]["no"], self.errors[lid]))
        if lid not in self.notes:
            raise AiError("%d차시는 아직 준비 중입니다." % self.lessons[lid]["no"])
        return self.lessons[lid]

    def _unit(self, lid, key):
        self._lesson(lid)
        note = self.notes[lid]
        if key not in note["visible"]:
            raise AiError("단원을 찾을 수 없습니다: %s" % key)
        return note["units"][key]

    def unit_list(self, lid):
        """그 차시의 공개 단원 [{"key", "title", "minutes", "kind", "key_figure", "steps", "deep"}]."""
        note = self.notes[lid]
        out = []
        for key in note["visible"]:
            unit, meta = note["units"][key], note["unit_meta"].get(key, {})
            steps = [s for s in unit["steps"] if s["scope"] != "trend"]
            out.append({"key": key, "title": unit["title"], "minutes": int(meta.get("minutes") or 5),
                        "kind": str(meta.get("kind") or "concept"), "key_figure": meta.get("key_figure"),
                        "steps": len(steps), "deep": any(s["scope"] == "deep" for s in steps)})
        return out

    def _blocks(self, lid, key, step, state):
        """단계 블록을 화면용으로. guess 는 답을 빼고 고른 번호를, reveal 은 짐작한 답과 정답을, figure 는 파일 경로를 채움."""
        guesses = state.guesses.get((lid, key), {})
        out = []
        unit = self.notes[lid]["units"][key]
        for block in step["blocks"]:
            block = dict(block)
            if block["kind"] == "guess":
                block["picked"] = guesses.get(block.get("id"))
                block.pop("answer", None)
            elif block["kind"] == "reveal":
                gid = block.get("guess") or block.get("id")
                source = next((b for s in unit["steps"] for b in s["blocks"]
                               if b["kind"] == "guess" and b.get("id") == gid), None)
                if source:
                    block.update(guess=gid, q=source.get("q"), options=source.get("options"), answer=source.get("answer"),
                                 picked=guesses.get(gid))
            out.append(block)
        return out

    def unit_steps(self, lid, key):
        """학습 단원의 단계. {"lesson", "unit", "title", "steps": [{"no", "title", "scope", "facts", "blocks"}], "at_step"}."""
        unit = self._unit(lid, key)
        state = self._state()
        steps = [{"no": s["no"], "title": s["title"], "scope": s["scope"], "facts": list(s["facts"]),
                  "blocks": self._blocks(lid, key, s, state)} for s in unit["steps"]]
        at = self._local().get("at_step", {}).get("%s/%s" % (lid, key))
        return {"lesson": lid, "unit": key, "title": unit["title"], "steps": steps, "at_step": at}

    def lesson(self, lid):
        """차시 화면. {"id", "no", "title", "date", "preview", "opened", "units": [단원 + read·cards·memorised·due]}."""
        entry = self._lesson(lid)
        state = self._state()
        units = []
        for unit in self.unit_list(lid):
            stats = state.unit_stats(lid, unit["key"])
            units.append(dict(unit, **stats))
        return {"id": lid, "no": entry["no"], "title": entry["title"], "date": entry["date"],
                "preview": state.is_preview(entry), "opened": lid in state.opened, "units": units}

    def note(self, lid, only_memo=False):
        """[전체 노트]·[외울 것] 화면. {"lesson", "title", "units": [{"key", "title", "steps"}]} 이고 only_memo 면 단계가
        외울 것 블록만 가짐. 맨 위 leeches 는 이 차시의 자주 틀리는 카드 id."""
        self._lesson(lid)
        state = self._state()
        units = []
        for unit in self.unit_list(lid):
            steps = self.unit_steps(lid, unit["key"])["steps"]
            if only_memo:
                steps = [dict(s, blocks=[b for b in s["blocks"] if b["kind"] == "memo"]) for s in steps]
                steps = [s for s in steps if s["blocks"]]
            units.append({"key": unit["key"], "title": unit["title"], "steps": steps})
        leeches = [cid for cid in state.leeches if self.cards.get(cid, {}).get("lesson") == lid]
        return {"lesson": lid, "title": self.lessons[lid]["title"], "units": units, "leeches": leeches}

    def revisit(self):
        """다시 볼 단원. {"lesson", "unit", "title", "figure", "memo"} 이나 없으면 None."""
        state = self._state()
        found = state.revisit_pick()
        if found is None:
            return None
        lid, key = found["lesson"], found["unit"]
        unit = self.notes[lid]["units"][key]
        meta = self.notes[lid]["unit_meta"].get(key, {})
        figure = None
        if meta.get("key_figure"):
            figure = os.path.join(self.notes[lid]["dir"], *str(meta["key_figure"]).split("/"))
        else:
            for step in unit["steps"]:
                fig = next((b for b in step["blocks"] if b["kind"] == "figure"), None)
                if fig:
                    figure = fig["path"]
                    break
        memo = [item for step in unit["steps"] for b in step["blocks"] if b["kind"] == "memo" for item in b.get("items", [])]
        return {"lesson": lid, "unit": key, "title": unit["title"], "figure": figure, "memo": memo}

    # 기록

    def _append(self, entry):
        try:
            return self.record.append(entry, now())
        except record.RecordError as error:
            raise AiError(str(error))

    def mark_read(self, lid, key):
        """마지막 단계를 보인 순간. 그 단원 핵심 카드가 열림."""
        self._unit(lid, key)
        return self._append({"kind": "learn", "lesson": lid, "unit": key})

    def save_revisit(self, lid, key):
        self._unit(lid, key)
        return self._append({"kind": "revisit", "lesson": lid, "unit": key})

    def save_guess(self, lid, key, gid, picked):
        self._unit(lid, key)
        return self._append({"kind": "guess", "lesson": lid, "unit": key, "id": str(gid), "picked": int(picked)})

    def save_recall(self, lid, key, rid, ok):
        self._unit(lid, key)
        return self._append({"kind": "recall", "lesson": lid, "unit": key, "id": str(rid), "ok": bool(ok)})

    def check_recall(self, block, value):
        """떠올리기 칸 하나를 채점함(기록은 save_recall 이 함). block 은 unit_steps 의 recall 블록."""
        return grade.grade_blank({"answer": block.get("answer") or [], "mode": block.get("mode") or "word"}, value,
                                 self.term_map)

    def _local(self):
        path = os.path.join(self.home, "state.json")
        try:
            data = study.read_json(path)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_step(self, lid, key, step):
        """학습 단원 중간 자리(로컬 state.json, 제출에 들어가지 않음)."""
        data = self._local()
        data.setdefault("at_step", {})["%s/%s" % (lid, key)] = int(step)
        try:
            study.write_text(os.path.join(self.home, "state.json"), json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        except OSError:
            pass  # 중간 자리는 편의라 못 써도 학습은 이어감

    # 카드

    def card_form(self, card, box):
        """카드가 이번에 나올 꼴(blank·choice). 문장 카드는 상자 2 이상이고 cloze 가 있으면 빈칸판."""
        kind = card["kind"]
        if kind in ("blank", "choice"):
            return kind
        if kind == "stmt":
            return "blank" if (box or 0) >= 2 and card["stmt"].get("cloze") else "choice"
        if kind == "gen":
            if card["id"] not in self._gen_kind:
                try:
                    self._gen_kind[card["id"]] = gen.run(card["gen"], 1)["kind"]
                except gen.GenError:
                    self._gen_kind[card["id"]] = "blank"
            return self._gen_kind[card["id"]]
        return "blank"

    def card_info(self, cid):
        card = self.cards.get(cid)
        if card is None:
            raise AiError("문항을 찾을 수 없습니다: %s" % cid)
        return card

    # 연습

    def start_set(self, mode, lesson=None, unit=None, mock=None, card=None, seed=None):
        """연습 묶음을 만들고 set 기록을 남김. 카드가 하나도 없으면 AiError."""
        if mode not in MODES:
            raise AiError("모르는 연습 모드입니다: %s" % mode)
        if mode == "lesson":
            self._lesson(lesson)
            if lesson not in self._state().opened:
                self._append({"kind": "open", "lesson": lesson})
        if mode == "unit" or (mode == "mixed" and unit):
            self._unit(lesson, unit)
        if mode == "note" and card is None:
            raise AiError("다시 풀 문항을 골라 주세요.")
        seed = int(seed) if seed is not None else secrets.randbelow(2 ** 31)
        state = self._state()
        picked = build_set(self, state, mode, random.Random(seed), lesson=lesson, unit=unit, card=card)
        if not picked:
            raise AiError("지금 풀 문항이 없습니다. 단원을 먼저 읽어 주세요.")
        day = state.today
        count = sum(1 for e in self.record.log if e.get("kind") == "set" and review.study_day(e.get("at")) == day)
        set_id = "s%s-%d" % (day.strftime("%Y%m%d"), count + 1)
        entry = {"kind": "set", "set": set_id, "mode": mode, "n": len(picked), "seed": seed}
        for name, value in (("lesson", lesson), ("unit", unit), ("card", card)):
            if value:
                entry[name] = value
        self._append(entry)
        return PracticeSet(self, set_id, mode, picked, seed, lesson=lesson, unit=unit)

    def title_of(self, mode, lesson=None, unit=None):
        """연습 화면 제목(설계 2.6)."""
        if mode == "unit" and lesson in self.notes and unit in self.notes[lesson]["units"]:
            return "%d차시 · %s" % (self.lessons[lesson]["no"], self.notes[lesson]["units"][unit]["title"])
        if mode == "lesson" and lesson in self.lessons:
            return "%d차시 풀기" % self.lessons[lesson]["no"]
        return MODE_TITLE.get(mode, "연습")

    # 오답 노트

    def wrong_notes(self):
        """[{"title", "items": [{"key", "label", "state", "sure", "leech", "deep", ...}]}]."""
        return self._state().notes()[0]

    def wrong_counts(self):
        return self._state().notes()[1]

    def wrong_item(self, key):
        """오답 노트 문항 하나. {"key", "title", "lines"(결과 줄), "stem", "kind", "options", "mine"(내 답 글 목록 또는 None),
        "ref", "lesson", "step"}."""
        state = self._state()
        card = self.card_info(key)
        rows = state.events.get(key, [])
        note = notes.card_note(rows, state.read_day(key))
        lines = []
        mock_rows = [r for r in rows if r["src"] == "mock" and r["result"] != "pass"]
        if mock_rows:
            lines.append("%s에서 %s" % (self.mocks.get(mock_rows[-1].get("mock"), {}).get("title", "모의고사"),
                                     "비움" if mock_rows[-1].get("dontknow") else "틀림"))
        if note["fails"]:
            times = sum(1 for r in rows if r["result"] != "pass")
            lines.append("%d일에 걸쳐 %d번 틀림" % (len(note["days"]), times) if len(note["days"]) > 1 else "%d번 틀림" % times)
        if note["sure"]:
            lines.append("확실하다고 했지만 틀림")
        last = self._last_wrong(key)
        mine = None
        if last is not None:
            if "value" in last:
                mine = [str(v) for v in last["value"]]
            elif last.get("dontknow"):
                mine = ["모르겠어요"]
            elif "picked" in last:
                mine = self._picked_text(card, last)
        view = self._static_view(card, last)
        return {"key": key, "title": state.note_title(card), "lines": lines, "stem": view["stem"], "kind": view["kind"],
                "options": [o["text"] for o in view.get("options", [])], "mine": mine, "ref": card["ref"],
                "lesson": card["lesson"], "step": card.get("step"), "state": note["state"]}

    def _last_wrong(self, key):
        """그 카드의 마지막 틀린 답 기록(생성기 시드와 문장 카드 shown 을 다시 쓰려고). 없으면 None."""
        return next((e for e in reversed(self.record.log) if e.get("kind") == "answer" and e.get("card") == key
                     and e.get("result") != "pass"), None)

    def _picked_text(self, card, entry):
        if card["kind"] == "stmt":
            texts = {s["id"]: s["text"] for s in card["topic"].get("statements", [])}
            return [texts.get(p, p) for p in entry.get("picked") or []]
        options = (card.get("item") or {}).get("options") or []
        return [options[p]["text"] for p in entry.get("picked") or [] if isinstance(p, int) and p < len(options)]

    def _static_view(self, card, entry=None):
        """오답 노트에 다시 그릴 문항. 생성기는 기록의 시드로, 문장 카드는 기록의 shown 순서로 다시 만듦."""
        entry = entry or {}
        if card["kind"] in ("blank", "choice"):
            return dict(card["item"])
        if card["kind"] == "gen":
            return gen.run(card["gen"], int(entry.get("seed") or 1))
        statement = card["stmt"]
        texts = {s["id"]: s for s in card["topic"].get("statements", [])}
        shown = [texts[i] for i in entry.get("shown") or [] if i in texts]
        if shown:
            return {"kind": "choice", "stem": "%s에 대한 설명으로 **%s** 것을 고르세요."
                    % (card["topic"].get("title", ""), "옳은" if statement.get("ok") else "옳지 않은"),
                    "options": [{"text": s["text"], "ok": bool(s.get("ok")), "why": s.get("why", "")} for s in shown],
                    "pick": entry.get("pick") or ("right" if statement.get("ok") else "wrong"), "explain": statement.get("why", "")}
        return {"kind": "choice", "stem": "다음 문장이 맞는지 고르세요.\n\n%s" % statement["text"], "options": [],
                "explain": statement.get("why", "")}

    def explain(self, key):
        """오답 노트 [해설 보기]. {"answer", "explain", "ref", "why"}."""
        card = self.card_info(key)
        view = self._static_view(card, self._last_wrong(key))
        if card["kind"] == "stmt":
            statement = card["stmt"]
            answer = ["맞는 문장입니다." if statement.get("ok") else "틀린 문장입니다."]
            return {"answer": answer, "explain": statement.get("why", ""), "ref": card["ref"], "why": {}}
        if view["kind"] == "blank":
            answer = [b["answer"][0] for b in view["blanks"]]
            return {"answer": answer, "explain": view.get("explain", ""), "ref": card["ref"], "why": {}}
        right = grade.right_options(view)
        return {"answer": [view["options"][n]["text"] for n in right], "explain": view.get("explain", ""), "ref": card["ref"],
                "why": {view["options"][n]["text"]: view["options"][n].get("why", "") for n in range(len(view["options"]))}}

    # 현황

    def overview(self):
        """홈과 허브의 현황(설계 2.13)."""
        return self._state().overview()


class _LogIndex(object):
    """기록을 덧붙는 만큼만 이어 읽는 색인. 카드별 답(review.EventIndex), 처음 읽은 날, 연 차시, 짐작, 다시 보기, 날마다 답한
    카드와 카드별 일정 캐시를 둠. 4주 기록(7,000줄 안팎)을 답마다 처음부터 다시 계산하지 않으려는 것임."""

    def __init__(self):
        self.events = review.EventIndex()
        self.reads, self.opened, self.guesses, self.revisits = {}, set(), {}, set()
        self.day_cards = {}
        self.sched, self.start_due = {}, {}
        self.n = 0

    def feed(self, entries):
        self.events.feed(entries)
        for e in entries:
            kind = e.get("kind")
            day = review.study_day(e.get("at"))
            where = (str(e.get("lesson")), str(e.get("unit")))
            if kind == "learn" and e.get("lesson") and e.get("unit") and day is not None:
                self.reads.setdefault(where, day)
            elif kind == "open" and e.get("lesson"):
                self.opened.add(str(e["lesson"]))
            elif kind == "guess":
                self.guesses.setdefault(where, {})[str(e.get("id"))] = e.get("picked")
            elif kind == "revisit" and day is not None:
                self.revisits.add(where + (day,))
            elif kind == "answer" and e.get("card") and day is not None:
                self.day_cards.setdefault(day, set()).add(str(e["card"]))
        self.n += len(entries)


class _State(object):
    """기록 한 판에서 계산한 값. AiSession._state 가 캐시하고, 카드 일정은 _LogIndex 의 캐시를 씀."""

    def __init__(self, sess, index, today):
        self.sess, self.today, self.exam, self.index = sess, today, sess.exam, index
        self.log = sess.record.log
        self.events = index.events.events
        self.reads = index.reads
        self.opened = index.opened
        self.guesses = index.guesses
        self.revisited_today = {(lesson, unit) for lesson, unit, day in index.revisits if day == today}
        self.sched = {}
        for cid, rows in self.events.items():
            read = self.read_day(cid)
            key = (index.events.ver.get(cid), today, read)
            hit = index.sched.get(cid)
            if hit is None or hit[0] != key:
                hit = (key, review.card_schedule(rows, read, self.exam, today, cid))
                index.sched[cid] = hit
            self.sched[cid] = hit[1]
        self.leeches = {cid for cid, s in self.sched.items() if review.leech(s)}
        self.new_today = sum(1 for cid, s in self.sched.items()
                             if s and s["first"] == today and cid in sess.cards and not sess.cards[cid]["core"])
        todays = {cid: self.events[cid] for cid in index.day_cards.get(today, ()) if cid in self.events}
        self.again = plan.again_cards(todays, today)
        self._notes = None
        self._units = {}
        for card in sess.cards.values():
            self._units.setdefault((card["lesson"], card["unit"]), []).append(card)

    # 카드 상태

    def read_day(self, cid):
        card = self.sess.cards.get(cid)
        if card is None:
            return None
        return self.reads.get((card["lesson"], card["unit"]))

    def box(self, cid):
        s = self.sched.get(cid)
        return s["box"] if s else None

    def unlocked(self, card):
        return (card["lesson"], card["unit"]) in self.reads or card["lesson"] in self.opened

    def core_ready(self, lesson, unit):
        """그 단원 핵심 카드가 모두 상자 2 이상인지(비핵심이 열리는 조건)."""
        core = [c for c in self._units.get((lesson, unit), []) if c["core"]]
        return all((self.box(c["id"]) or 0) >= 2 for c in core)

    def is_open(self, card):
        return card["id"] in self.events or (card["core"] and self.unlocked(card))

    def new_cap_left(self):
        """오늘 더 열 수 있는 비핵심 새 카드 수. NEW_PER_DAY 가 None 이면 상한 없음."""
        if NEW_PER_DAY is None:
            return 10 ** 6
        return max(0, NEW_PER_DAY - self.new_today)

    def eligible_new(self, card):
        """아직 답한 적 없고 오늘 새로 낼 수 있는 카드인지. 차시 풀기로 연 차시(문제집)는 모든 카드, 읽은 단원은 핵심 카드와
        핵심이 모두 상자 2 이상인 단원의 비핵심 카드(last_new 뒤에는 비핵심을 새로 열지 않음). 비핵심 하루 상한은 묶음을 만들 때 셈."""
        if card["id"] in self.events or not self.unlocked(card):
            return False
        if card["core"] or card["lesson"] in self.opened:
            return True
        last_new = self.exam.get("last_new")
        if last_new is not None and self.today > last_new:
            return False
        return self.core_ready(card["lesson"], card["unit"])

    def due_day(self, cid):
        card = self.sess.cards.get(cid)
        if cid not in self.sched:
            if card and card["core"] and self.unlocked(card) and review.in_sweep(self.exam, self.today):
                return review.sweep_day(cid, self.exam)
            return None
        return review.due_on(self.sched[cid], cid, self.exam, self.today)

    def sure_wrong(self, cid):
        """확신 오답을 다시 보는 기간(확실함으로 틀린 다음 날부터 7일 뒤 다시 볼 날까지)인지."""
        s = self.sched.get(cid)
        return bool(s) and s["recheck"] is not None and s["recheck"] >= self.today

    def due_cards(self):
        """날짜가 된 복습 카드(상대 지연 큰 순). 12-01 에는 상자 1·확신 오답·자주 틀리는 문항만."""
        last_day = self.exam.get("last_review") is not None and self.today == self.exam["last_review"]
        rows = []
        for cid, card in self.sess.cards.items():
            day = self.due_day(cid)
            if day is None or day > self.today:
                continue
            if last_day and not (self.box(cid) == 1 or self.sure_wrong(cid) or cid in self.leeches):
                continue
            rows.append(cid)
        rows.sort(key=lambda c: (-review.relative_delay(self.sched.get(c), self.today), c))
        return rows

    # 묶음

    def is_preview(self, lesson):
        day = review.parse_day(lesson.get("date"))
        return day is not None and day > self.today

    def unit_stats(self, lid, key):
        cards = self._units.get((lid, key), [])
        memorised = families_memorised(cards, self.sched)
        due = sum(1 for c in cards if (self.due_day(c["id"]) or datetime.date.max) <= self.today)
        return {"read": (lid, key) in self.reads, "cards": len(cards), "memorised": memorised,
                "families": len({c["family"] for c in cards}), "due": due}

    def revisit_pick(self):
        rows = []
        for (lid, key), day in self.reads.items():
            if lid not in self.sess.notes or key not in self.sess.notes[lid]["visible"]:
                continue
            core = [c for c in self._units.get((lid, key), []) if c["core"]] or self._units.get((lid, key), [])
            boxes = [self.box(c["id"]) or 0 for c in core]
            rows.append({"lesson": lid, "unit": key, "core_box": sum(boxes) / float(len(boxes)) if boxes else 0.0, "read": day})
        return plan.pick_revisit(rows, self.revisited_today)

    def note_title(self, card):
        return notes.group_title(card, self.sess.lessons, self.sess.mocks)[0]

    def notes(self):
        if self._notes is None:
            cards = dict(self.sess.cards)
            for cid in self.events:
                if cid not in cards and bank.MOCK_ID.match(cid.split("-")[0]):
                    cards[cid] = {"id": cid, "kind": "mock", "lesson": None}
            read = {cid: self.read_day(cid) for cid in self.events}
            mock_order = []
            for e in reversed(self.log):
                if e.get("kind") == "mock_submit" and e.get("mock") not in mock_order:
                    mock_order.append(e.get("mock"))
            self._notes = notes.wrong_notes(self.events, cards, read, self.sess.lessons, self.sess.mocks, self.leeches,
                                            mock_order)
        return self._notes

    def _units_read_before_today(self):
        return sum(1 for day in self.reads.values() if day < self.today)

    def _unread_units(self):
        rows = []
        for lid, note in self.sess.notes.items():
            entry = self.sess.lessons[lid]
            for n, key in enumerate(note["visible"]):
                if (lid, key) in self.reads:
                    continue
                meta = note["unit_meta"].get(key, {})
                rows.append({"lesson": lid, "no": entry["no"], "date": review.parse_day(entry["date"]), "unit": key, "order": n,
                             "title": note["units"][key]["title"], "minutes": int(meta.get("minutes") or 5)})
        return rows

    def plan(self):
        """오늘 목표 줄 값. DAILY_GOAL 이 꺼져 있어도 계산은 하고 goal 키로 알림(화면이 보일지 정함)."""
        planned = sum(e["units"] for e in self.sess.index["lessons"])
        planned += sum(len(p["units"]) for p in self.sess.index["patterns"])
        unread = self._unread_units()
        read_today = sum(1 for day in self.reads.values() if day == self.today)
        start_due = self._due_at_start()
        target = plan.units_target(planned, self._units_read_before_today(), len(unread) + read_today, self.today, self.exam,
                                   start_due)
        return {"days_left": plan.days_left(self.exam, self.today), "units_today": target, "units_read_today": read_today,
                "new_today": self.new_today, "new_cap": NEW_PER_DAY, "sweep": review.in_sweep(self.exam, self.today),
                "backlog": start_due > BACKLOG_HALF, "goal": DAILY_GOAL}

    def _due_at_start(self):
        """오늘 첫 화면 때의 밀린 복습 수(오늘 답을 빼고 계산). 하루에 한 번 계산해 색인에 둠."""
        if self.today in self.index.start_due:
            return self.index.start_due[self.today]
        count = 0
        for cid, rows in self.events.items():
            if cid not in self.sess.cards:
                continue
            before = [r for r in rows if r["day"] < self.today]
            if not before:
                continue
            s = review.card_schedule(before, self.read_day(cid), self.exam, self.today, cid)
            day = review.due_on(s, cid, self.exam, self.today)
            if day is not None and day <= self.today:
                count += 1
        self.index.start_due[self.today] = count
        return count

    def next(self, plan_row, due):
        ready = {mid for mid in self.sess.mocks if os.path.isfile(os.path.join(bank.mock_dir(mid, self.sess.root), "meta.json"))}
        taken = {str(e.get("mock")) for e in self.log if e.get("kind") == "mock_submit"}
        unit = plan.pick_unit(self._unread_units(), self.today)
        revisit = self.revisit_pick()
        if revisit:
            revisit = dict(revisit, no=self.sess.lessons[revisit["lesson"]]["no"],
                           title=self.sess.notes[revisit["lesson"]]["units"][revisit["unit"]]["title"])
        ctx = {"today": self.today, "exam": self.exam, "again": self.again,
               "mock": plan.pending_mock(self.sess.index["mocks"], ready, taken, self.today, self.exam), "due": due,
               "target": plan_row["units_today"] if DAILY_GOAL else None, "read_today": plan_row["units_read_today"], "unit": unit,
               "revisit": revisit}
        return plan.next_card(ctx)

    def overview(self):
        sess = self.sess
        due = self.due_cards()
        lessons = []
        for entry in sess.index["lessons"]:
            row = {"id": entry["id"], "no": entry["no"], "title": entry["title"], "date": entry["date"], "weight": entry["weight"],
                   "ready": entry["id"] in sess.notes, "error": sess.errors.get(entry["id"]), "preview": self.is_preview(entry),
                   "units": [], "read": 0, "units_total": 0, "cards": 0, "memorised": 0, "families": 0, "due": 0,
                   "state": "none"}
            if row["ready"]:
                core_marks = []
                for unit in sess.unit_list(entry["id"]):
                    stats = self.unit_stats(entry["id"], unit["key"])
                    row["units"].append(dict(unit, **stats))
                    row["read"] += int(stats["read"])
                    for key in ("cards", "memorised", "families", "due"):
                        row[key] += stats[key]
                    core_marks += [review.memorised(self.sched.get(c["id"])) for c in self._units.get((entry["id"], unit["key"]), [])
                                   if c["core"]]
                row["units_total"] = len(row["units"])
                row["state"] = plan.lesson_state(row["read"], row["units_total"], core_marks)
            lessons.append(row)
        today_rows = [e for e in sess.record.log if e.get("kind") == "answer" and review.study_day(e.get("at")) == self.today]
        moved = 0
        for cid, s in self.sched.items():
            if s and any(day == self.today and flag for day, _, flag in s["days"]):
                moved += 1
        plan_row = self.plan()
        counts = self.notes()[1]
        activity = activity_counts(self.log)
        mocks = [{"id": m["id"], "title": m["title"], "minutes": m["minutes"], "count": m["count"], "range": m["range"],
                  "window": m["window"], "ready": os.path.isfile(os.path.join(bank.mock_dir(m["id"], sess.root), "meta.json"))}
                 for m in sess.index["mocks"]]
        last_at = max((str(e.get("at") or "") for e in self.log), default=None) or None
        return {"lessons": lessons, "patterns": [], "mocks": mocks, "due": len(due), "again": len(self.again),
                "today_answers": moved, "today_extra": max(0, len(today_rows) - moved),
                "memorised": families_memorised(list(sess.cards.values()), self.sched), "cards": len(sess.cards),
                "families": len({c["family"] for c in sess.cards.values()}), "plan": plan_row, "next": self.next(plan_row, len(due)),
                "notes": counts, "activity": sorted(activity), "activity_counts": activity, "recent": recent_lines(self.log),
                "last_at": last_at, "errors": dict(sess.errors)}


def families_memorised(cards, sched):
    """외운 문항 수. family 하나를 한 번만 세고, family 안 열린(답한) 카드가 모두 상자 4 이상일 때 외운 것으로 봄."""
    groups = {}
    for card in cards:
        s = sched.get(card["id"])
        if s:
            groups.setdefault(card["family"], []).append(review.memorised(s))
    return sum(1 for marks in groups.values() if marks and all(marks))


def activity_counts(log):
    """{달력 날짜: AI 하루 수}. 끝낸 연습 묶음, 끝까지 읽은 단원, 제출한 모의고사를 1 씩 셈(허브 막대)."""
    counts = {}
    for e in log:
        if e.get("kind") in ("set_end", "learn", "mock_submit") and e.get("at"):
            day = str(e["at"])[:10]
            counts[day] = counts.get(day, 0) + 1
    return counts


def recent_lines(log, most=5):
    """허브 최근 채점 줄 [{"at", "kind", "n", "first_pass", "score", "of", "mock"}] (최근 순)."""
    out = []
    for e in reversed(log):
        if e.get("kind") == "set_end":
            out.append({"at": e.get("at"), "kind": "set", "n": e.get("n"), "first_pass": e.get("first_pass")})
        elif e.get("kind") == "mock_submit" and int(e.get("try") or 1) == 1:
            out.append({"at": e.get("at"), "kind": "mock", "mock": e.get("mock"), "score": e.get("score"), "of": e.get("of")})
        if len(out) >= most:
            break
    return out


# 묶음 만들기

def _choose(sess, state, pools, size, rng, taken=()):
    """pools 의 순서대로 카드를 고름. family 하나, 생성기 GEN_SHARE·심화 DEEP_SHARE 상한, 심화 짝을 지킴. [(카드 id, 풀 이름)].
    taken 은 이미 고른 [(카드 id, 풀 이름)](상한과 family 를 이어 셈)."""
    chosen, families = list(taken), {sess.cards[c]["family"] for c, _ in taken}
    gens = sum(1 for c, _ in taken if sess.cards[c]["kind"] == "gen")
    deeps = sum(1 for c, _ in taken if sess.cards[c]["deep"])
    gen_cap, deep_cap = int(size * GEN_SHARE), max(1, int(size * DEEP_SHARE))
    seen = {c for c, _ in taken}
    all_ids = [cid for _, ids in pools for cid in ids]

    def can(cid):
        card = sess.cards[cid]
        if cid in seen or card["family"] in families:
            return False
        if card["kind"] == "gen" and gens >= gen_cap:
            return False
        if card["deep"] and deeps >= deep_cap:
            return False
        return True

    def take(cid, pool):
        nonlocal gens, deeps
        card = sess.cards[cid]
        chosen.append((cid, pool))
        seen.add(cid)
        families.add(card["family"])
        gens += card["kind"] == "gen"
        deeps += bool(card["deep"])

    for pool, ids in pools:
        for cid in ids:
            if len(chosen) >= size:
                break
            if cid not in sess.cards or not can(cid):
                continue
            take(cid, pool)
            card = sess.cards[cid]
            if card["deep"] and card["confuse"] and len(chosen) < size:  # 심화 짝을 같은 묶음에
                mate = next((m for m in all_ids if m in sess.cards and sess.cards[m]["deep"] and m != cid
                             and set(sess.cards[m]["confuse"]) & set(card["confuse"]) and can(m)), None)
                if mate:
                    take(mate, pool)
    return chosen


def _fix_blanks(sess, state, chosen, pools, protected):
    """빈칸 꼴이 BLANK_MIN 아래면 보호하지 않은 풀의 고르기 카드를 남은 빈칸 카드로 바꿈(완화 순서의 마지막)."""
    def form(cid):
        return sess.card_form(sess.cards[cid], state.box(cid))
    families = {sess.cards[c]["family"] for c, _ in chosen}
    have = {c for c, _ in chosen}
    spare = [(cid, pool) for pool, ids in pools for cid in ids if cid in sess.cards and cid not in have
             and form(cid) == "blank" and sess.cards[cid]["kind"] != "gen" and sess.cards[cid]["family"] not in families]
    while chosen and sum(1 for c, _ in chosen if form(c) == "blank") < BLANK_MIN * len(chosen) and spare:
        swap = next((n for n in range(len(chosen) - 1, -1, -1) if chosen[n][1] not in protected and form(chosen[n][0]) == "choice"), None)
        if swap is None:
            break
        new = spare.pop(0)
        if sess.cards[new[0]]["family"] in {sess.cards[c]["family"] for c, _ in chosen}:
            continue
        chosen[swap] = new
    return chosen


def _gen_trim(sess, chosen):
    """묶음이 작아졌을 때 생성기를 GEN_SHARE 아래로 줄임(뒤의 것부터)."""
    while True:
        gens = [n for n, (c, _) in enumerate(chosen) if sess.cards[c]["kind"] == "gen"]
        if not gens or len(gens) <= int(len(chosen) * GEN_SHARE):
            return chosen
        del chosen[gens[-1]]


def _arrange(sess, state, chosen, rng, pattern=None):
    """순서 정하기. 같은 confuse 카드는 사이에 한 문항만 두고, 같은 차시·tags 는 붙이지 않고, 고르기는 CHOICE_RUN 개 넘게
    잇지 않음. 맞지 않으면 confuse → 차시·tags → 고르기 순으로 풂. pattern 이 있으면(단원 모드) 자리마다 N(새 카드, 주어진
    순서 그대로)·R(나머지)을 정함."""
    def form(cid):
        return sess.card_form(sess.cards[cid], state.box(cid))
    new = [c for c, pool in chosen if pool == "new"] if pattern else []
    rest = [c for c, pool in chosen if not pattern or pool != "new"]
    rng.shuffle(rest)
    seq = []
    while new or rest:
        if pattern:
            slot = pattern[len(seq) % len(pattern)]
            if slot == "N" and new:
                seq.append(new.pop(0))
                continue
            if not rest:
                seq.append(new.pop(0))
                continue
        pool = rest
        prev = sess.cards[seq[-1]] if seq else None
        two = sess.cards[seq[-2]] if len(seq) >= 2 else None
        run = 0
        for c in reversed(seq):
            if form(c) != "choice":
                break
            run += 1

        spread = prev is not None and any(sess.cards[c]["lesson"] != prev["lesson"] for c in pool)
        loose = prev is not None and any(not set(sess.cards[c]["tags"]) & set(prev["tags"]) for c in pool)

        def ok(cid, level):
            card = sess.cards[cid]
            if level < 3 and run >= CHOICE_RUN and form(cid) == "choice":
                return False
            if level < 2 and prev is not None and ((spread and prev["lesson"] == card["lesson"])
                                                    or (loose and set(prev["tags"]) & set(card["tags"]))):
                return False
            if level < 1:
                if prev is not None and set(prev["confuse"]) & set(card["confuse"]):
                    return False  # 바로 붙이지 않고 한 문항 띄움
                if two is not None and two["confuse"] and any(set(two["confuse"]) & set(sess.cards[m]["confuse"]) for m in pool):
                    return bool(set(two["confuse"]) & set(card["confuse"]))
            return True

        choices = sum(1 for c in pool if form(c) == "choice")
        dense = choices >= CHOICE_RUN * (len(pool) - choices)  # 고르기가 많으면 빈칸을 칸막이로 아껴 둠
        pick = None
        for level in range(4):
            allowed = [c for c in pool if ok(c, level)]
            if allowed:
                preferred = []
                if dense and run < CHOICE_RUN:  # 고르기가 많으면 차시·tags 떨어뜨리기를 먼저 풀어 고르기 잇기 규칙을 지킴
                    preferred = [c for c in allowed if form(c) == "choice"]
                    if not preferred and level < 2:
                        preferred = [c for c in pool if form(c) == "choice" and ok(c, 2)]
                pick = (preferred or allowed)[0]
                break
        pool.remove(pick)
        seq.append(pick)
    return seq


def build_set(sess, state, mode, rng, lesson=None, unit=None, card=None):
    """모드별 묶음 카드 id 목록(설계 2.9). 화면 순서까지 정해서 돌려줌."""
    cards = sess.cards
    today = state.today
    again = [c for c in state.again if c in cards]
    due = [c for c in state.due_cards() if c not in again]
    cap = state.new_cap_left()

    def new_cards(where=None):
        rows, extra = [], 0
        for c in sorted(cards.values(), key=lambda c: (sess.lessons[c["lesson"]]["no"], c["unit"], c["order"])):
            if where and not where(c):
                continue
            if not state.eligible_new(c):
                continue
            if not c["core"]:
                if extra >= cap:
                    continue
                extra += 1
            rows.append(c["id"])
        rows.sort(key=lambda cid: not cards[cid]["core"])
        return rows

    def read_cards(where=None):
        return [c["id"] for c in cards.values() if state.is_open(c) and c["id"] in state.events and (not where or where(c))]

    def weighted(ids):
        pool = list(ids)
        out = []
        while pool:
            weights = [sess.lessons[cards[c]["lesson"]]["weight"] * cards[c]["prio"] * (6 - (state.box(c) or 0)) for c in pool]
            total = sum(weights)
            mark, acc = rng.random() * total, 0.0
            for n, w in enumerate(weights):
                acc += w
                if acc >= mark:
                    out.append(pool.pop(n))
                    break
            else:
                out.append(pool.pop())
        return out

    size = SET_SIZE
    pattern = None
    overflow = []
    protected = {"again", "due", "new", "lead"}
    if mode == "unit":
        fresh = new_cards(lambda c: c["lesson"] == lesson and c["unit"] == unit)
        others = [c for c in read_cards(lambda c: (c["lesson"], c["unit"]) != (lesson, unit)) if c not in due and c not in again]
        rng.shuffle(others)
        pools = [("again", again), ("new", fresh[:UNIT_NEW]), ("due", due[:UNIT_REVIEW]), ("other", others)]
        overflow = [("new", fresh[UNIT_NEW:]), ("due", due[UNIT_REVIEW:])]  # 묶음이 SET_MIN 보다 작을 때만 씀
        pattern = "NNR"
    elif mode in ("review", "sweep"):
        low = sorted([c for c in read_cards() if c not in due and c not in again and (state.box(c) or 0) <= 2],
                     key=lambda c: (state.box(c) or 0, str(state.due_day(c)), c))
        gens = [c for c in read_cards() if cards[c]["kind"] == "gen" and c not in due]
        rng.shuffle(gens)
        pools = [("again", again), ("due", due), ("low", low), ("gen", gens)]
    elif mode in ("mixed", "lesson"):
        where = (lambda c: c["lesson"] == lesson) if mode == "lesson" else None
        if where:
            again = [c for c in again if where(cards[c])]
            due = [c for c in due if where(cards[c])]
        fresh = new_cards(where)
        rest = weighted([c for c in read_cards(where) if c not in due and c not in again])
        pools = [("again", again), ("due", due), ("new", fresh), ("rest", rest)]
        if mode == "mixed" and lesson and unit:  # 다시 보기 뒤: 맨 앞 REVISIT_LEAD 문항을 그 단원 카드로
            mine = [c["id"] for c in state._units.get((lesson, unit), []) if state.is_open(c)]
            mine.sort(key=lambda c: (c not in due, state.box(c) or 0, cards[c]["order"]))
            pools.insert(0, ("lead", mine[:REVISIT_LEAD]))
    elif mode == "note":
        groups = state.notes()[0]
        target = None
        for group in groups:
            for item in group["items"]:
                if item["key"] == card:
                    target = (group, item)
        if card not in cards:
            raise AiError("문항을 찾을 수 없습니다: %s" % card)
        mates = []
        if target:
            mates = [i["key"] for i in target[0]["items"] if i["state"] == target[1]["state"] and i["key"] != card]
        pools = [("lead", [card]), ("rest", mates)]
        size = NOTE_MAX
    else:
        raise AiError("모르는 연습 모드입니다: %s" % mode)
    chosen = _choose(sess, state, pools, size, rng)
    if len(chosen) < SET_MIN and overflow:
        chosen = _choose(sess, state, overflow, SET_MIN, rng, taken=chosen)
    chosen = _fix_blanks(sess, state, chosen, pools, protected)
    chosen = _gen_trim(sess, chosen)
    if mode == "unit":
        return _arrange(sess, state, chosen, rng, pattern)
    lead = [c for c, pool in chosen if pool == "lead"]
    rest = [(c, pool) for c, pool in chosen if pool != "lead"]
    return lead + _arrange(sess, state, rest, rng)


# 연습 묶음

class PracticeSet(object):
    """묶음 하나(설계 2.7). current() → answer()/dont_know() → (override()) → next() 를 되풀이하고 끝나면 summary().
    틀리면 GAP_WRONG 문항 뒤에, 틀린 적 있는 카드를 처음 맞히면 GAP_CONFIRM 문항 뒤에 다시 내고, 두 번 이어 맞히면 끝냄.
    같은 묶음에서 MAX_FAIL 번째로 틀리면 빼서 오늘 다시 볼 카드로 남김."""

    def __init__(self, sess, set_id, mode, cards, seed, lesson=None, unit=None):
        self.sess, self.id, self.mode, self.lesson, self.unit = sess, set_id, mode, lesson, unit
        self.rng = random.Random(seed * 7919 + 1)
        self.queue = [{"card": cid, "again": 0, "seed": self.rng.randrange(2 ** 31)} for cid in cards]
        self.pos = 0
        self.stats = {cid: {"fails": 0, "streak": 0, "shown": 0, "first": None, "done": False, "left": False} for cid in cards}
        self.answered = None
        self._undo = None
        self.answers = 0
        state = sess._state()
        self.before = {cid: state.box(cid) for cid in cards}
        self.before_due = {cid: state.due_day(cid) for cid in cards}
        self.had_before = {cid: any(e["day"] < state.today for e in state.events.get(cid, [])) for cid in cards}
        self.sure_before = {cid for cid in cards if state.sure_wrong(cid)}
        self.memorised_before = families_memorised([sess.cards[c] for c in cards], state.sched)
        self.title = sess.title_of(mode, lesson, unit)
        self.ended = False

    # 문항 보이기

    def _view(self, entry):
        if "view" in entry:
            return entry["view"]
        sess = self.sess
        card = sess.cards[entry["card"]]
        state = sess._state()
        box = state.box(card["id"])
        rng = random.Random(entry["seed"])
        view = {"form": sess.card_form(card, box), "shown": None, "seed": entry["seed"]}
        if card["kind"] in ("blank", "choice"):
            item = card["item"]
            if entry["again"] and isinstance(item.get("alt"), dict):  # 묶음 안에서 다시 낼 때 바꿔 쓴 판
                item = dict(item, **item["alt"])
        elif card["kind"] == "gen":
            item = gen.run(card["gen"], entry["seed"])
        elif view["form"] == "blank":
            cloze = card["stmt"]["cloze"]
            item = {"kind": "blank", "stem": cloze["text"],
                    "blanks": [{"answer": cloze["answer"], "mode": cloze.get("mode") or "word", "hint": cloze.get("hint", "")}],
                    "explain": card["stmt"].get("why", "")}
        else:
            item = self._statement_choice(card, state, rng, entry["again"])
            view["shown"] = [o["id"] for o in item["options"]]
        view["item"] = item
        order = list(range(len(item.get("options") or [])))
        if order and not view["shown"]:
            rng.shuffle(order)
        view["order"] = order
        entry["view"] = view
        return view

    def _statement_choice(self, card, state, rng, again):
        """문장 카드의 고르기판. 참 문장이면 거짓 문장 셋과 pick right, 거짓이면 참 문장 셋과 pick wrong. 함께 낼 문장은 열린
        것부터 상자가 낮은 순(다시 낼 때는 열린 것 가운데 아무거나), 모자라면 같은 차시 같은 tag 주제에서 빌림."""
        sess, statement, topic = self.sess, card["stmt"], card["topic"]
        want = not bool(statement.get("ok"))
        pool = [s for s in topic.get("statements", []) if bool(s.get("ok")) == want and s["id"] != statement["id"]]
        if len(pool) < 3:
            for other in sess.cards.values():
                if other["kind"] == "stmt" and other["lesson"] == card["lesson"] and other["topic"]["id"] != topic["id"] \
                        and set(other["tags"]) & set(card["tags"]) and bool(other["stmt"].get("ok")) == want:
                    pool.append(other["stmt"])
        rows = list(pool)
        rng.shuffle(rows)
        opened = [s for s in rows if s["id"] in sess.cards and state.is_open(sess.cards[s["id"]])]
        closed = [s for s in rows if s not in opened]
        if not again:
            opened.sort(key=lambda s: state.box(s["id"]) or 0)
        mates = (opened + closed)[:3]
        options = [{"id": s["id"], "text": s["text"], "ok": bool(s.get("ok")), "why": s.get("why", "")} for s in [statement] + mates]
        rng.shuffle(options)
        return {"kind": "choice", "stem": "%s에 대한 설명으로 **%s** 것을 고르세요." % (topic.get("title", ""), "옳은" if statement.get("ok") else "옳지 않은"),
                "options": options, "pick": "right" if statement.get("ok") else "wrong", "multi": False,
                "explain": statement.get("why", "")}

    def current(self):
        """지금 문항. 끝났으면 None. {"card", "kind", "chips", "stem", "blanks": [{"mode", "hint"}], "options": [{"no", "text"}],
        "multi", "pick", "code", "again", "step", "lesson", "at", "total", "answered"}."""
        if self.pos >= len(self.queue):
            return None
        entry = self.queue[self.pos]
        card = self.sess.cards[entry["card"]]
        view = self._view(entry)
        item = view["item"]
        form = item.get("kind") or view["form"]
        code = form == "blank" and bank.blanks_in_code(item.get("stem", ""))
        chips = []
        lesson = self.sess.lessons.get(card["lesson"])
        if lesson:
            chips.append("%d차시" % lesson["no"])
        chips.append(("코드 빈칸" if code else "빈칸") if form == "blank" else "고르기")
        if card["kind"] == "gen":
            chips.append("숫자 바뀜")
        if entry["again"]:
            chips.append("다시 나온 문항")
        if card["id"] in self.sure_before:
            chips.append("지난번 확실했던 문항")
        if card["deep"]:
            chips.append("심화")
        options = [{"no": n, "text": item["options"][n]["text"]} for n in view["order"]]
        return {"card": card["id"], "kind": form, "chips": chips, "stem": item.get("stem", ""),
                "blanks": [{"mode": b.get("mode") or "word", "hint": b.get("hint", "")} for b in item.get("blanks") or []],
                "options": options, "multi": bool(item.get("multi")), "pick": item.get("pick", "right"), "code": code,
                "again": entry["again"], "step": card.get("step"), "lesson": card["lesson"], "at": self.pos + 1,
                "total": len(self.queue), "answered": self.answered is not None}

    # 답하기

    def _feedback(self, card, view, graded, picked=None):
        item = view["item"]
        out = {"result": graded["result"], "per_blank": graded.get("per_blank", []), "correct": [], "picked": picked or [],
               "right": graded.get("right", []), "why": {}, "explain": item.get("explain", ""), "ref": self._ref(card, view),
               "errata": self._errata(card), "sure_wrong": False}
        if item.get("blanks"):
            out["correct"] = [b["answer"][0] for b in item["blanks"]]
        for n, option in enumerate(item.get("options") or []):
            out["why"][n] = option.get("why", "")
        return out

    def _ref(self, card, view):
        if card["kind"] == "stmt":
            return list(card["stmt"].get("ref") or card["ref"])
        return list(card["ref"])

    def _errata(self, card):
        data = self.sess.items.get(card["lesson"], {})
        return [{"id": x, "right": data.get("errata", {}).get(x, {}).get("right", ""),
                 "where": data.get("errata", {}).get(x, {}).get("where", "")} for x in card["errata"]]

    def answer(self, value, secs, sure):
        """답을 채점하고 기록함. 빈칸은 칸마다 글 목록, 고르기는 고른 보기의 no(원래 번호) 목록."""
        if self.pos >= len(self.queue):
            raise AiError("묶음이 끝났습니다.")
        if self.answered is not None:
            raise AiError("이미 답한 문항입니다.")
        entry = self.queue[self.pos]
        card = self.sess.cards[entry["card"]]
        view = self._view(entry)
        item = view["item"]
        row = {"kind": "answer", "set": self.id, "card": card["id"], "sure": bool(sure), "secs": round(float(secs or 0), 1),
               "again": entry["again"]}
        if card["kind"] == "gen" or view["shown"]:
            row["seed"] = entry["seed"]
        if (item.get("kind") or view["form"]) == "blank":
            values = [str(v) for v in (value or [])]
            graded = grade.grade_item(item, values, self.sess.term_map)
            feedback = self._feedback(card, view, graded)
            if graded["result"] != "pass":
                row["value"] = values
        else:
            picked = sorted({int(v) for v in (value or [])})
            graded = grade.grade_choice(item, picked)
            feedback = self._feedback(card, view, graded, picked)
            if view["shown"]:
                row.update(shown=view["shown"], pick=item.get("pick"))
                row["picked"] = [view["shown"][p] for p in picked if p < len(view["shown"])]
                also = self._also(card, view, picked, graded)
                if also:
                    row["also"] = also
            elif graded["result"] != "pass":
                row["picked"] = picked
        row["result"] = graded["result"]
        feedback["sure_wrong"] = bool(sure) and graded["result"] != "pass"
        return self._settle(entry, row, feedback)

    def _also(self, card, view, picked, graded):
        """문장 카드에서 고른 다른 보기. 그 보기가 열린 카드면 그 카드에도 stuck(설계 3.5, 열리지 않은 카드는 남기지 않음)."""
        state = self.sess._state()
        out = {}
        right = set(graded["right"])
        for p in picked:
            if p in right or p >= len(view["shown"]):
                continue
            sid = view["shown"][p]
            if sid != card["id"] and sid in self.sess.cards and state.is_open(self.sess.cards[sid]):
                out[sid] = "stuck"
        return out

    def dont_know(self, secs):
        """[모르겠어요]. stuck 으로 기록하고 정답을 보임."""
        if self.pos >= len(self.queue) or self.answered is not None:
            raise AiError("답할 문항이 없습니다.")
        entry = self.queue[self.pos]
        card = self.sess.cards[entry["card"]]
        view = self._view(entry)
        row = {"kind": "answer", "set": self.id, "card": card["id"], "result": "stuck", "dontknow": True,
               "secs": round(float(secs or 0), 1), "again": entry["again"]}
        if card["kind"] == "gen" or view["shown"]:
            row["seed"] = entry["seed"]
        if view["shown"]:
            row.update(shown=view["shown"], pick=view["item"].get("pick"), picked=[])
        item = view["item"]
        if item.get("blanks"):
            graded = {"result": "stuck", "per_blank": [False] * len(item["blanks"])}
        else:
            graded = {"result": "stuck", "right": grade.right_options(item)}
        return self._settle(entry, row, self._feedback(card, view, graded))

    def _settle(self, entry, row, feedback):
        self.sess._append(row)
        self.answers += 1
        snapshot = (list(self.queue), {k: dict(v) for k, v in self.stats.items()})
        self._undo = (snapshot, entry, row)
        self._apply(entry, row["result"])
        self.answered = feedback
        return feedback

    def _apply(self, entry, result):
        st = self.stats[entry["card"]]
        st["shown"] += 1
        if st["first"] is None:
            st["first"] = result
        at = self.pos
        if result == "pass":
            if st["fails"] == 0:
                st["done"] = True
                return
            st["streak"] += 1
            if st["streak"] >= 2:
                st["done"] = True
                return
            self._requeue(entry, at + 1 + GAP_CONFIRM)
            return
        st["fails"] += 1
        st["streak"] = 0
        if st["fails"] >= MAX_FAIL:
            st["left"] = True
            return
        self._requeue(entry, at + 1 + GAP_WRONG)

    def _requeue(self, entry, where):
        again = {"card": entry["card"], "again": entry["again"] + 1, "seed": self.rng.randrange(2 ** 31)}
        if where >= len(self.queue):
            self.queue.append(again)
        else:
            self.queue.insert(where, again)

    def override(self):
        """[내 답도 맞음]. 방금 틀린 빈칸 답을 맞음으로 바꾸고 override 기록을 남김."""
        if self._undo is None or self.answered is None:
            raise AiError("바꿀 답이 없습니다.")
        (queue, stats), entry, row = self._undo
        if row["result"] == "pass" or "value" not in row:
            raise AiError("빈칸을 틀린 답만 바꿀 수 있습니다.")
        self.sess._append({"kind": "override", "set": self.id, "again": row["again"], "card": row["card"], "value": row["value"]})
        self.queue, self.stats = queue, stats
        self._apply(entry, "pass")
        self.answered = dict(self.answered, result="pass", overridden=True)
        self._undo = None
        return self.answered

    def next(self):
        """다음 문항으로. 끝나면 set_end 를 기록하고 None."""
        if self.answered is None and self.pos < len(self.queue):
            raise AiError("답한 뒤에 넘어갈 수 있습니다.")
        self.pos += 1
        self.answered, self._undo = None, None
        if self.pos >= len(self.queue):
            self._end()
            return None
        return self.current()

    def _end(self):
        if self.ended:
            return
        self.ended = True
        first_pass = sum(1 for st in self.stats.values() if st["first"] == "pass")
        self.sess._append({"kind": "set_end", "set": self.id, "n": len(self.stats), "first_pass": first_pass,
                           "answers": self.answers})

    def summary(self):
        """끝 요약(설계 2.7). 상자 변화는 묶음을 시작할 때와 지금의 기록으로 셈."""
        state = self.sess._state()
        today = state.today
        up = same = down = 0
        first_today = again_day = early = 0
        for cid, st in self.stats.items():
            if not st["shown"]:
                continue
            before, after = self.before.get(cid), state.box(cid)
            if before is None or after is None or after == before:
                same += 1
            elif after > before:
                up += 1
            else:
                down += 1
            if st["first"] == "pass" and self.had_before[cid]:
                again_day += 1
                if self.before_due.get(cid) and self.before_due[cid] > today:
                    early += 1
            elif st["done"] and not self.had_before[cid]:
                first_today += 1
        sure_wrong = sum(1 for e in self.sess.record.log if e.get("kind") == "answer" and e.get("set") == self.id
                         and e.get("sure") and e.get("result") != "pass")
        memorised = families_memorised([self.sess.cards[c] for c in self.stats], state.sched) - self.memorised_before
        nexts = sorted(d for d in (state.due_day(c) for c in self.stats) if d is not None and d > today)
        upcoming = None
        if nexts:
            upcoming = {"date": nexts[0].isoformat(), "text": _md(nexts[0]), "count": nexts.count(nexts[0])}
        left = [cid for cid, st in self.stats.items() if st["left"]]
        return {"set": self.id, "mode": self.mode, "lesson": self.lesson, "unit": self.unit, "n": len(self.stats),
                "answers": self.answers, "first_today": first_today, "again_day": again_day, "up": up, "same": same,
                "down": down, "sure_wrong": sure_wrong, "memorised": max(0, memorised), "next": upcoming, "early": early,
                "left": left, "first_pass": sum(1 for st in self.stats.values() if st["first"] == "pass")}
