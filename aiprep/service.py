# -*- coding: utf-8 -*-
"""AI 비전 개론 서비스(설계 2.7~2.13). 화면은 AiSession 과 PracticeSet 만 부름. 반환은 dict·list, 오류는 사용자에게
그대로 보여 줄 AiError 임.

기록은 submissions/<ID>/ai/record.json 에 덧붙기만 하고(AiRecord), 상자·날짜·오늘 목표·오답 갈래는 기록에서 그때그때
계산해 (파일 mtime_ns, 크기, 줄 수, 학습일) 키로 캐시함. 학습 단원의 중간 자리(at_step)는 ~/.rokey-study/ai/<ID>/state.json
(STUDY_AI_HOME 으로 바꿈)에 둬서 제출에 들어가지 않음. 묶음은 secrets.randbelow 로 고른 시드 하나의 random.Random 으로 만들고
set 기록에 시드를 남겨 같은 기록·같은 시드면 같은 묶음이 나옴. 모의고사는 제출 전 답안을 로컬에만 두고 첫 제출의 오답을 복습에 넣음.

상황별 코드(index.json patterns, 무리 id pc)는 학습 노트(l18), 사실·검토 기록과 수치 생성기(items/pc)를 가짐. 코드 카드는
ai/patterns/S*.json 뼈대에서 skel.cards 가 만듦. 카드 lesson 은 무리 id, after 는 권하는 차시이고, 차시를 묻는 곳(정렬, 무게,
차시 풀기)은 after 차시를 씀. 단원 이름은 unit_name 한 규칙("5차시 · 단원 제목", "학습 루프 · 단원 제목")을 모든 화면값이 씀.
"""
import copy
import datetime
import hashlib
import json
import os
import random
import re
import secrets
import threading

import adaptive
import session
import study
from aiprep import bank, gen, grade, mixed_mock, mock, notes, plan, review, skel
from learning_data import collection
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
    메모리의 기록에 덧붙여 씀(4주 기록 1MB 안팎을 답마다 다시 읽지 않으려는 것). 파일 식별값과 변경 시각도 비교해서
    크기와 수정 시각이 같은 파일 교체를 감지함. 다른 창이나 문제 받기로 파일이 바뀌면
    지금처럼 다시 읽음."""

    def __init__(self, path, user, label=LABEL):
        self._data, self._key, self.reads = None, None, 0
        super().__init__(path, user, label)

    def stamp(self):
        try:
            info = os.stat(self.path)
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size, info.st_ino, info.st_ctime_ns)

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
    def __init__(self, user, home=None, root=None, course="intro"):
        """은행과 record.json 을 읽음. index.json·terms.json 이나 기록이 깨졌으면 AiError. 차시 하나가 깨지면 그 차시만 빼고
        errors 에 이유를 둠."""
        if not session.valid_user(user):
            raise AiError("ID 가 올바르지 않습니다: %r" % (user,))
        if course not in bank.COURSES:
            raise AiError("학습 과정을 찾을 수 없습니다.")
        self.course = course
        self.user = user
        self.root = root or bank.AI_DIR
        self.folder = os.path.join(study.SUBMISSIONS_DIR, user, "ai")
        self.home = os.path.join(home or home_dir(), user)
        self.mock_home = self.home
        self.collection = collection.Collection(self.home, study.ROOT)
        try:
            self.collection.initialize_distribution()
        except collection.CollectionError as error:
            self.collection.error = str(error)
        if course != "intro":
            self.home = os.path.join(self.home, course)
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
        self.mock_lessons = {e["id"]: e for e in self.index["lessons"]}
        pending_mocks, accepted_mocks = {}, []
        for spec in self.index["mocks"]:
            if mixed_mock.candidate(spec):
                try:
                    mixed_mock.validate(spec, study.read_json(os.path.join(bank.mock_dir(spec["id"], self.root), "meta.json")))
                except (OSError, ValueError, TypeError) as error:
                    pending_mocks[spec["id"]] = str(error)
                    continue
            elif course != "intro":
                continue
            accepted_mocks.append(spec)
        self.index["mocks"] = accepted_mocks
        if os.path.isfile(os.path.join(bank.mock_dir("m4", self.root), "meta.json")) and not any(m["id"] == "m4" for m in accepted_mocks):
            pending_mocks.setdefault("m4", "혼합 모의고사의 문항 검토와 목록 연결을 준비하고 있습니다.")
        self.index["lessons"] = [e for e in self.index["lessons"] if e["course"] == course]
        if course != "intro":
            self.index["patterns"] = []
            self.index["exam"] = {}
        self.exam = review.exam_dates(self.index["exam"])
        self.term_map = grade.term_map(self.terms)
        self.collection_terms_revision = collection.digest(self.terms)
        self.lessons = {e["id"]: e for e in self.index["lessons"]}
        self.mocks = {e["id"]: e for e in self.index["mocks"]}
        self.notes, self.items, self.cards, self.errors = {}, {}, {}, {}
        self.errors.update(pending_mocks)
        self.mock_pending = pending_mocks
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
        self.patterns = {g["id"]: g for g in self.index["patterns"]}
        self.skeletons = {}
        try:
            self.skeletons = skel.load_patterns(self.root)
        except bank.AiBankError as error:
            self.errors["patterns"] = str(error)
        for group in self.index["patterns"]:
            if bank.pattern_ready(group, self.root):
                self._load_pattern(group)
        self._cache_key, self._cache = None, None
        self._index, self._index_log = None, None
        self._gen_kind = {}
        self._content_versions_cache = None
        self._card_versions_cache = None
        self._active_set = None
        self._mock_loaded = set()
        self._mock_exams = {}
        self._recover_mocks()

    def resume_course(self):
        """자료는 재사용하고 다른 과정에서 바뀐 기록·연습·모의고사를 다시 읽음."""
        self._content_versions_cache = None
        self._cache_key, self._index = None, None
        self._active_set = None
        for key in ("card_versions", *self.mocks):
            self.errors.pop(key, None)
        self._state()
        self._mock_exams.clear()
        self._recover_mocks()

    def _recover_mocks(self):
        """미제출 회차를 먼저 보관함. 만료 회차는 홈을 그리기 전에 제출하며 실패하면 다음 tick에서 다시 시도함."""
        done = {(row.get('mock'), int(row.get('try') or 1)) for row in self.record.log if row.get('kind') == 'mock_submit'}
        starts = {}
        for row in self.record.log:
            if row.get('kind') == 'mock_start':
                starts[row.get('mock')] = row
        for mid, row in starts.items():
            if mid not in self.mocks or (mid, int(row.get('try') or 1)) in done:
                continue
            try:
                self.start_mock(mid, _submit_expired=False)
            except AiError as error:
                self.errors[mid] = str(error)
        self.expire_mocks()

    def expire_mocks(self):
        """열지 않은 회차도 시간이 다 됐으면 제출함. 화면 ticker가 부름."""
        for mid, exam in self._mock_exams.items():
            if exam.result is None and exam.remaining() == 0:
                try:
                    exam.submit(auto=True)
                    self.errors.pop(mid, None)
                except mock.MockError as error:
                    self.errors[mid] = str(error)

    def mock_info(self, mid):
        """시작 전 안내용 회차 정보. 이 조회는 시작 기록을 만들지 않음."""
        if mid not in self.mocks:
            raise AiError('모의고사를 찾을 수 없습니다.')
        try:
            items, fingerprint = mock.load_items(self.root, self.mocks[mid], self.mock_lessons)
            rows = mock.submissions(self.record.reload(), mid)
        except (mock.MockError, record.RecordError) as error:
            raise AiError(str(error)) from error
        exam = self._mock_exams.get(mid)
        latest = next((row for row in reversed(self.record.log) if row.get("kind") == "mock_start" and row.get("mock") == mid), None)
        restart_required = (latest is not None and latest.get("fingerprint") != fingerprint
                            and not any(int(row.get("try") or 1) == int(latest.get("try") or 1) for row in rows))
        return dict(self.mocks[mid], blanks=sum(item['kind'] == 'blank' for item in items.values()),
                    choices=sum(item['kind'] == 'choice' for item in items.values()), taken=bool(rows),
                    restart_required=restart_required,
                    first_score=rows[0]['score'] if rows else None, last_score=rows[-1]['score'] if rows else None,
                    active=exam is not None and exam.result is None,
                    remaining=exam.remaining() if exam is not None and exam.result is None else None)

    def mock_state(self, mid):
        """홈에 보일 진행 상태. 회차의 문항을 다시 읽거나 새 풀이를 시작하지 않음."""
        self._state()
        first = self._index.mocks.get(mid)
        exam = self._mock_exams.get(mid)
        active = exam is not None and exam.result is None
        return {'first_score': first['score'] if first else None, 'active': active,
                'remaining': exam.remaining() if active else None, 'error': self.errors.get(mid, '')}

    def _load_mock_reviews(self):
        """첫 제출에서 틀리거나 비운 문항만 복습 카드로 읽음. 미제출 회차의 문항은 연습에 넣지 않음."""
        for mid, row in self._index.mocks.items():
            if mid in self._mock_loaded or mid not in self.mocks:
                continue
            try:
                items, fingerprint = mock.load_items(self.root, self.mocks[mid], self.mock_lessons)
                if row.get('fingerprint') != fingerprint:
                    raise mock.MockError('제출한 뒤 문제 자료가 바뀌었습니다. 이전 결과와 답안은 보존했습니다.')
                cards = bank.cards_of({'id': mid}, {'items': list(items.values()), 'topics': [], 'gens': []})
                for card in cards:
                    if mixed_mock.candidate(self.mocks[mid]) and card["item"]["course"] != self.course:
                        continue
                    if row.get('results', {}).get(card['id']) not in ('stuck', 'blank', 'partial'):
                        continue
                    card['mock'], card['after'] = mid, card['item'].get('lesson')
                    self.cards[card['id']] = card
            except mock.MockError as error:
                self.errors[mid] = str(error)
            self._mock_loaded.add(mid)

    def _load_pattern(self, group):
        """상황별 코드 무리 하나를 읽음. 학습 노트, 사실·검토 기록과 수치 생성기, 공개 단원의 뼈대 카드.
        카드마다 시드 1 문항을 한 번 만들어 보고, 깨진 뼈대면 그 무리를 빼고 errors 에 이유를 둠."""
        gid = group["id"]
        try:
            note = bank.load_note({"id": group["page"], "title": group["title"]}, self.root)
            data = bank.load_items({"id": gid}, self.root)
            units = {key: {"after": info["after"], "name": info["name"], "title": note["units"][key]["title"]}
                     for key, info in group["units"].items() if key in note["visible"]}
            made = skel.cards(group, self.skeletons, units)
            for card in made:
                if card["pattern"] not in self.skeletons:
                    raise bank.AiBankError("뼈대 %s 를 찾을 수 없습니다." % card["pattern"])
                skel.view(card, self.skeletons[card["pattern"]], 1)
            generated = bank.pattern_gen_cards(group, data, units)
            for card in generated:
                gen.run(card["gen"], 1)
            made.extend(generated)
        except bank.AiBankError as error:
            self.errors[gid] = str(error)
            return
        except (gen.GenError, KeyError, TypeError, ValueError, AttributeError, IndexError) as error:
            self.errors[gid] = "뼈대 카드를 만들 수 없습니다: %s" % error
            return
        self.notes[gid], self.items[gid] = note, data
        for card in made:
            self.cards[card["id"]] = card

    # 자리와 단원 이름

    def place(self, lid):
        """차시나 상황별 코드 무리의 자리. {"id", "kind": "lesson"|"pattern", "no"(무리는 None), "label"("5차시"|"상황별 코드"),
        "title"("5차시 경사하강법 구현"|"상황별 코드"), "back"("lesson"|"home", 학습 단원 화면의 뒤로 가기)}. 모르는 id 는 AiError."""
        if lid in self.lessons:
            entry = self.lessons[lid]
            return {"id": lid, "kind": "lesson", "no": entry["no"], "label": self.lesson_label(entry),
                    "title": "%s %s" % (self.lesson_label(entry), entry["title"]), "back": "lesson"}
        if lid in self.patterns:
            title = self.patterns[lid]["title"]
            return {"id": lid, "kind": "pattern", "no": None, "label": title, "title": title, "back": "home"}
        raise AiError("차시를 찾을 수 없습니다: %s" % lid)

    def lesson_label(self, entry):
        return ("응용 %d차시" if entry.get("course") == "app" else "%d차시") % entry["no"]

    def course_log(self):
        """원본 기록을 보존하고 현재 과정의 계산용 줄만 고름."""
        return [row for e in self.record.log if (row := mixed_mock.course_entry(e, self.course)) is not None]

    def unit_name(self, lid, key):
        """단원 이름 한 규칙. 차시는 "5차시 · 단원 제목", 상황별 코드는 "학습 루프 · 단원 제목"(index 단원 name). 단원 제목을
        모르면(공개 전) 차시는 "5차시 · ", 상황별 코드는 name 만."""
        note = self.notes.get(lid)
        title = note["units"][key]["title"] if note is not None and key in note["units"] else ""
        if lid in self.patterns:
            name = self.patterns[lid]["units"].get(key, {}).get("name", "")
            return "%s · %s" % (name, title) if name and title else (name or title)
        entry = self.lessons.get(lid)
        if lid in self.mocks:
            return self.mocks[lid]['title']
        return "%s · %s" % (self.lesson_label(entry), title) if entry else title

    def _home(self, card):
        """카드의 차시 index 항목. 차시 카드는 그 차시, 상황별 코드 카드는 권하는 차시(after). 없으면 맨 뒤 차시처럼 둠."""
        entry = self.lessons.get(card["lesson"]) or self.lessons.get(card.get("after") or "")
        return entry or {"id": "", "no": 999, "weight": 1.0, "title": "", "date": ""}

    # 날짜와 캐시

    def today(self):
        return _today()

    def _card_versions(self):
        """자료가 같은 세션에서는 문항 본문·용어의 해시를 재사용함."""
        if self._card_versions_cache is not None:
            return self._card_versions_cache
        versions, sources = {}, {}
        metadata = {"order", "ref", "errata", "prio", "core", "deep", "level", "tags", "facts", "step",
                    "unit", "family", "confuse", "after"}
        def content_only(value):
            if isinstance(value, dict):
                return {key: content_only(item) for key, item in value.items() if key not in metadata}
            if isinstance(value, (list, tuple)):
                return [content_only(item) for item in value]
            return value
        for cid, card in self.cards.items():
            if card.get("mock"):
                continue
            content = dict(card)
            content.pop("gen", None)
            source_text = []
            if card["kind"] == "gen":
                spec = card["gen"]
                hashes = []
                for source in (spec.path, os.path.join(self.root, "items", "common", "gens.py")):
                    if source not in sources:
                        try:
                            with open(source, "rb") as stream:
                                raw = stream.read()
                            sources[source] = hashlib.sha256(raw).hexdigest(), raw.decode("utf-8", errors="replace")
                        except OSError:
                            sources[source] = None, ""
                    checksum, text = sources[source]
                    hashes.append(checksum)
                    source_text.append(text)
                content["generator"] = {"id": spec.id, "meta": spec.meta, "doc": spec.doc, "sources": hashes}
            if card["kind"] == "skel":
                content["skeleton"] = self.skeletons.get(card["pattern"])
            content = content_only(content)
            text = grade.norm("word", collection.packed(content) + " ".join(source_text))
            terms = {key: sorted(values) for key, values in self.term_map.items() if key in text}
            versions[cid] = collection.digest({"card": content, "terms": terms})
        self._card_versions_cache = versions
        return versions

    def _content_versions(self):
        """현재 문항과 이전에 관찰한 문항을 대조함. 원래 답 기록은 바꾸지 않음."""
        with self._lock:
            if self._content_versions_cache is not None:
                return self._content_versions_cache
            path = os.path.join(self.home, "content-versions.json")
            writable = True
            try:
                local = study.read_json(path) if os.path.exists(path) else {}
                if not isinstance(local, dict):
                    raise ValueError("local state")
            except (OSError, ValueError):
                local, writable = {}, False
                self.errors["card_versions"] = "문항 변경 기록을 읽지 못했습니다. 원본을 보관하고 스터디장에게 알려 주세요."
            saved = local.get("card_versions", {})
            saved = saved if isinstance(saved, dict) else {}
            versions, revised = self._card_versions(), set()
            for cid, revision in versions.items():
                previous = saved.get(cid, {})
                if isinstance(previous, dict) and (previous.get("changed") or previous.get("revision") not in (None, revision)):
                    revised.add(cid)
            for entry in self.course_log():
                cid, revision = entry.get("card"), entry.get("content_revision")
                if cid in versions and revision is not None and revision != versions[cid]:
                    revised.add(cid)
                for other, revision in (entry.get("content_revisions") or {}).items():
                    if other in versions and revision is not None and revision != versions[other]:
                        revised.add(other)
            updated = dict(saved)
            updated.update({cid: {"revision": revision, "changed": cid in revised} for cid, revision in versions.items()})
            if updated != saved and writable:
                local["card_versions"] = updated
                try:
                    study.write_text(path, json.dumps(local, ensure_ascii=False, indent=1) + "\n")
                except OSError:
                    self.errors["card_versions"] = "문항 변경 정보를 저장하지 못했습니다. 이 컴퓨터의 저장 공간과 폴더 권한을 확인해 주세요."
            self._content_versions_cache = versions, revised
            return versions, revised

    def _state(self):
        """기록에서 계산한 값 묶음. 기록과 학습일이 바뀌지 않았으면 다시 계산하지 않음."""
        with self._lock:
            try:
                self.record.reload()
            except record.RecordError as error:
                raise AiError(str(error))
            log = self.record.log
            versions, revised = self._content_versions()
            if self._index is None or self._index_log is not log or self._index.n > len(log):
                self._index, self._index_log = _LogIndex(self.course, versions, revised), log  # 파일을 다시 읽었으면 처음부터
                self.cards = {cid: card for cid, card in self.cards.items() if not card.get('mock')}
                self._mock_loaded.clear()
            self._index.feed(log[self._index.n:])
            self._load_mock_reviews()
            key = (self.record.version, self.today())
            if key == self._cache_key and self._cache is not None:
                return self._cache
            state = _State(self, self._index, key[1])
            self._cache_key, self._cache = key, state
            return state

    # 학습 단원

    def _lesson(self, lid):
        if lid in self.patterns:
            group = self.patterns[lid]
            if lid in self.errors:
                raise AiError("%s를 읽을 수 없습니다. %s" % (group["title"], self.errors[lid]))
            if lid not in self.notes:
                raise AiError("%s는 아직 준비 중입니다." % group["title"])
            return {"id": lid, "no": None, "title": group["title"], "page": group["page"], "date": ""}
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

    def _skel_block(self, block):
        """ai-diff·ai-rotate 블록에 채울 값. diff 는 skel.diff 결과, rotate 는 skel.rotate_block 결과(code, slots). 모르는 뼈대·코드 예제·
        자리면 {"error"}."""
        skeleton = self.skeletons.get(str(block.get("skel")))
        if skeleton is None:
            return {"error": "뼈대를 찾을 수 없습니다: %s" % block.get("skel")}
        try:
            if block["kind"] == "diff":
                return skel.diff(skeleton, block.get("left"), block.get("right"))
            slots = block.get("slots")
            return skel.rotate_block(skeleton, block.get("variant"), slots if isinstance(slots, list) else None)
        except bank.AiBankError as error:
            return {"error": str(error)}

    def _blocks(self, lid, key, step, state):
        """단계 블록을 화면용으로. guess 는 답을 빼고 고른 번호를, reveal 은 짐작한 답과 정답을, figure 는 파일 경로를, diff 는
        두 코드 예제의 행을, rotate 는 예제 코드와 자리마다 그 자리만 가린 코드를 채움."""
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
            elif block["kind"] in ("diff", "rotate") and not block.get("error"):
                block.update(self._skel_block(block))
            out.append(block)
        return out

    def unit_steps(self, lid, key):
        """학습 단원의 단계. {"lesson", "unit", "title", "name"(단원 이름), "steps": [{"no", "title", "scope", "facts", "blocks"}],
        "at_step"}."""
        unit = self._unit(lid, key)
        state = self._state()
        steps = [{"no": s["no"], "title": s["title"], "scope": s["scope"], "facts": list(s["facts"]),
                  "blocks": self._blocks(lid, key, s, state)} for s in unit["steps"]]
        at = self._local().get("at_step", {}).get("%s/%s" % (lid, key))
        return {"lesson": lid, "unit": key, "title": unit["title"], "name": self.unit_name(lid, key), "steps": steps, "at_step": at}

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
        외울 것 블록만 가짐. 맨 위 leeches 는 이 차시의 자주 틀리는 카드 id. 상황별 코드는 단원 화면에서만 열어 AiError."""
        if lid in self.patterns:
            raise AiError("%s는 단원 화면에서 엽니다." % self.patterns[lid]["title"])
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
        """다시 볼 단원. {"lesson", "unit", "title", "name"(단원 이름), "figure", "figure_info", "memo"} 이나 없으면 None."""
        state = self._state()
        found = state.revisit_pick()
        if found is None:
            return None
        lid, key = found["lesson"], found["unit"]
        unit = self.notes[lid]["units"][key]
        meta = self.notes[lid]["unit_meta"].get(key, {})
        figure, figure_info = None, None
        figures = [block for step in unit["steps"] for block in step["blocks"] if block["kind"] == "figure"]
        if meta.get("key_figure"):
            figure = os.path.join(self.notes[lid]["dir"], *str(meta["key_figure"]).split("/"))
            figure_info = next((block for block in figures
                                if os.path.normpath(block["path"]) == os.path.normpath(figure)), None)
        elif figures:
            figure_info = figures[0]
            figure = figure_info["path"]
        memo = [item for step in unit["steps"] for b in step["blocks"] if b["kind"] == "memo" for item in b.get("items", [])]
        return {"lesson": lid, "unit": key, "title": unit["title"], "name": self.unit_name(lid, key), "figure": figure,
                "figure_info": dict(figure_info) if figure_info else None, "memo": memo}

    # 기록

    def collect_event(self, kind, data, item=None, key=None, at=None, *, observation_context=collection.CURRENT_CONTEXT, _mock_exam=None):
        """동의한 뒤의 추가 데이터만 저장함. 과거 제출 기록은 가져오지 않음."""
        if not os.path.exists(self.collection.path):
            return
        try:
            status = self.collection.status()
            if status["enabled"]:
                observed_course = self.course
                if _mock_exam is not None:
                    observed_course = mixed_mock.collection_course(_mock_exam, self, kind, data)
                    data = dict(data, scope="mixed")
                    data.update(seed=_mock_exam.draft["seed"], blueprint_revision=_mock_exam.spec["blueprint_revision"])
                    if data.get("card"):
                        item = _mock_exam.collection_item(data["card"])
                        data["course_no"] = self.mock_lessons[_mock_exam.items[data["card"]]["lesson"]]["no"]
                elif data.get("scope") == "mixed":
                    data = {k: v for k, v in data.items() if k != "scope"}
                data = dict(data, course=observed_course)
                item = item() if callable(item) else item
                if item is not None:
                    item = copy.deepcopy(item)
                    content = item["content"]
                    content["course"] = observed_course
                    entries = self.mock_lessons if _mock_exam is not None else self.lessons
                    content["course_no"] = entries.get(content.get("lesson"), {}).get("no")
                    item["revision"] = collection.digest({"revision": item["revision"], "course": observed_course,
                                                          "course_no": content["course_no"]})
                self.collection.emit(kind, data, item, key=key, at=at,
                                     observation_context=observation_context)
            elif status["error"]:
                self.collection.emit(kind, data, key=key, at=at, observation_context=observation_context)
        except (ValueError, KeyError, TypeError, OSError, collection.CollectionError) as error:
            self.collection.error = "추가 학습 데이터의 문항 정보를 저장하지 못했습니다. %s" % error
            self.collection.missed += 1

    def _collect_mixed_record(self, exam, row, *, observation_context=collection.CURRENT_CONTEXT):
        """회차의 묶음 공개를 과정별 집계로 나누고 같은 공개 시각을 유지함."""
        for course in exam.spec["courses"]:
            data = {k: v for k, v in row.items() if k != "at"}
            data["course"] = course
            if row["kind"] == "mock_submit":
                data["results"] = {cid: result for cid, result in row["results"].items() if exam.items[cid]["course"] == course}
                data.update(of=len(data["results"]), score=sum(v == "pass" for v in data["results"].values()), related=[])
                data["omitted_before_consent"] = sum(i["course"] == course for i in exam.items.values()) - len(data["results"])
            key = "mixed-record:%s:%d:%s:%s:%s" % (exam.id, exam.attempt, exam.fingerprint, row["kind"], course)
            self.collect_event(row["kind"], data, key=key, at=row["at"], observation_context=observation_context, _mock_exam=exam)

    def _collect_record(self, row, private=None, item=None, *, observation_context=collection.CURRENT_CONTEXT):
        data = {key: value for key, value in row.items() if key not in ("at", "value", "picked", "also_value", "content_revision", "content_revisions")}
        response = {key: row[key] for key in ("value", "picked", "also_value") if key in row}
        if response:
            data["response"] = response
        data.update(private or {})
        key = "record:%d:%s" % (len(self.record.log), collection.digest(row))
        self.collect_event(row["kind"], data, item=item, key=key, at=row.get("at"), observation_context=observation_context)

    def _append(self, entry, private=None, item=None):
        try:
            entry = dict(entry)
            if entry.get("kind") == "answer":
                versions, _ = self._content_versions()
                entry["content_revision"] = versions.get(entry.get("card"))
                entry["content_revisions"] = {cid: versions[cid] for cid in entry.get("also") or {} if cid in versions}
            if self.course != "intro":
                entry["course"] = self.course
            row = self.record.append(entry, now())
        except record.RecordError as error:
            raise AiError(str(error))
        self._collect_record(row, private=private, item=item)
        return row

    def mark_read(self, lid, key):
        """마지막 단계에서 연습 시작을 누르면 기록함. 단원 연습 완료와 외운 문항 수는 따로 셈."""
        self._unit(lid, key)
        return self._append({"kind": "learn", "lesson": lid, "unit": key})

    def save_revisit(self, lid, key):
        self._unit(lid, key)
        return self._append({"kind": "revisit", "lesson": lid, "unit": key})

    def save_guess(self, lid, key, gid, picked):
        unit = self._unit(lid, key)
        block = next((b for step in unit["steps"] for b in step["blocks"] if b["kind"] == "guess" and str(b.get("id")) == str(gid)), None)
        item = (lambda: collection.question({"stem": block.get("q", ""), "options": [{"text": text} for text in block["options"]]},
                                            lesson=lid, unit=key, terms_revision=self.collection_terms_revision)) if block else None
        return self._append({"kind": "guess", "lesson": lid, "unit": key, "id": str(gid), "picked": int(picked)}, item=item)

    def save_recall(self, lid, key, rid, ok, level=None, value=None, block=None):
        """떠올리기 결과 한 줄. level 은 세 수준 블록의 확인 물음일 때 수준(7·15·20)이고 기록에 "level" 로 남음."""
        self._unit(lid, key)
        entry = {"kind": "recall", "lesson": lid, "unit": key, "id": str(rid), "ok": bool(ok)}
        if level is not None:
            entry["level"] = int(level)
        item = (lambda: collection.question(dict(block, stem=block.get("q", "")), lesson=lid, unit=key,
                                            terms_revision=self.collection_terms_revision)) if block else None
        return self._append(entry, private={"response": value}, item=item)

    def check_rotate(self, lid, key, rid, slot, value, readonly=False):
        """돌려 가며 빈칸 한 자리를 채점함. 그 자리만 가린 예제 코드를 지문으로 둔 한 칸 문항을 grade_item 으로 채점해 연습과 같은
        문맥 떼기를 씀. readonly 가 아니면 {"kind": "recall", "lesson", "unit", "id", "slot", "ok"} 를 한 번 기록하고 상자는
        움직이지 않음. {"ok", "answer"(첫 답), "explain"(같은 자리의 기존 해설)}. 모르는 블록·자리면 AiError."""
        unit = self._unit(lid, key)
        block = next((b for s in unit["steps"] for b in s["blocks"] if b["kind"] == "rotate" and str(b.get("id")) == str(rid)), None)
        if block is None or block.get("error"):
            raise AiError("돌려 가며 빈칸을 찾을 수 없습니다: %s" % rid)
        made = self._skel_block(block)
        if made.get("error"):
            raise AiError(made["error"])
        spot = next((s for s in made["slots"] if s["id"] == slot), None)
        if spot is None:
            raise AiError("돌려 가며 빈칸에 없는 자리입니다: %s" % slot)
        entry = skel.entry_of(self.skeletons[str(block["skel"])], "slot", slot)
        answers = [str(a) for a in entry.get("answer") or []]
        item = {"stem": "```python\n%s\n```" % spot["code"], "blanks": [{"answer": answers, "mode": spot["mode"]}]}
        ok = grade.grade_item(item, [value], self.term_map)["result"] == "pass"
        if not readonly:
            self._append({"kind": "recall", "lesson": lid, "unit": key, "id": str(rid), "slot": str(slot), "ok": ok},
                         private={"response": value}, item=lambda: collection.question(item, lesson=lid, unit=key, slot=slot,
                                                                                     terms_revision=self.collection_terms_revision))
        return {"ok": ok, "answer": answers[0] if answers else "", "explain": str(entry.get("explain") or "")}

    def check_recall(self, block, value):
        """떠올리기 칸 하나를 채점함(기록은 save_recall 이 함). block 은 unit_steps 의 recall 블록이나 세 수준 블록의 수준 하나이고
        places·unit 이 있으면 같이 넘김."""
        return grade.grade_blank({"answer": block.get("answer") or [], "mode": block.get("mode") or "word",
                                  "places": block.get("places"), "unit": block.get("unit")}, value, self.term_map)

    def _local(self):
        path = os.path.join(self.home, "state.json")
        try:
            data = study.read_json(path)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        steps = data.get("at_step")
        data["at_step"] = {k: v for k, v in steps.items() if type(v) is int} if isinstance(steps, dict) else {}  # 손댄 파일에 막히지 않게
        return data

    def save_step(self, lid, key, step):
        """학습 단원 중간 자리(로컬 state.json, 제출에 들어가지 않음)."""
        data = self._local()
        data.setdefault("at_step", {})["%s/%s" % (lid, key)] = int(step)
        data["last_unit"] = [lid, key]
        data["continuation"] = {"kind": "unit", "lesson": lid, "unit": key, "at": now()}
        self._save_local(data)

    def _save_local(self, data):
        """제출 기록과 분리한 중간 상태를 저장함. 기존 키는 남김."""
        try:
            study.write_text(os.path.join(self.home, "state.json"), json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        except OSError:
            return False  # 중간 자리는 편의라 못 써도 학습은 이어감
        return True

    def completed_units(self):
        """끝낸 단원 연습 묶음을 셈. 읽기 기록이나 마지막 단계 진입으로 완료를 추정하지 않음."""
        return set(self._state().practice_completed)

    def continuation(self):
        """로컬의 마지막 학습 자리나 미완료 연습을 돌려줌. 예전 at_step과 제출 기록을 덮어쓰지 않음."""
        self._state()
        data = self._local()
        cursor = data.get("continuation")
        cursor = cursor if isinstance(cursor, dict) else {}
        if cursor.get("kind") == "practice":
            practice = self.resume_set()
            if practice is not None:
                return {"kind": "practice", "lesson": practice.lesson, "unit": practice.unit, "mode": practice.mode,
                        "card": practice.card, "title": practice.title, "count": len(practice.queue), "at": cursor.get("at")}
        rows = []
        for entry in self.index["lessons"]:
            lid = entry["id"]
            if lid in self.notes:
                rows += [dict(u, lesson=lid, unit=u["key"], no=entry["no"], order=i, name=self.unit_name(lid, u["key"]))
                         for i, u in enumerate(self.unit_list(lid))]
        for lid in self.patterns:
            if lid in self.notes:
                group = self.patterns[lid]
                for u in self.unit_list(lid):
                    meta = group["units"].get(u["key"])
                    if meta is None:
                        continue
                    after = self.lessons.get(meta["after"])
                    rows.append(dict(u, lesson=lid, unit=u["key"], no=after["no"] if after else 999,
                                     order=100 + list(group["units"]).index(u["key"]), name=self.unit_name(lid, u["key"])))
        valid = {(r["lesson"], r["unit"]) for r in rows}
        saved = data.get("last_unit")
        last = tuple(saved) if isinstance(saved, list) and len(saved) == 2 and all(isinstance(v, str) for v in saved) else None
        if last not in valid:
            candidates = [tuple(k.split("/")) for k in data.get("at_step", {}) if len(k.split("/")) == 2]
            last = next((key for key in reversed(candidates) if key in valid), None)
        if last is None:
            last = next(((e.get("lesson"), e.get("unit")) for e in reversed(self.record.log)
                         if (e.get("lesson"), e.get("unit")) in valid), None)
        completed = self.completed_units()
        if cursor.get("kind") == "unit":
            completed.discard(last)  # 완료한 단원을 직접 다시 읽는 중이면 그 자리를 이어 엶
        target = plan.continue_unit(rows, last, completed)
        if target is None:
            return {"kind": "none", "at": cursor.get("at")}
        target = dict(target, kind="unit", at=cursor.get("at"))
        target["step"] = max(1, min(target["steps"], data.get("at_step", {}).get("%s/%s" % (target["lesson"], target["unit"]), 1)))
        target["resuming"] = (target["lesson"], target["unit"]) == last
        return target

    def resume_set(self, mode=None, lesson=None, unit=None, card=None):
        """미완료 묶음을 기록 추가 없이 복원함. 문항이나 답 기록이 달라졌으면 복원하지 않음."""
        saved = self._local().get("practice")
        if not isinstance(saved, dict):
            return None
        args = (saved.get("mode"), saved.get("lesson"), saved.get("unit"), saved.get("card"))
        if mode is not None and args != (mode, lesson, unit, card):
            return None
        self._state()
        rows = [e for e in self.record.log if e.get("set") == saved.get("id")]
        if saved.get("set_records") != rows:
            return None
        if self._active_set is not None and self._active_set.id == saved.get("id"):
            return None if self._active_set.ended else self._active_set
        try:
            practice = PracticeSet.restore(self, saved)
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        self._active_set = practice
        return practice

    def save_practice(self, practice, activate=False):
        """현재 묶음과 입력 초안을 로컬에 저장함. 숨길 때 저장한 초안으로 새 학습 자리를 덮지 않음."""
        if self._active_set is not practice:
            return
        data = self._local()
        data["practice"] = practice.snapshot()
        if activate:
            data["continuation"] = {"kind": "practice", "at": now()}
            if practice.lesson and practice.unit:
                data["last_unit"] = [practice.lesson, practice.unit]
        return self._save_local(data)

    # 카드

    def card_form(self, card, box):
        """카드가 이번에 나올 꼴(blank·choice). 문장 카드는 상자 2 이상이고 cloze 가 있으면 빈칸판."""
        kind = card["kind"]
        if kind in ("blank", "choice"):
            return kind
        if kind == "stmt":
            return "blank" if (box or 0) >= 2 and card["stmt"].get("cloze") else "choice"
        if kind == "skel":
            return "blank" if card["part"] == "slot" else "choice"
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

    def note_target(self, cid):
        """실제로 공개된 학습 단계만 참고 대상으로 돌려줌. 외부 자료 위치는 포함하지 않음."""
        self._state()
        card = self.cards.get(cid)
        if card is None:
            return None
        lid = card.get("after") if card.get("mock") else card.get("lesson")
        note = self.notes.get(lid)
        found = re.fullmatch(r"(a?[0-9]{1,2}[a-i])/([1-9][0-9]*)", str(card.get("step") or ""))
        if note is None or found is None:
            return None
        key, number = found.group(1), int(found.group(2))
        if key not in note["visible"] or not any(s["no"] == number for s in note["units"][key]["steps"]):
            return None
        return {"lesson": lid, "step": "%s/%d" % (key, number), "label": "%s %d단계" % (self.unit_name(lid, key), number)}

    # 연습

    def review_status(self):
        """자동 복습 후보 유무와 다음 복습 날짜를 돌려줌. 기록은 남기지 않음."""
        return self._state().review_status()

    def start_mock(self, mid, repeat=False, seed=None, clock=None, monotonic=None, _submit_expired=True):
        """회차를 시작하거나 로컬 초안을 이어 엶. 제출한 회차는 결과를 열고 repeat이면 새 풀이를 시작함."""
        try:
            if mid in self.mocks and mixed_mock.candidate(self.mocks[mid]):
                with mixed_mock.lock(self, mid):
                    _, fingerprint = mock.load_items(self.root, self.mocks[mid], self.mock_lessons)
                    exam = mixed_mock.cached(self, mid)
                    starts = [r for r in self.record.reload() if r.get("kind") == "mock_start" and r.get("mock") == mid]
                    latest = max((int(r.get("try") or 1) for r in starts), default=0)
                    if repeat or exam is None or exam.fingerprint != fingerprint or exam.attempt != latest:
                        exam = mock.MockExam(self, mid, repeat=repeat, seed=seed, clock=clock or (lambda: now()),
                                             monotonic=monotonic, submit_expired=_submit_expired)
                        mixed_mock.remember(self, exam)
                    self._mock_exams[mid] = exam
                    self.errors.pop(mid, None)
                    return exam
            if not repeat and mid in self._mock_exams:
                return self._mock_exams[mid]
            exam = mock.MockExam(self, mid, repeat=repeat, seed=seed, clock=clock or (lambda: now()), monotonic=monotonic,
                                 submit_expired=_submit_expired)
            self._mock_exams[mid] = exam
            self.errors.pop(mid, None)
            return exam
        except mock.MockError as error:
            raise AiError(str(error)) from error

    def start_set(self, mode, lesson=None, unit=None, mock=None, card=None, seed=None):
        """연습 묶음을 만들고 set 기록을 남김. 카드가 하나도 없으면 AiError."""
        if mode not in MODES:
            raise AiError("모르는 연습 모드입니다: %s" % mode)
        if mode == "lesson":
            if lesson in self.patterns:
                raise AiError("%s는 단원마다 풉니다." % self.patterns[lesson]["title"])
            self._lesson(lesson)
            if lesson not in self._state().opened:
                self._append({"kind": "open", "lesson": lesson})
        if mode == "unit" or (mode == "mixed" and unit):
            self._unit(lesson, unit)
        if mode == "note" and card is None:
            raise AiError("다시 풀 문항을 골라 주세요.")
        seed = int(seed) if seed is not None else secrets.randbelow(2 ** 31)
        state = self._state()
        selection = {}
        picked = build_set(self, state, mode, random.Random(seed), lesson=lesson, unit=unit, card=card, trace=selection)
        if not picked:
            if mode in ("review", "sweep"):
                raise AiError("지금 복습할 문항이 없습니다.")
            raise AiError("지금 풀 문항이 없습니다. 단원을 먼저 읽어 주세요.")
        day = state.today
        count = sum(1 for e in self.record.log if e.get("kind") == "set" and review.study_day(e.get("at")) == day)
        set_id = "s%s-%d" % (day.strftime("%Y%m%d"), count + 1)
        entry = {"kind": "set", "set": set_id, "mode": mode, "n": len(picked), "seed": seed}
        for name, value in (("lesson", lesson), ("unit", unit), ("card", card)):
            if value:
                entry[name] = value
        self._append(entry, private={"selection": selection})
        practice = PracticeSet(self, set_id, mode, picked, seed, lesson=lesson, unit=unit)
        practice.card = card
        self._active_set = practice
        self.save_practice(practice, activate=True)
        return practice

    def title_of(self, mode, lesson=None, unit=None):
        """연습 화면 제목(설계 2.6)."""
        if mode == "unit" and lesson in self.notes and unit in self.notes[lesson]["units"]:
            return self.unit_name(lesson, unit)
        if mode == "lesson" and lesson in self.lessons:
            return "%s 풀기" % self.lesson_label(self.lessons[lesson])
        return MODE_TITLE.get(mode, "연습")

    # 오답 노트

    def wrong_notes(self):
        """[{"title", "items": [{"key", "label", "state", "sure", "leech", "deep", ...}]}]."""
        return self._state().notes()[0]

    def read_today(self, key):
        """그 카드의 단원을 오늘 처음 읽었는지. 그날의 오답은 오답 노트에 넣지 않음."""
        state = self._state()
        return state.read_day(key) == state.today

    def wrong_counts(self):
        return self._state().notes()[1]

    def wrong_item(self, key):
        """오답 노트 문항 하나. {"key", "title", "name"(카드 단원 이름), "lines"(결과 줄), "stem", "kind", "pick", "options"(원래 순서),
        "code_options"(보기가 코드인지), "mine"(내 답 글 목록 또는 None), "ref", "lesson", "step"}. 뼈대 카드는 기록의
        seed·masked·whole·back 으로 같은 문항을 다시 만들고, 함께 가린 칸으로만 틀린 자리는 그 칸에 쓴 글을 내 답으로 보임."""
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
        view = self._static_view(card, last)
        mine = None
        if last is not None:
            if "value" in last:
                mine = [str(v) for v in last["value"]]
            elif last.get("dontknow"):
                mine = ["모르겠어요"]
            elif "picked" in last:
                mine = self._picked_text(card, last, view)
        elif card["kind"] == "skel":
            shared = next((e for e in reversed(self.record.log) if e.get("kind") == "answer"
                           and key in (e.get("also_value") or {})), None)
            if shared is not None:
                mine = [str(shared["also_value"][key])]
        elif card.get('mock'):
            try:
                first = state.index.mocks.get(card['mock'], {})
                path = os.path.join(self.home, 'mocks', '%s-%d.json' % (card['mock'], int(first.get('try') or 1)))
                draft = study.read_json(path)
                saved = None
                if first.get('fingerprint') and draft.get('fingerprint') == first['fingerprint']:
                    saved = draft.get('answers', {}).get(key)
                if isinstance(saved, list):
                    if card['kind'] == 'blank' and all(isinstance(value, str) for value in saved):
                        mine = list(saved)
                    elif card['kind'] == 'choice' and all(type(value) is int and 0 <= value < len(view['options']) for value in saved):
                        mine = [view['options'][value]['text'] for value in saved]
            except (OSError, ValueError, AttributeError, TypeError):
                pass  # 다른 기기에 없는 로컬 답안은 빈 상태로 둠
        return {"key": key, "title": state.note_title(card), "name": self.unit_name(card["lesson"], card["unit"]),
                "lines": lines, "stem": view["stem"], "kind": view["kind"], "pick": view.get("pick"),
                "options": [o["text"] for o in view.get("options", [])], "code_options": bool(view.get("code_options")),
                "mine": mine, "ref": card["ref"], "lesson": card.get('after') if card.get('mock') else card["lesson"], "step": card.get("step"), "state": note["state"]}

    def _last_wrong(self, key):
        """그 카드의 마지막 틀린 답 기록(생성기 시드와 문장 카드 shown 을 다시 쓰려고). 없으면 None."""
        return next((e for e in reversed(self.record.log) if e.get("kind") == "answer" and e.get("card") == key
                     and e.get("result") != "pass"), None)

    def _picked_text(self, card, entry, view):
        if card["kind"] == "stmt":
            texts = {s["id"]: s["text"] for s in card["topic"].get("statements", [])}
            return [texts.get(p, p) for p in entry.get("picked") or []]
        options = view.get("options") or []  # 생성기는 기록의 시드로 다시 만든 보기
        return [options[p]["text"] for p in entry.get("picked") or [] if isinstance(p, int) and p < len(options)]

    def _static_view(self, card, entry=None):
        """오답 노트에 다시 그릴 문항. 생성기는 기록의 시드로, 문장 카드는 기록의 shown 순서로 다시 만들고 shown 이 없으면 빈칸판.
        뼈대 카드는 기록의 답 줄(seed, masked, whole, fade, back)로 다시 만들고 기록이 없으면 f = 0 코드 예제."""
        entry = entry or {}
        seed = entry.get("seed")
        if seed is None:
            seed = 1
        if card["kind"] in ("blank", "choice"):
            return dict(card["item"])
        if card["kind"] == "skel":
            record = entry if entry.get("kind") == "answer" else None
            try:
                return skel.view(card, self.skeletons[card["pattern"]], int(seed), record=record)
            except (bank.AiBankError, KeyError) as error:
                raise AiError("문항을 다시 만들 수 없습니다: %s" % error)
        if card["kind"] == "gen":
            return gen.run(card["gen"], int(seed))
        statement = card["stmt"]
        texts = {s["id"]: s for s in card["topic"].get("statements", [])}
        shown = [texts[i] for i in entry.get("shown") or [] if i in texts]
        if shown:
            return {"kind": "choice", "stem": "%s에 대한 설명으로 **%s** 것을 고르세요."
                    % (card["topic"].get("title", ""), "옳은" if statement.get("ok") else "옳지 않은"),
                    "options": [{"text": s["text"], "ok": bool(s.get("ok")), "why": s.get("why", "")} for s in shown],
                    "pick": entry.get("pick") or ("right" if statement.get("ok") else "wrong"), "explain": statement.get("why", "")}
        if entry.get("kind") == "answer" and statement.get("cloze"):  # 고르기판 답에는 shown 이 늘 있으니 빈칸판에서 틀린 것
            return cloze_item(statement)
        return {"kind": "choice", "stem": "다음 문장이 맞는지 고르세요.\n\n%s" % statement["text"], "options": [],
                "explain": statement.get("why", "")}

    def explain(self, key):
        """오답 노트 [해설 보기]. {"answer", "explain", "ref", "why"}."""
        card = self.card_info(key)
        view = self._static_view(card, self._last_wrong(key))
        if view["kind"] == "choice" and not view["options"]:  # 함께 고른 보기로만 노트에 든 문장 카드
            answer = ["맞는 문장입니다." if card["stmt"].get("ok") else "틀린 문장입니다."]
            return {"answer": answer, "explain": view["explain"], "ref": card["ref"], "why": {}}
        if view["kind"] == "blank":
            answer = [b["answer"][0] for b in view["blanks"]]
            return {"answer": answer, "explain": view.get("explain", ""), "ref": card["ref"], "why": {}}
        right = grade.right_options(view)
        return {"answer": [view["options"][n]["text"] for n in right], "explain": view.get("explain", ""), "ref": card["ref"],
                "why": {view["options"][n]["text"]: view["options"][n].get("why", "") for n in range(len(view["options"]))}}

    # 현황

    def overview(self):
        """홈과 허브의 현황(설계 2.13)."""
        result = self._state().overview()
        result["continuation"] = self.continuation()
        result["last_at"] = max(str(result.get("last_at") or ""), str(result["continuation"].get("at") or "")) or None
        return result

    def hub_overview(self):
        """과정별 진도·이어갈 위치와 두 과정의 실제 활동 기록을 허브에 줌."""
        result = dict(self.overview())
        counts = dict(self._index.all_activity)
        result.update(activity_counts=counts, activity=sorted(counts),
                      recent=[dict(row) for row in self._index.all_recent])
        return result


class _LogIndex(object):
    """기록을 덧붙는 만큼만 이어 읽는 색인. 카드별 답(review.EventIndex), 처음 읽은 날, 연 차시, 짐작, 다시 보기, 날마다 답한
    카드와 카드별 일정 캐시를 둠. 4주 기록(7,000줄 안팎)을 답마다 처음부터 다시 계산하지 않으려는 것임."""

    def __init__(self, course="intro", versions=None, revised=()):
        self.course = course
        self.events = review.EventIndex(versions=versions, revised=revised)
        self.reads, self.opened, self.guesses, self.revisits = {}, set(), {}, set()
        self.day_cards = {}
        self.sched, self.start_due = {}, {}
        self.mocks = {}
        self.related = []
        self.all_activity, self.all_recent = {}, []
        self.all_first_mocks = {}
        self.n = 0

    def feed(self, entries):
        self.n += len(entries)
        for day, count in activity_counts(entries).items():
            self.all_activity[day] = self.all_activity.get(day, 0) + count
        self.all_recent = (recent_lines(entries, with_course=True, first_mocks=self.all_first_mocks) + self.all_recent)[:5]
        entries = [row for e in entries if (row := mixed_mock.course_entry(e, self.course)) is not None]
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
            elif kind == 'mock_submit' and e.get('mock') not in self.mocks:
                self.mocks.setdefault(e.get('mock'), e)
                if day is not None:
                    self.related += [(cid, day + datetime.timedelta(days=1)) for cid in e.get('related') or [] if isinstance(cid, str)]


class _State(object):
    """기록 스냅샷에서 계산한 값. AiSession._state 가 캐시하고, 카드 일정은 _LogIndex 의 캐시를 씀."""

    def __init__(self, sess, index, today):
        self.sess, self.today, self.exam, self.index = sess, today, sess.exam, index
        self.log = sess.course_log()
        starts = {e.get("set"): (e.get("lesson"), e.get("unit")) for e in self.log
                  if e.get("kind") == "set" and e.get("mode") == "unit"}
        self.practice_completed = {starts[e.get("set")] for e in self.log
                                   if e.get("kind") == "set_end" and e.get("set") in starts}
        self.events = index.events.events
        self.revised = index.events.dropped
        self.legacy_cards = {cid for cid in index.events.unversioned if cid in self.events and cid in sess.cards and not sess.cards[cid].get("mock")}
        self.reads = index.reads
        self.opened = index.opened
        self.guesses = index.guesses
        self.revisited_today = {(lesson, unit) for lesson, unit, day in index.revisits if day == today}
        self.sched = {}
        self._overview, self._overview_key = None, None
        self.related_due = {}
        for cid, day in index.related:
            if cid in sess.cards and not any(row['src'] == 'answer' and row['day'] >= day for row in self.events.get(cid, [])):
                self.related_due[cid] = min(day, self.related_due.get(cid, day))
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
                             if s and s["first"] == today and cid in sess.cards and not sess.cards[cid]["core"] and not sess.cards[cid].get('mock'))
        todays = {cid: self.events[cid] for cid in index.day_cards.get(today, ()) if cid in self.events}
        self.again = plan.again_cards(todays, today)
        self.completed_today = set(todays) - set(self.again)
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
        return card["id"] in self.events or card['id'] in self.related_due or (card["core"] and self.unlocked(card))

    def new_cap_left(self):
        """오늘 더 열 수 있는 비핵심 새 카드 수. NEW_PER_DAY 가 None 이면 상한 없음."""
        if NEW_PER_DAY is None:
            return 10 ** 6
        return max(0, NEW_PER_DAY - self.new_today)

    def eligible_new(self, card):
        """아직 답한 적 없고 오늘 새로 낼 수 있는 카드인지. 차시 풀기로 연 차시(문제집)는 모든 카드, 읽은 단원은 핵심 카드와
        핵심이 모두 상자 2 이상인 단원의 비핵심 카드(last_new 뒤에는 비핵심을 새로 열지 않음). 비핵심 하루 상한은 묶음을 만들 때 셈."""
        if card["id"] in self.events or card['id'] in self.related_due or not self.unlocked(card):
            return False
        if card["core"] or card["lesson"] in self.opened:
            return True
        last_new = self.exam.get("last_new")
        if last_new is not None and self.today > last_new:
            return False
        return self.core_ready(card["lesson"], card["unit"])

    def due_day(self, cid):
        card = self.sess.cards.get(cid)
        extra = self.related_due.get(cid)
        if cid not in self.sched:
            if card and card["core"] and self.unlocked(card) and review.in_sweep(self.exam, self.today):
                day = review.sweep_day(cid, self.exam)
                return min(day, extra) if extra is not None else day
            return extra
        day = review.due_on(self.sched[cid], cid, self.exam, self.today)
        return min(day, extra) if day is not None and extra is not None else (day or extra)

    def sure_wrong(self, cid):
        """확신 오답을 다시 보는 기간(확실함으로 틀린 다음 날부터 7일 뒤 다시 볼 날까지)인지."""
        s = self.sched.get(cid)
        return bool(s) and s["recheck"] is not None and s["recheck"] >= self.today

    def due_cards(self):
        """날짜가 된 복습 카드(상대 지연 큰 순). 마지막 복습일에는 상자 1·확신 오답·자주 틀리는 문항과
        모의고사 관련 연습 카드를 남김."""
        last_day = self.exam.get("last_review") is not None and self.today == self.exam["last_review"]
        rows = []
        for cid, card in self.sess.cards.items():
            day = self.due_day(cid)
            if day is None or day > self.today:
                continue
            if last_day and cid not in self.related_due and not (self.box(cid) == 1 or self.sure_wrong(cid) or cid in self.leeches):
                continue
            rows.append(cid)
        rows.sort(key=lambda c: (-review.relative_delay(self.sched.get(c), self.today), c))
        return rows

    # 묶음

    def review_status(self):
        """자동 복습과 같은 후보 규칙으로 낼 문항이 있는지 확인함. 다음 날짜는 전체 카드에서 셈."""
        days = sorted(day for day in (self.due_day(cid) for cid in self.sess.cards) if day is not None and day > self.today)
        upcoming = {"date": days[0].isoformat(), "text": _md(days[0]), "count": days.count(days[0])} if days else None
        return {"available": bool(build_set(self.sess, self, "review", random.Random(0))), "next": upcoming}

    def is_preview(self, lesson):
        day = review.parse_day(lesson.get("date"))
        return day is not None and day > self.today

    def unit_stats(self, lid, key):
        cards = self._units.get((lid, key), [])
        memorised = families_memorised(cards, self.sched, self.revised)
        due = sum(1 for c in cards if (self.due_day(c["id"]) or datetime.date.max) <= self.today)
        return {"read": (lid, key) in self.reads, "cards": len(cards), "memorised": memorised,
                "families": len({c["family"] for c in cards}), "due": due, "practiced": (lid, key) in self.practice_completed}

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
        """안 읽은 공개 단원. 차시 단원은 그 차시 no·date 와 단원 순서, 상황별 코드 단원은 권하는 차시 no, date None, order
        100 + index 단원 순서라 권하는 차시 단원 뒤·다음 차시 앞에 옴. 모두 name(단원 이름)을 가짐."""
        rows = []
        for lid, note in self.sess.notes.items():
            group = self.sess.patterns.get(lid)
            for n, key in enumerate(note["visible"]):
                if (lid, key) in self.reads:
                    continue
                meta = note["unit_meta"].get(key, {})
                row = {"lesson": lid, "unit": key, "title": note["units"][key]["title"], "name": self.sess.unit_name(lid, key),
                       "minutes": int(meta.get("minutes") or 5)}
                if group is not None:
                    if key not in group["units"]:
                        continue
                    after = self.sess.lessons.get(group["units"][key]["after"])
                    row.update(no=after["no"] if after else 999, date=None, order=100 + list(group["units"]).index(key))
                else:
                    entry = self.sess.lessons[lid]
                    row.update(no=entry["no"], date=review.parse_day(entry["date"]), order=n)
                rows.append(row)
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
        if revisit:  # 상황별 코드 단원도 고를 수 있어 lessons 를 직접 읽지 않고 place·unit_name 을 씀
            lid, key = revisit["lesson"], revisit["unit"]
            revisit = dict(revisit, no=self.sess.place(lid)["no"], name=self.sess.unit_name(lid, key),
                           title=self.sess.notes[lid]["units"][key]["title"])
        ctx = {"today": self.today, "exam": self.exam, "again": self.again,
               "mock": plan.pending_mock(self.sess.index["mocks"], ready, taken, self.today, self.exam), "due": due,
               "target": plan_row["units_today"] if DAILY_GOAL else None, "read_today": plan_row["units_read_today"], "unit": unit,
               "revisit": revisit}
        return plan.next_card(ctx)

    def pattern_rows(self):
        """홈 「상황별 코드」 구역 값. [{"id", "title", "ready", "error", "units": [단원]}], 단원은 {"key", "name", "title", "label",
        "after", "after_no", "ready", "read", "cards", "memorised", "families", "due", "minutes"} 이고 index 의 단원 순서.
        공개 안 된 단원은 ready False, title "", label = name, 수는 0."""
        sess = self.sess
        out = []
        for group in sess.index["patterns"]:
            gid = group["id"]
            note = sess.notes.get(gid)
            row = {"id": gid, "title": group["title"], "ready": note is not None,
                   "error": sess.errors.get(gid) or sess.errors.get("patterns"), "units": []}
            for key, info in group["units"].items():
                after = sess.lessons.get(info["after"])
                unit = {"key": key, "name": info["name"], "title": "", "label": info["name"], "after": info["after"],
                        "after_no": after["no"] if after else None, "ready": False, "read": False, "cards": 0, "memorised": 0,
                        "families": 0, "due": 0, "minutes": 0}
                if note is not None and key in note["visible"]:
                    meta = note["unit_meta"].get(key, {})
                    unit.update(self.unit_stats(gid, key))
                    unit.update(title=note["units"][key]["title"], label=sess.unit_name(gid, key), ready=True,
                                minutes=int(meta.get("minutes") or 5))
                row["units"].append(unit)
            out.append(row)
        return out

    def overview(self):
        key = (tuple(os.path.isfile(os.path.join(bank.mock_dir(mid, self.sess.root), "meta.json"))
                     for mid in self.sess.mocks), tuple(sorted(self.sess.errors.items())),
               plan.REVIEW_FIRST, plan.BACKLOG_HALF, NEW_PER_DAY, BACKLOG_HALF, DAILY_GOAL)
        if self._overview is None or self._overview_key != key:
            self._overview = self._make_overview()
            self._overview_key = key
        return copy.deepcopy(self._overview)

    def _make_overview(self):
        sess = self.sess
        due = self.due_cards()
        lessons = []
        for entry in sess.index["lessons"]:
            row = {"course": sess.course, "id": entry["id"], "no": entry["no"], "title": entry["title"], "date": entry["date"], "weight": entry["weight"],
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
        today_rows = [e for e in self.log if e.get("kind") == "answer" and review.study_day(e.get("at")) == self.today]
        moved = 0
        for cid, s in self.sched.items():
            if s and any(day == self.today and flag for day, _, flag in s["days"]):
                moved += 1
        plan_row = self.plan()
        counts = self.notes()[1]
        activity = activity_counts(self.log)
        mocks = [dict(m, ready=os.path.isfile(os.path.join(bank.mock_dir(m["id"], sess.root), "meta.json")))
                 for m in sess.index["mocks"]]
        last_at = max((str(e.get("at") or "") for e in self.log), default=None) or None
        return {"course": sess.course, "lessons": lessons, "patterns": self.pattern_rows(), "mocks": mocks,
                "mock_pending": " ".join(sess.mock_pending.values()), "due": len(due), "again": len(self.again),
                "today_answers": moved, "today_extra": max(0, len(today_rows) - moved),
                "memorised": families_memorised(list(sess.cards.values()), self.sched, self.revised), "cards": len(sess.cards),
                "families": len({c["family"] for c in sess.cards.values()}), "plan": plan_row, "next": self.next(plan_row, len(due)),
                "notes": counts, "activity": sorted(activity), "activity_counts": activity, "recent": recent_lines(self.log),
                "last_at": last_at, "errors": dict(sess.errors), "legacy_cards": len(self.legacy_cards),
                "revised_cards": sum(cid in sess.cards and not review.memorised(self.sched.get(cid)) for cid in self.revised)}


def families_memorised(cards, sched, revised=()):
    """외운 문항 수. family 하나를 한 번만 세고, family 안 열린(답한) 카드가 모두 상자 4 이상일 때 외운 것으로 봄."""
    groups = {}
    for card in cards:
        s = sched.get(card["id"])
        if s or card["id"] in revised:
            groups.setdefault(card["family"], []).append(review.memorised(s) if s else False)
    return sum(1 for marks in groups.values() if marks and all(marks))


def activity_counts(log):
    """{달력 날짜: AI 하루 수}. 끝낸 연습 묶음, 끝까지 읽은 단원, 제출한 모의고사를 1 씩 셈(허브 막대)."""
    counts = {}
    for e in log:
        if e.get("kind") in ("set_end", "learn", "mock_submit") and e.get("at"):
            day = str(e["at"])[:10]
            counts[day] = counts.get(day, 0) + 1
    return counts


def recent_lines(log, most=5, with_course=False, first_mocks=None):
    """허브 최근 채점 줄 [{"at", "kind", "n", "first_pass", "score", "of", "mock"}] (최근 순)."""
    out = []
    first_mocks = {} if first_mocks is None else first_mocks
    for entry in log:
        if entry.get("kind") == "mock_submit":
            first_mocks.setdefault(entry.get("mock"), entry)
    for e in reversed(log):
        if e.get("kind") == "set_end":
            out.append({"at": e.get("at"), "kind": "set", "n": e.get("n"), "first_pass": e.get("first_pass")})
        elif e.get("kind") == "mock_submit" and first_mocks.get(e.get("mock")) is e:
            out.append({"at": e.get("at"), "kind": "mock", "mock": e.get("mock"), "score": e.get("score"), "of": e.get("of")})
        else:
            continue
        if with_course:
            out[-1]["course"] = e.get("course", bank.course_of(e.get("lesson") or e.get("card")))
        if len(out) >= most:
            break
    return out


# 묶음 만들기

def _overlapping_pattern_answers(sess, first, second):
    """같은 코드 예제의 줄 고르기와 고칠 줄 문항이 같은 답 줄을 보여주는지 확인함."""
    a, b = sess.cards[first], sess.cards[second]
    if a.get("kind") != "skel" or b.get("kind") != "skel" or a["pattern"] != b["pattern"]:
        return False
    if {a["part"], b["part"]} != {"pick", "change"}:
        return False
    pick, change = (a, b) if a["part"] == "pick" else (b, a)
    skeleton = sess.skeletons[pick["pattern"]]
    target = skel.lines_of(skeleton, pick["variant"])[pick["entry"]["line"]].strip()
    entry = change["entry"]
    if pick["variant"] not in (entry["from"], entry["to"]):
        return False
    rows = skel.diff(skeleton, entry["from"], entry["to"])["rows"]
    return any(not row["same"] and target in {(row["left"] or "").strip(), (row["right"] or "").strip()} for row in rows)


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
        if card["kind"] == "skel" and any(_overlapping_pattern_answers(sess, cid, other) for other, _ in chosen
                                          if sess.cards[other]["kind"] == "skel"):
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


def cloze_item(statement):
    """문장 카드의 빈칸판 문항."""
    cloze = statement["cloze"]
    return {"kind": "blank", "stem": cloze["text"],
            "blanks": [{"answer": cloze["answer"], "mode": cloze.get("mode") or "word", "hint": cloze.get("hint", "")}],
            "explain": statement.get("why", "")}


def _gen_trim(sess, chosen, keep=(), minimum=0):
    """묶음 크기에 맞춰 생성기를 뒤에서 줄임. minimum개와 keep의 문항은 남김."""
    while True:
        gens = [n for n, (c, _) in enumerate(chosen) if sess.cards[c]["kind"] == "gen"]
        spare = [n for n in gens if chosen[n][0] not in keep]
        if not spare or len(gens) <= max(minimum, int(len(chosen) * GEN_SHARE)):
            return chosen
        del chosen[spare[-1]]


def _shows(card):
    """뼈대 카드가 드러내는 코드 예제 이름 집합(change 는 from·to 둘)."""
    return set(card.get("situations") or {}) | {card.get("variant")}


# 같은 뼈대에서 먼저 낼 꼴. slot 은 코드 예제 전체를, change 는 두 코드 예제의 같은 줄을 보기로 보여 순위가 낮은 꼴의 답이 됨
SKEL_RANK = {"order": 0, "pick": 0, "change": 1, "slot": 2}


def _blockers(sess, cid, waiting):
    """cid 가 뼈대 change·slot 카드면 waiting 가운데 cid 보다 먼저 낼 카드. 같은 뼈대이고 SKEL_RANK 가 낮고 보이는 코드 예제가 겹치는
    카드임."""
    card = sess.cards[cid]
    if card.get("kind") != "skel":
        return []
    return [m for m in waiting if m != cid and sess.cards[m].get("kind") == "skel" and sess.cards[m]["pattern"] == card["pattern"]
            and SKEL_RANK[sess.cards[m]["part"]] < SKEL_RANK[card["part"]] and _shows(card) & _shows(sess.cards[m])]


def _hold_lead(sess, lead, rest):
    """다시 보기 뒤 앞 카드(lead)도 _blockers 를 따르게 함. lead 카드가 기다리는 카드가 rest 에 있으면 lead 끝으로 당겨 옴.
    당겨 온 카드도 같은 뼈대 카드라 lead 는 그 단원 카드로 남음. 그다음 기다리는 카드를 lead 안에서 SKEL_RANK 순으로 뒤에 두고
    (lead, rest) 를 돌려줌."""
    while True:
        pull = [(m, pool) for m, pool in rest if any(_blockers(sess, c, [m]) for c in lead)]
        if not pull:
            break
        lead = lead + [m for m, _ in pull]
        rest = [r for r in rest if r not in pull]
    rank = {c: SKEL_RANK[sess.cards[c]["part"]] if _blockers(sess, c, lead) else -1 for c in lead}
    return sorted(lead, key=lambda c: rank[c]), rest


def _arrange(sess, state, chosen, rng, pattern=None):
    """순서 정하기. 같은 confuse 카드는 사이에 한 문항만 두고, 같은 차시·tags 는 붙이지 않고, 고르기는 CHOICE_RUN 개 넘게
    잇지 않음. 같은 코드 예제 뼈대 카드가 아직 남았으면 SKEL_RANK 가 높은 카드를 미룸(slot 은 코드 예제 전체를 보여 고르기의 답이 되고, change 는
    같은 줄 보기로 pick 의 답을 보임). 맞지 않으면 confuse → 차시·tags → 고르기 → 뼈대 순으로 풂. pattern 이 있으면(단원 모드)
    자리마다 N(새 카드, 주어진 순서 그대로이되 같은 코드 예제 카드를 기다리는 카드는 미룸)·R(나머지)을 정하고, R 자리는 바로 뒤 N 자리에
    올 새 고르기까지 세어 고르기를 잇는 수를 지킴."""
    def form(cid):
        return sess.card_form(sess.cards[cid], state.box(cid))

    def blockers(cid, waiting):
        return _blockers(sess, cid, waiting)

    def held(cid, waiting):
        return bool(blockers(cid, waiting))
    new = [c for c, pool in chosen if pool == "new"] if pattern else []
    rest = [c for c, pool in chosen if not pattern or pool != "new"]
    rng.shuffle(rest)
    seq = []
    while new or rest:
        if pattern:
            slot = pattern[len(seq) % len(pattern)]
            if slot == "N" and new:
                free = [c for c in new if not held(c, new + rest)]
                if free:
                    seq.append(new.pop(new.index(free[0])))
                    continue
                waiting = [m for m in rest if m in blockers(new[0], rest)]
                ready = [m for m in waiting if not held(m, new + rest)]
                if waiting:  # 새 카드가 모두 같은 코드 예제 카드를 기다리면 그 카드를 먼저 냄
                    seq.append(rest.pop(rest.index((ready or waiting)[0])))
                else:
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
        if pattern:  # 이 자리 바로 뒤 N 자리에 올 새 고르기도 이어지는 수에 셈
            gap = 0
            while gap < len(pattern) and pattern[(len(seq) + 1 + gap) % len(pattern)] == "N":
                gap += 1
            for c in [c for c in new if not held(c, new + rest)][:gap]:
                if form(c) != "choice":
                    break
                run += 1

        spread = prev is not None and any(sess.cards[c]["lesson"] != prev["lesson"] for c in pool)
        loose = prev is not None and any(not set(sess.cards[c]["tags"]) & set(prev["tags"]) for c in pool)

        def ok(cid, level):
            card = sess.cards[cid]
            if level < 4 and held(cid, new + pool):
                return False
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
        for level in range(5):
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


def build_set(sess, state, mode, rng, lesson=None, unit=None, card=None, trace=None):
    """모드별 묶음 카드 id 목록(설계 2.9). 화면 순서까지 정해서 돌려줌."""
    cards = sess.cards
    today = state.today
    again = [c for c in state.again if c in cards]
    due = [c for c in state.due_cards() if c not in again]
    cap = state.new_cap_left()

    def new_cards(where=None):
        rows, extra = [], 0
        for c in sorted(cards.values(), key=lambda c: (sess._home(c)["no"], c["kind"] == "skel", c["unit"], c["order"])):
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
        weights = [sess._home(cards[c])["weight"] * cards[c]["prio"] * (6 - (state.box(c) or 0)) for c in pool]
        out = []
        while pool:
            total = sum(weights)
            mark, acc = rng.random() * total, 0.0
            for n, w in enumerate(weights):
                acc += w
                if acc >= mark:
                    out.append(pool.pop(n))
                    weights.pop(n)
                    break
            else:
                out.append(pool.pop())
                weights.pop()
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
        low = sorted([c for c in read_cards() if c not in due and c not in again and c not in state.completed_today
                      and (state.box(c) or 0) <= 2],
                     key=lambda c: (state.box(c) or 0, str(state.due_day(c)), c))
        gens = [c for c in read_cards() if cards[c]["kind"] == "gen" and c not in due and c not in state.completed_today]
        rng.shuffle(gens)
        pools = [("again", again), ("due", due), ("low", low), ("gen", gens)]
    elif mode in ("mixed", "lesson"):
        # 차시 풀기에는 그 차시 뒤에 권하는 상황별 코드 카드도 넣음(단원을 읽어야 열리는 것은 eligible_new 그대로)
        where = (lambda c: c["lesson"] == lesson or c.get("after") == lesson) if mode == "lesson" else None
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
    if trace is not None:
        trace.update(policy="rules-v1", runtime_revision=collection.runtime_revision(),
                     trigger="learner_choice" if mode == "note" else "rules",
                     requested_card=card if mode == "note" else None,
                     candidate_scope="mode_pools_before_choose",
                     candidate_pools=[{"name": name, "ids": list(ids), "overflow": extra}
                                      for extra, groups in ((False, pools), (True, overflow)) for name, ids in groups],
                     candidate_ids=list(dict.fromkeys(cid for _, ids in pools + overflow for cid in ids)),
                     selection_probability=None)
    chosen = _choose(sess, state, pools, size, rng)
    if len(chosen) < SET_MIN and overflow:
        chosen = _choose(sess, state, overflow, SET_MIN, rng, taken=chosen)
    chosen = _fix_blanks(sess, state, chosen, pools, protected)
    keep = {card} if mode == "note" else set()
    if mode in ("review", "sweep"):
        keep.update(cid for cid, pool in chosen if pool in ("again", "due"))
    chosen = _gen_trim(sess, chosen, keep=keep, minimum=1 if mode == "unit" else 0)
    if trace is not None:
        trace["selected_pools"] = dict(chosen)
        trace["selected_sources"] = {cid: "learner_choice" if mode == "note" and cid == card else "rules"
                                     for cid, _ in chosen}
    if mode == "unit":
        selected = _arrange(sess, state, chosen, rng, pattern)
        if trace is not None:
            trace["selected"] = list(selected)
        return selected
    lead = [c for c, pool in chosen if pool == "lead"]
    rest = [(c, pool) for c, pool in chosen if pool != "lead"]
    if mode == "mixed":  # [다시 풀기](note)의 lead 는 학습자가 고른 카드라 옮기지 않음
        lead, rest = _hold_lead(sess, lead, rest)
    selected = lead + _arrange(sess, state, rest, rng)
    if trace is not None:
        trace["selected"] = list(selected)
    return selected


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
        self.memorised_before = families_memorised([sess.cards[c] for c in cards], state.sched, state.revised)
        self.title = sess.title_of(mode, lesson, unit)
        self.ended = False
        self.card, self.draft = None, {}

    def fingerprint(self, previous_refs=False):
        """묶음 전체를 대조함. 출처 정정은 등록한 이전 ref로만 다시 계산함."""
        def generator(value):
            if not isinstance(value, gen.GenSpec):
                raise TypeError(type(value).__name__)
            sources = []
            for path in (value.path, os.path.join(self.sess.root, "items", "common", "gens.py")):
                try:
                    with open(path, "rb") as stream:
                        sources.append(hashlib.sha256(stream.read()).hexdigest())
                except OSError:
                    sources.append(None)
            return {"id": value.id, "meta": value.meta, "doc": value.doc, "sources": sources}

        content = {"cards": [self.sess.cards[c] for c in self.stats], "terms": self.sess.terms,
                   "skeletons": self.sess.skeletons}
        if previous_refs:
            cards, replaced = [], False
            for card in content["cards"]:
                fixes = self.sess.items.get(card.get("lesson"), {}).get("meta", {}).get("resume_source_refs", {})
                fix = fixes.get(card["id"]) if isinstance(fixes, dict) else None
                if fix is not None:
                    if (not isinstance(fix, dict) or card["kind"] not in ("blank", "choice")
                            or any(not isinstance(fix.get(key), list) or not all(isinstance(ref, str) for ref in fix[key])
                                   for key in ("previous", "current"))
                            or card.get("ref") != fix["current"] or card["item"].get("ref") != fix["current"]):
                        return None
                    card = dict(card, ref=fix["previous"], item=dict(card["item"], ref=fix["previous"]))
                    replaced = True
                cards.append(card)
            if not replaced:
                return None
            content["cards"] = cards
        return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, default=generator).encode("utf-8")).hexdigest()

    def snapshot(self):
        """큐·현재 문항·답한 뒤 상태·입력 초안을 로컬 JSON 값으로 만듦."""
        names = ("id", "mode", "lesson", "unit", "card", "queue", "pos", "stats", "answered", "_undo", "answers",
                 "before", "had_before", "memorised_before", "title", "ended", "draft")
        data = {name: getattr(self, name) for name in names}
        data.update(rng=self.rng.getstate(), sure_before=sorted(self.sure_before),
                    before_due={k: d.isoformat() if d else None for k, d in self.before_due.items()},
                    fingerprint=self.fingerprint(), set_records=[e for e in self.sess.record.log if e.get("set") == self.id])
        return data

    @classmethod
    def restore(cls, sess, saved):
        """저장한 묶음의 시드와 답 상태를 이어 씀. 다시 채점하거나 set 기록을 추가하지 않음."""
        if saved["ended"] or saved["mode"] not in MODES:
            raise ValueError("끝난 묶음")
        result = cls.__new__(cls)
        result.sess = sess
        for key in ("id", "mode", "lesson", "unit", "card", "queue", "pos", "stats", "answered", "_undo", "answers",
                    "before", "had_before", "memorised_before", "title", "ended", "draft"):
            setattr(result, key, copy.deepcopy(saved[key]))
        if not 0 <= result.pos < len(result.queue) or any(e["card"] not in sess.cards for e in result.queue):
            raise ValueError("문항이 바뀐 묶음")
        if saved["fingerprint"] != result.fingerprint():
            previous = result.fingerprint(previous_refs=True)
            if previous is None or saved["fingerprint"] != previous:
                raise ValueError("문항이 바뀐 묶음")
        result.before_due = {k: datetime.date.fromisoformat(d) if d else None for k, d in saved["before_due"].items()}
        result.sure_before = set(saved["sure_before"])
        result.rng = random.Random()
        state = saved["rng"]
        result.rng.setstate((state[0], tuple(state[1]), state[2]))
        return result

    # 문항 보이기

    def _collection_item(self, entry):
        card = self.sess.cards[entry["card"]]
        view = self._view(entry)
        return collection.question(view["item"], card=card["id"], lesson=card["lesson"], unit=card["unit"],
                                   family=card.get("family"), tags=card.get("tags") or [], step=card.get("step"),
                                   difficulty=card.get("level"),
                                   seed=entry["seed"], option_order=view["order"], form=view["form"],
                                   terms_revision=self.sess.collection_terms_revision)

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
            if entry["again"] and isinstance(item.get("alt"), dict):  # 묶음 안에서 다시 낼 때 바꿔 쓴 문항
                item = dict(item, **item["alt"])
        elif card["kind"] == "gen":
            source = bank.generation_source(card["gen"])
            item = gen.run(card["gen"], entry["seed"])
            # 실제 생성 때의 소스를 초안에 보존함. 예전 캐시에는 값을 소급하지 않음.
            item["_generation"] = source
        elif card["kind"] == "skel":
            item = self._skel_view(card, state, entry)
        elif view["form"] == "blank":
            item = cloze_item(card["stmt"])
        else:
            item = self._statement_choice(card, state, rng, entry["again"])
            view["shown"] = [o["id"] for o in item["options"]]
        view["item"] = item
        order = list(range(len(item.get("options") or [])))
        if order and not view["shown"] and not item.get("keep_order"):
            rng.shuffle(order)
        view["order"] = order
        entry["view"] = view
        return view

    def _skel_view(self, card, state, entry):
        """뼈대 카드 문항. slot 은 같은 뼈대·같은 코드 예제 slot 카드 가운데 주 자리와 열린 자리의 상자로 점차 지우기를 정함."""
        sess = self.sess
        boxes = None
        if card["part"] == "slot":
            boxes = {other["id"]: state.box(other["id"]) for other in sess.cards.values()
                     if other["kind"] == "skel" and other["part"] == "slot" and other["pattern"] == card["pattern"]
                     and other["variant"] == card["variant"] and (other["id"] == card["id"] or state.is_open(other))}
        try:
            return skel.view(card, sess.skeletons[card["pattern"]], entry["seed"], boxes, entry["again"])
        except (bank.AiBankError, KeyError) as error:
            raise AiError("문항을 만들 수 없습니다: %s" % error)

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

    def current(self, *, measure_input=False):
        """지금 문항. 끝났으면 None. {"card", "kind", "chips", "stem", "blanks": [{"mode", "hint"}], "options": [{"no", "text"}],
        "multi", "pick", "code", "code_options"(보기가 코드), "grid"(보기 열 수 1·2), "again", "step", "lesson", "at", "total",
        "answered"}. chips 첫째는 자리 꼬리표(차시 "5차시", 상황별 코드는 단원 name), 둘째는 꼴."""
        if self.pos >= len(self.queue):
            return None
        entry = self.queue[self.pos]
        card = self.sess.cards[entry["card"]]
        view = self._view(entry)
        item = view["item"]
        form = item.get("kind") or view["form"]
        code = form == "blank" and bank.blanks_in_code(item.get("stem", ""))
        chips = []
        lesson = self.sess.lessons.get(card.get('after') if card.get('mock') else card["lesson"])
        if lesson:
            chips.append(self.sess.lesson_label(lesson))
        elif card["lesson"] in self.sess.patterns:
            chips.append(card.get("name") or self.sess.place(card["lesson"])["label"])
        if card["kind"] == "skel":
            chips.append(skel.PART_CHIP[card["part"]])
        else:
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
        self.sess.collect_event("question_returned", {"set": self.id, "card": card["id"], "position": self.pos,
                                                     "again": entry["again"], "mode": self.mode,
                                                     **({"input_schema": collection.AI_INPUT_SCHEMA} if measure_input else {})},
                                item=lambda: self._collection_item(entry),
                                key="question:%s:%d:%s:%d" % (self.id, self.pos, card["id"], entry["seed"]))
        return {"card": card["id"], "kind": form, "chips": chips, "stem": item.get("stem", ""),
                "blanks": [{"mode": b.get("mode") or "word", "hint": b.get("hint", "")} for b in item.get("blanks") or []],
                "options": options, "multi": bool(item.get("multi")), "pick": item.get("pick", "right"), "code": code,
                "code_options": bool(item.get("code_options")), "grid": int(item.get("grid") or 1), "again": entry["again"], "step": card.get("step"), "lesson": card.get('after') if card.get('mock') else card["lesson"], "at": self.pos + 1,
                "total": len(self.queue), "answered": self.answered is not None}

    # 답하기

    def _feedback(self, card, view, graded, picked=None):
        item = view["item"]
        also = graded.get("also") or {}
        out = {"result": graded["result"], "per_blank": graded.get("per_blank", []), "correct": [], "picked": picked or [],
               "right": graded.get("right", []), "why": {}, "explain": item.get("explain", ""), "ref": self._ref(card, view),
               "errata": self._errata(card), "sure_wrong": False,
               "also": [{"blank": n, "slot": b["slot"]} for n, b in enumerate(item.get("blanks") or []) if b.get("slot") in also]}
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
        """답을 채점하고 기록함. 빈칸은 칸마다 글 목록, 고르기는 고른 보기의 no(원래 번호) 목록. 뼈대 카드는 seed 를, 뼈대
        빈칸은 fade·masked·whole 을 남기고, 함께 가린 칸이 틀리면 also(그 자리 카드에 stuck)와 also_value(틀린 칸의 글)를 남김.
        feedback 의 also 는 [{"blank": 0부터 칸 번호, "slot": 자리 id}]."""
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
        if card["kind"] in ("gen", "skel") or view["shown"]:
            row["seed"] = entry["seed"]
        self._skel_row(card, item, row)
        if (item.get("kind") or view["form"]) == "blank":
            values = [str(v) for v in (value or [])]
            if card["kind"] == "skel":
                values += [""] * (len(item.get("blanks") or []) - len(values))
                graded = grade.grade_skel(item, values, self.sess.term_map)
                if graded["also"]:
                    row["also"] = dict(graded["also"])
                    row["also_value"] = {b["slot"]: values[n] for n, b in enumerate(item["blanks"]) if b["slot"] in graded["also"]}
            else:
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
        return self._settle(entry, row, feedback, response=list(value or []))

    @staticmethod
    def _skel_row(card, item, row):
        """답 줄에 다시 그릴 값을 더함. slot은 fade·masked·whole, change는 보기 버전와 반대 방향 여부를 남김."""
        if card["kind"] != "skel":
            return
        made = item.get("skel") or {}
        if made.get("part") == "slot":
            row.update(fade=int(made.get("fade") or 0), masked=list(made.get("masked") or []), whole=bool(made.get("whole")))
        elif made.get("part") == "change":
            row["change_rev"] = made["change_rev"]
            if made.get("back"):
                row["back"] = True

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
        if card["kind"] in ("gen", "skel") or view["shown"]:
            row["seed"] = entry["seed"]
        self._skel_row(card, view["item"], row)
        if view["shown"]:
            row.update(shown=view["shown"], pick=view["item"].get("pick"), picked=[])
        item = view["item"]
        if item.get("blanks"):
            graded = {"result": "stuck", "per_blank": [False] * len(item["blanks"])}
        else:
            graded = {"result": "stuck", "right": grade.right_options(item)}
        return self._settle(entry, row, self._feedback(card, view, graded))

    def _settle(self, entry, row, feedback, response=None):
        self.sess._append(row, private={"response": response, "position": self.pos,
                                       "first_in_set": self.stats[entry["card"]]["first"] is None,
                                       "feedback_returned": True}, item=lambda: self._collection_item(entry))
        self.answers += 1
        snapshot = (list(self.queue), {k: dict(v) for k, v in self.stats.items()})
        self._undo = (snapshot, entry, row)
        self._apply(entry, row["result"])
        self.answered = feedback
        self.sess.save_practice(self, activate=True)
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
        """[내 답도 맞음]. 방금 틀린 빈칸 답을 맞음으로 바꾸고 override 기록을 남김. 뼈대 빈칸은 함께 가린 칸이 틀린 것도
        바꿀 수 있고(also_value), 한 번에 틀린 칸 모두를 맞음으로 봄."""
        if self._undo is None or self.answered is None:
            raise AiError("바꿀 답이 없습니다.")
        (queue, stats), entry, row = self._undo
        main = row["result"] != "pass" and "value" in row
        if not main and not row.get("also_value"):
            raise AiError("빈칸을 틀린 답만 바꿀 수 있습니다.")
        out = {"kind": "override", "set": self.id, "again": row["again"], "card": row["card"]}
        if main:
            out["value"] = row["value"]
        if row.get("also_value"):
            out["also_value"] = dict(row["also_value"])
        self.sess._append(out)
        self.queue, self.stats = queue, stats
        self._apply(entry, "pass")
        self.answered = dict(self.answered, result="pass", overridden=True, also=[])
        self._undo = None
        self.sess.save_practice(self, activate=True)
        return self.answered

    def next(self, *, measure_input=False):
        """다음 문항으로. 끝나면 set_end 를 기록하고 None."""
        if self.answered is None and self.pos < len(self.queue):
            raise AiError("답한 뒤에 넘어갈 수 있습니다.")
        saved = (self.pos, self.answered, self._undo)
        self.pos += 1
        self.answered, self._undo = None, None
        try:
            if self.pos >= len(self.queue):
                self._end()
                self.sess.save_practice(self, activate=True)
                return None
            self.draft = {}
            item = self.current(measure_input=measure_input)
            self.sess.save_practice(self, activate=True)
            return item
        except AiError:
            self.pos, self.answered, self._undo = saved  # 기록을 읽거나 쓰지 못했으면 [다음]을 다시 누를 수 있게 되돌림
            raise

    def _end(self):
        if self.ended:
            return
        first_pass = sum(1 for st in self.stats.values() if st["first"] == "pass")
        self.sess._append({"kind": "set_end", "set": self.id, "n": len(self.stats), "first_pass": first_pass,
                           "answers": self.answers})
        self.ended = True

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
        memorised = families_memorised([self.sess.cards[c] for c in self.stats], state.sched, state.revised) - self.memorised_before
        nexts = sorted(d for d in (state.due_day(c) for c in self.stats) if d is not None and d > today)
        upcoming = None
        if nexts:
            upcoming = {"date": nexts[0].isoformat(), "text": _md(nexts[0]), "count": nexts.count(nexts[0])}
        left = [cid for cid, st in self.stats.items() if st["left"]]
        return {"set": self.id, "mode": self.mode, "lesson": self.lesson, "unit": self.unit, "n": len(self.stats),
                "answers": self.answers, "first_today": first_today, "again_day": again_day, "up": up, "same": same,
                "down": down, "sure_wrong": sure_wrong, "memorised": max(0, memorised), "next": upcoming, "early": early,
                "left": left, "first_pass": sum(1 for st in self.stats.values() if st["first"] == "pass")}
