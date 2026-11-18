# -*- coding: utf-8 -*-
"""모의고사 시작·로컬 초안·제출을 다룸. 제출 전에는 정답과 해설을 반환하지 않음.

입력은 로컬 home/mocks에 문항 id로 보관하고 제출 기록에는 판정만 남김. 남은 시간은
시작 시각과 경과 시간을 함께 써서 화면 이동이나 재시작 뒤에도 이어 셈.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import random
import secrets
import threading
import time

import study
import session
from aiprep import bank, grade, mixed_mock, mock_code
from learning_data import collection
from webprep import bank as webbank
from webprep import record

CODE_KEYS = ("starter", "entry", "examples", "tests", "limit_ms", "tol")
ENV_LIMIT = 3
SUBMITTING = "제출한 답안을 채점하고 있습니다. 채점이 끝날 때까지 답을 바꿀 수 없습니다."
ENV_FAILED = "이 기기에서 코드 작성 문항을 채점하지 못해 제출하지 않았습니다. 잠시 뒤 다시 제출해 주세요."


class MockError(session.SessionError):
    """모의고사 자료나 초안을 읽고 저장하지 못함."""


def _moment(value):
    value = value if isinstance(value, datetime.datetime) else record.parse_at(value)
    if value is None:
        raise MockError("모의고사 시각을 읽을 수 없습니다.")
    return value.astimezone() if value.tzinfo is None else value


def _now():
    return datetime.datetime.now().astimezone()


def _check_code(item):
    """코드 작성 문항이 채점할 수 있는 꼴인지 봄. 숨은 테스트 수 같은 출제 기준은 여기서 보지 않음."""
    code = item.get("code")
    if not isinstance(code, dict) or not isinstance(code.get("starter"), str) or not isinstance(code.get("entry"), str):
        raise ValueError("코드 작성 문항의 시작 코드가 맞지 않습니다")
    count = mock_code.fill_count(code["starter"])
    if not count or not code["entry"].isidentifier():
        raise ValueError("코드 작성 문항의 채울 줄이나 함수 이름이 맞지 않습니다")
    for name in ("examples", "tests"):
        cases = code.get(name)
        if not isinstance(cases, list) or not cases or any(not isinstance(case, dict) or "expected" not in case
                                                            or not isinstance(case.get("args"), list) for case in cases):
            raise ValueError("코드 작성 문항의 예시나 숨은 테스트가 맞지 않습니다")
    limit, tol = code.get("limit_ms"), code.get("tol")
    if limit is not None and (type(limit) is not int or limit <= 0) or tol is not None and (
            type(tol) not in (int, float) or tol < 0):
        raise ValueError("코드 작성 문항의 시간 제한이나 허용 오차가 맞지 않습니다")
    solution = item.get("solution")
    if not isinstance(solution, list) or len(solution) != count or any(not isinstance(line, str) for line in solution):
        raise ValueError("코드 작성 문항의 모범 답안 줄 수가 맞지 않습니다")


def _stable(item):
    """fingerprint 에 넣는 문항 내용. code 묶음은 kind=code 문항에만 더해 다른 문항의 해시는 예전과 같음."""
    row = dict({key: item.get(key) for key in ("id", "kind", "stem", "pick", "multi")},
               blanks=[{key: blank.get(key) for key in ("answer", "mode", "places", "unit", "term", "context")}
                       for blank in item.get("blanks") or []],
               options=[{key: option.get(key) for key in ("text", "ok")} for option in item.get("options") or []])
    if item.get("kind") == "code":
        row["code"] = {key: item["code"].get(key) for key in CODE_KEYS}
    return row


def load_items(root, spec, lessons=None):
    """회차의 문항과 채점 버전 해시를 읽음."""
    folder = bank.mock_dir(spec["id"], root)
    try:
        meta = study.read_json(os.path.join(folder, "meta.json"))
        items = json.loads(webbank.load_secrets(folder)["items.json"])["items"]
        if not isinstance(meta, dict) or not isinstance(items, list) or not items or len(items) != spec["count"]:
            raise ValueError("문항 수가 목록과 맞지 않습니다")
        if type(spec["minutes"]) is not int or spec["minutes"] <= 0:
            raise ValueError("제한 시간이 맞지 않습니다")
        if mixed_mock.candidate(spec):
            mixed_mock.validate(spec, meta, items, lessons)
        ids = [item["id"] for item in items]
        if len(set(ids)) != len(ids) or not all(isinstance(cid, str) and cid for cid in ids):
            raise ValueError("문항 id가 비었거나 겹칩니다")
        for item in items:
            if item.get("kind") not in ("blank", "choice", "code") or item.get("errata"):
                raise ValueError("빈칸·객관식·코드 작성 문항만 쓰고 정정 주제는 넣지 않습니다")
            if item["kind"] == "blank" and not 1 <= len(item.get("blanks") or []) <= 2:
                raise ValueError("빈칸 수가 맞지 않습니다")
            if item["kind"] == "choice" and len(item.get("options") or []) != 4:
                raise ValueError("객관식 보기 수가 맞지 않습니다")
            if item["kind"] == "code":
                _check_code(item)
        stable = [_stable(item) for item in items]
        if mixed_mock.candidate(spec):
            stable = {"items": stable, "blueprint_revision": spec["blueprint_revision"],
                      "classification": [{k: i.get(k) for k in ("id", "course", "lesson", "family", "concept", "format",
                                                               "level", "transferaxis", "conditions", "sourcefacts")} for i in items]}
        fingerprint = hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, webbank.BankError) as error:
        raise MockError("모의고사 자료를 읽을 수 없습니다. %s" % error) from error
    return {item["id"]: item for item in items}, fingerprint


def submissions(log, mid):
    """회차 제출 기록을 실제로 기록된 순서로 돌려줌."""
    return [row for row in log if row.get("kind") == "mock_submit" and row.get("mock") == mid]


def _blank(item, value):
    """답을 비웠는지 봄. 빈칸과 코드 작성은 모든 칸이 공백뿐이면 비운 것이고 주석만 있는 줄은 답한 것임.
    수집의 answered(learning_data/collection.py)도 같은 규칙임."""
    return not value or item["kind"] != "choice" and not any(text.strip() for text in value)


class MockExam:
    """회차 하나. question·save_answer·move·toggle_flag는 초안만 다루고 submit에서 채점함."""

    def __init__(self, session, mid, repeat=False, seed=None, clock=None, monotonic=None, submit_expired=True):
        self.sess, self.id = session, mid
        self.clock, self.monotonic = clock or _now, monotonic or time.monotonic
        self.lock = getattr(session, "_lock", None) or threading.RLock()
        try:
            self.spec = dict(session.mocks[mid])
        except KeyError as error:
            raise MockError("모의고사를 찾을 수 없습니다.") from error
        self.items, self.fingerprint = load_items(session.root, self.spec, getattr(session, "mock_lessons", None))
        self.mixed = mixed_mock.candidate(self.spec)
        if self.mixed:
            self.lock = mixed_mock.lock(session, mid)
        self.local_answers = True
        self.pending_inputs = {}
        self.recovered_draft = False
        self.has_code = any(item["kind"] == "code" for item in self.items.values())
        self.submitting = False  # submit 이 답을 복사한 뒤 기록을 마칠 때까지 참. 초안 파일에는 쓰지 않음
        with self.lock:
            log = self._log()
            starts = [row for row in log if row.get("kind") == "mock_start" and row.get("mock") == mid]
            latest = max(starts, key=lambda row: int(row.get("try") or 1), default=None)
            done = submissions(log, mid)
            if latest is None and done:
                latest = dict(done[-1])
            submitted = {int(row.get("try") or 1): row for row in done}
            active = latest is not None and int(latest.get("try") or 1) not in submitted
            changed = latest is not None and latest.get("fingerprint") != self.fingerprint
            if changed and not repeat:
                if not latest.get("fingerprint"):
                    raise MockError("시작한 문항 버전을 확인하지 못해 이어풀기를 멈췄습니다. 이전 기록은 보존했습니다.")
                raise MockError('시작한 뒤 문제 자료가 바뀌었습니다. 초안과 제출 기록은 보존했습니다.')
            if repeat and active and not changed:
                raise MockError("풀고 있는 모의고사를 먼저 제출하세요.")
            if latest is not None and not repeat:
                self.attempt = int(latest.get("try") or 1)
                self.path = self._path()
                self.result = submitted.get(self.attempt)
                if not os.path.exists(self.path):
                    self.draft = self._fresh_draft(_moment(latest["at"]), latest.get("seed", 0))
                    self.local_answers = self.result is None
                    if self.result is None:
                        self._write_draft()
                        self.recovered_draft = True
                else:
                    self.draft = self._read_draft()
            else:
                self.attempt = max([int(row.get("try") or 1) for row in starts + done] or [0]) + 1
                self.path = self._path()
                started = _moment(self.clock())
                if os.path.exists(self.path):
                    self.draft = self._read_draft()
                    started = _moment(self.draft["started"])
                else:
                    self.draft = self._fresh_draft(started, secrets.randbelow(2 ** 31) if seed is None else seed)
                self.result = None
                self._write_draft()
                try:
                    started_row = session.record.append(dict({"kind": "mock_start", "mock": mid, "try": self.attempt,
                                                          "seed": self.draft["seed"], 'fingerprint': self.fingerprint}, **self.scope_fields()), at=started.isoformat())
                except record.RecordError as error:
                    raise MockError(str(error)) from error
                if self.mixed:
                    session._collect_mixed_record(self, started_row)
                elif hasattr(session, "_collect_record"):
                    session._collect_record(started_row)
            self._anchor = self.monotonic()
            self._budget = self._wall_remaining()
            if submit_expired and self.result is None and self.remaining() <= 0:
                self.submit(auto=True)

    def _path(self):
        home = self.sess.mock_home if self.mixed else self.sess.home
        return os.path.join(home, "mocks", "%s-%d.json" % (self.id, self.attempt))

    def scope_fields(self):
        if not self.mixed:
            return {}
        return {"scope": "mixed", "courses": list(self.spec["courses"]),
                "item_courses": {cid: i["course"] for cid, i in self.items.items()},
                "blueprint_revision": self.spec["blueprint_revision"]}

    def collection_item(self, cid):
        item = self.items[cid]
        metadata = {"card": cid, "lesson": item.get("lesson"), "family": item.get("family"),
                    "tags": item.get("tags") or [], "difficulty": item.get("level"),
                    "option_order": self.draft["shuffle"][cid],
                    "terms_revision": getattr(self.sess, "collection_terms_revision", None)}
        if self.mixed:
            metadata.update(course=item["course"], course_no=self.sess.mock_lessons[item["lesson"]]["no"],
                            scope="mixed", seed=self.draft["seed"], blueprint_revision=self.spec["blueprint_revision"],
                            concept=item.get("concept"), format=item.get("format"), transferaxis=item.get("transferaxis"),
                            conditions=item.get("conditions") or [], sourcefacts=item.get("sourcefacts") or [],
                            classification_basis="author")
        if item["kind"] == "code":
            # 채점 실행기 파일이 바뀌면 code 문항의 버전만 바뀌게 전역 runtime_revision 과 따로 둠
            metadata["code_runtime_revision"] = mock_code.runtime_revision()
        return collection.question(item, **metadata)

    def _log(self):
        try:
            return self.sess.record.reload()
        except record.RecordError as error:
            raise MockError(str(error)) from error

    def _fresh_draft(self, started, seed):
        duration = int(self.spec["minutes"]) * 60
        rng = random.Random(seed)
        order = list(self.items)
        rng.shuffle(order)
        shuffle = {}
        for cid, item in self.items.items():
            choices = list(range(len(item.get("options") or [])))
            rng.shuffle(choices)
            shuffle[cid] = choices
        return {"format": 1, "mock": self.id, "try": self.attempt, "seed": seed, "fingerprint": self.fingerprint,
                "started": started.isoformat(), "deadline": (started + datetime.timedelta(seconds=duration)).isoformat(),
                "duration": duration, "order": order, "shuffle": shuffle, "answers": {}, "flags": [], "current": 0}

    def _read_draft(self):
        try:
            draft = study.read_json(self.path)
            if draft.get("format") != 1 or draft.get("mock") != self.id or draft.get("try") != self.attempt:
                raise ValueError("회차와 풀이 횟수가 맞지 않습니다")
            if draft.get("fingerprint") != self.fingerprint:
                raise ValueError("시작한 뒤 문제 자료가 바뀌었습니다. 초안은 보존했습니다")
            if sorted(draft["order"]) != sorted(self.items) or len(draft["order"]) != len(self.items):
                raise ValueError("문항 순서가 맞지 않습니다")
            if type(draft["current"]) is not int or not 0 <= draft["current"] < len(self.items):
                raise ValueError("열었던 문항 번호가 맞지 않습니다")
            if not isinstance(draft["answers"], dict) or not set(draft["answers"]) <= set(self.items):
                raise ValueError("답안의 문항 id가 맞지 않습니다")
            if not isinstance(draft["flags"], list) or not set(draft["flags"]) <= set(self.items):
                raise ValueError("나중에 볼 문항 id가 맞지 않습니다")
            if draft["duration"] != int(self.spec["minutes"]) * 60:
                raise ValueError("제한 시간이 맞지 않습니다")
            start, end = _moment(draft["started"]), _moment(draft["deadline"])
            if (end - start).total_seconds() != draft["duration"]:
                raise ValueError("종료 시각이 맞지 않습니다")
            for cid, item in self.items.items():
                order = draft["shuffle"][cid]
                if not isinstance(order, list) or any(type(n) is not int for n in order) \
                        or sorted(order) != list(range(len(item.get("options") or []))):
                    raise ValueError("보기 순서가 맞지 않습니다")
            for cid, answer in draft["answers"].items():
                self._validate_answer(cid, answer)
            return draft
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise MockError("모의고사 초안을 읽을 수 없습니다. %s" % error) from error

    def _write_draft(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            study.write_text(self.path, json.dumps(self.draft, ensure_ascii=False, indent=1) + "\n")
        except OSError as error:
            raise MockError("답안을 저장하지 못했습니다. 다시 저장해 주세요. %s" % error) from error

        for cid, original in self.pending_inputs.items():
            if self.draft["answers"][cid] != original:
                self.sess.collect_event("ai_input", {"mock": self.id, "try": self.attempt, "card": cid,
                                                     "input_schema": collection.AI_INPUT_SCHEMA},
                                        observation_context=self.draft["collection_observations"][cid],
                                        **({"_mock_exam": self} if self.mixed else {}))
        self.pending_inputs.clear()

    def _wall_remaining(self):
        seconds = (_moment(self.draft["deadline"]) - _moment(self.clock())).total_seconds()
        return max(0.0, min(self.draft["duration"], seconds))

    def remaining(self):
        if self.result is not None:
            return 0
        elapsed = max(0.0, self.monotonic() - self._anchor)
        return max(0, math.ceil(min(self._wall_remaining(), self._budget - elapsed)))

    def _active(self, submit=True):
        """submit 이 거짓이면 시간이 다 돼도 제출하지 않음. save_answer·move·toggle_flag 는 잠금을 쥔 채 이 함수를 부르는데,
        코드 작성 채점은 잠금을 놓고 해야 함. 그래서 코드 작성 회차에서는 거짓을 넘기고 만료 제출은 expire_mocks 가 맡음."""
        if self.result is not None or self.submitting:
            return False
        if self.remaining() <= 0:
            if submit:
                self.submit(auto=True)
            return False
        return True

    def _validate_answer(self, cid, answer):
        if cid not in self.items or not isinstance(answer, list):
            raise MockError("답안 형식이 맞지 않습니다.")
        item = self.items[cid]
        if item["kind"] == "blank":
            if len(answer) != len(item["blanks"]) or any(not isinstance(value, str) for value in answer):
                raise MockError("빈칸 답안 형식이 맞지 않습니다.")
        elif item["kind"] == "code":
            if len(answer) != mock_code.fill_count(item["code"]["starter"]) or any(not isinstance(value, str) for value in answer):
                raise MockError("코드 답안 형식이 맞지 않습니다.")
            if any("\n" in value or "\r" in value for value in answer):
                raise MockError("채울 줄 하나에는 코드 한 줄만 쓸 수 있습니다.")
            if any(value.strip() == mock_code.FILL for value in answer):
                raise MockError("____ 자리에 코드를 써 주세요.")
        elif any(type(value) is not int or not 0 <= value < len(item["options"]) for value in answer):
            raise MockError("고른 보기 번호가 맞지 않습니다.")
        elif not item.get("multi") and len(set(answer)) > 1:
            raise MockError("보기 하나를 고르세요.")

    def save_answer(self, value, cid=None, flush=True):
        with self.lock:
            if self.submitting:
                raise MockError(SUBMITTING)
            if not self._active(submit=not self.has_code):
                return False
            cid = cid or self.draft["order"][self.draft["current"]]
            self._validate_answer(cid, value)
            previous_draft = copy.deepcopy(self.draft)
            was_pending = cid in self.pending_inputs
            item = self.items[cid]
            empty = ([""] * len(item.get("blanks", [])) if item["kind"] == "blank"
                     else [""] * mock_code.fill_count(item["code"]["starter"]) if item["kind"] == "code" else [])
            previous = self.draft["answers"].get(cid)
            if previous != list(value) and hasattr(self.sess, "collection"):
                context = self.sess.collection.observation_context()
                if value != (previous if previous is not None else empty):
                    self.pending_inputs.setdefault(cid, previous if previous is not None else empty)
                self.draft.setdefault("collection_epochs", {})[cid] = context.get("epoch") if context else None
                self.draft.setdefault("collection_observations", {})[cid] = context
            self.draft["answers"][cid] = list(value)
            try:
                if flush:
                    self._write_draft()
            except MockError:
                self.draft.clear()
                self.draft.update(previous_draft)
                if not was_pending:
                    self.pending_inputs.pop(cid, None)
                raise
            return True

    def move(self, position):
        with self.lock:
            if not self._active(submit=not self.has_code):
                return False
            if type(position) is not int or not 0 <= position < len(self.items):
                raise MockError("문항 번호가 맞지 않습니다.")
            previous = self.draft["current"]
            self.draft["current"] = position
            try:
                self._write_draft()
            except MockError:
                self.draft["current"] = previous
                raise
            return True

    def toggle_flag(self):
        with self.lock:
            if not self._active(submit=not self.has_code):
                return False
            cid = self.draft["order"][self.draft["current"]]
            previous = list(self.draft["flags"])
            flags = set(previous)
            flags.remove(cid) if cid in flags else flags.add(cid)
            self.draft["flags"] = sorted(flags)
            try:
                self._write_draft()
            except MockError:
                self.draft["flags"] = previous
                raise
            return cid in flags

    def question(self, position=None):
        if self.result is None:
            self._active()
        position = self.draft["current"] if position is None else position
        if type(position) is not int or not 0 <= position < len(self.items):
            raise MockError("문항 번호가 맞지 않습니다.")
        cid = self.draft["order"][position]
        item = self.items[cid]
        if self.result is None and hasattr(self.sess, "collect_event"):
            self.sess.collect_event("mock_question_returned", {"mock": self.id, "try": self.attempt, "card": cid, "position": position,
                                                           "input_schema": collection.AI_INPUT_SCHEMA},
                                    item=lambda: self.collection_item(cid),
                                    key="mock-question:%s:%d:%s:%s" % (self.id, self.attempt, self.fingerprint, cid),
                                    **({"_mock_exam": self} if self.mixed else {}))
        return {"card": cid, "kind": item["kind"], "stem": item["stem"], "lesson": item.get("lesson"),
                "step": item.get("step"), "at": position + 1, "total": len(self.items), "code": "```" in item["stem"],
                "code_options": bool(item.get("code_options")), "grid": int(item.get("grid") or 1),
                "pick": item.get("pick", "right"), "multi": bool(item.get("multi")),
                "blanks": [{"mode": b.get("mode", "word"), "hint": b.get("hint", "")} for b in item.get("blanks") or []],
                "options": [{"no": n, "text": item["options"][n]["text"]} for n in self.draft["shuffle"][cid]],
                "mine": list(self.draft["answers"].get(cid, [])) if self.local_answers else None,
                "flagged": cid in self.draft["flags"],
                **({"course": item["course"], "course_no": self.sess.mock_lessons[item["lesson"]]["no"]} if self.mixed else {}),
                **({key: copy.deepcopy(item["code"][key]) for key in ("starter", "entry", "examples")}
                   if item["kind"] == "code" else {})}

    def answered(self, cid):
        value = self.draft["answers"].get(cid) or []
        if self.items[cid]["kind"] == "code":
            return not _blank(self.items[cid], value)
        return bool(value) and (all(text.strip() for text in value) if self.items[cid]["kind"] == "blank" else True)

    def progress(self):
        return [{"card": cid, "answered": self.answered(cid), "flagged": cid in self.draft["flags"]}
                for cid in self.draft["order"]]

    def _related(self, results, links=None):
        """첫 풀이의 오답마다 같은 주제의 연습 카드 하나를 고름. 답한 것으로 기록하지 않음."""
        if submissions(self._log(), self.id):
            return []
        cards, out = getattr(self.sess, 'cards', {}), []
        if self.mixed:
            cards = mixed_mock.related_cards(self.sess, with_gens=True)
        for cid in self.draft['order']:
            if results[cid] in ('pass', 'ungraded'):
                continue
            item = self.items[cid]
            choices = mixed_mock.practice_candidates(item, cards, out)
            if choices:
                out.append(choices[0]['id'])
                if links is not None:
                    links[cid] = choices[0]['id']
        return out

    def _submitted(self):
        done = next((row for row in submissions(self._log(), self.id) if int(row.get("try") or 1) == self.attempt), None)
        if done is not None:
            self.result = done
        return done

    def submit(self, auto=False):
        """채점해 mock_submit 을 남김. 코드 작성 문항은 잠금을 놓은 채 채점하며, 답을 복사한 뒤 기록을 마칠 때까지
        save_answer 를 거절함. 코드를 실행하지 못하면 ENV_LIMIT 번째 전까지는 mock_submit 을 남기지 않고 MockError 를 냄. 같은 시도에서
        ENV_LIMIT 번째로 실패하면 실행하지 못한 코드 작성 문항만 ungraded 로 기록하고 제출함."""
        with self.lock:
            done = self._submitted()
            if done is not None:
                return dict(done)
            if self.submitting:
                raise MockError(SUBMITTING)
            self._write_draft()
            answers = copy.deepcopy(self.draft["answers"])
            elapsed = self.draft["duration"] - self._wall_remaining()
            elapsed = max(elapsed, self.draft["duration"] - self._budget + max(0, self.monotonic() - self._anchor))
            auto = bool(auto or self.remaining() <= 0)
            codes = [cid for cid, item in self.items.items() if item["kind"] == "code" and not _blank(item, answers.get(cid))]
            self.submitting = True
        try:
            graded = {cid: mock_code.grade(self.items[cid], answers[cid]) for cid in codes}
        except BaseException:
            with self.lock:
                self.submitting = False
            raise
        self.lock.acquire()
        try:
            done = self._submitted()  # 잠금을 놓은 사이 다른 곳에서 같은 시도를 제출했는지 다시 봄
            if done is not None:
                return dict(done)
            if any(value["result"] == mock_code.ENV for value in graded.values()):
                self.draft["env_failures"] = int(self.draft.get("env_failures") or 0) + 1
                if self.draft["env_failures"] < ENV_LIMIT:
                    self._write_draft()
                    raise MockError(ENV_FAILED)
            results = {}
            for cid, item in self.items.items():
                value = answers.get(cid) or []
                if _blank(item, value):
                    results[cid] = "blank"
                elif item["kind"] == "code":
                    results[cid] = "ungraded" if graded[cid]["result"] == mock_code.ENV else graded[cid]["result"]
                else:
                    answer = grade.grade_item(item, value, self.sess.term_map) if item["kind"] == "blank" else grade.grade_choice(item, value)
                    results[cid] = "pass" if answer["result"] == "pass" else "stuck"
            if graded:
                # 통과 수는 이 기기 초안에만 둠. 제출 기록과 수집에는 맞음·틀림만 남김
                self.draft["code_passed"] = {cid: [value["passed"], value["total"]] for cid, value in graded.items()
                                             if value["result"] != mock_code.ENV}
                self._write_draft()
            event = {"kind": "mock_submit", "mock": self.id, "try": self.attempt, "results": results,
                     "score": sum(value == "pass" for value in results.values()), "of": len(results),
                     "secs": min(self.draft["duration"], max(0, round(elapsed))), "auto": auto,
                     "seed": self.draft["seed"], 'fingerprint': self.fingerprint}
            event.update(self.scope_fields())
            related_links = {}
            event['related'] = self._related(results, related_links)
            event['related_by_question'] = related_links
            try:
                self.result = self.sess.record.append(event, at=_moment(self.clock()).isoformat())
            except record.RecordError as error:
                raise MockError(str(error)) from error
            if any(value != "blank" for value in results.values()) and hasattr(self.sess, "collection"):
                self.sess.collection.mark_graded()
            if hasattr(self.sess, "_collect_record"):
                consent = self.sess.collection.observation_context() or {}
                included = {cid for cid in self.draft["order"] if not answers.get(cid)
                            or consent.get("epoch") and self.draft.get("collection_epochs", {}).get(cid) == consent["epoch"]}
                partial = dict(self.result, results={cid: results[cid] for cid in included}, of=len(included),
                               score=sum(results[cid] == "pass" for cid in included), scope="current_consent",
                               omitted_before_consent=len(results) - len(included), related=[], related_by_question={})
                if self.mixed:
                    partial["collection_scope"] = partial.pop("scope")
                    partial["scope"] = "mixed"
                    self.sess._collect_mixed_record(self, partial, observation_context=consent)
                else:
                    self.sess._collect_record(partial, observation_context=consent)
                for position, cid in enumerate(self.draft["order"]):
                    item = self.items[cid]
                    context = self.draft.get("collection_observations", {}).get(cid)
                    if context is None:
                        context = {"epoch": self.draft.get("collection_epochs", {}).get(cid),
                                   "goal": None, "observed_at": None}
                    self.sess.collect_event("mock_answer", {"mock": self.id, "try": self.attempt, "card": cid, "position": position,
                                                           "response": list(answers.get(cid) or []) if cid in included else None,
                                                           "result": results[cid] if cid in included else "not_collected",
                                                           "secs": None, "auto": event["auto"]},
                                            item=lambda cid=cid: self.collection_item(cid),
                                            key="mock-answer:%s:%d:%s:%s" % (self.id, self.attempt, self.fingerprint, cid),
                                            at=self.result["at"], observation_context=context,
                                            **({"_mock_exam": self} if self.mixed else {}))
            return dict(self.result)
        finally:
            self.submitting = False
            self.lock.release()

    def summary(self):
        if self.result is None:
            raise MockError("제출한 뒤 결과를 볼 수 있습니다.")
        lessons = {}
        for cid, result in self.result["results"].items():
            lesson = self.items[cid].get("lesson", "")
            counts = lessons.setdefault(lesson, {"correct": 0, "total": 0})
            counts["total"] += 1
            counts["correct"] += result == "pass"
        done = submissions(self._log(), self.id)
        if not done:
            raise MockError('제출 기록을 찾을 수 없습니다. 기록 파일을 확인하세요.')
        first = done[0]
        return {"mock": self.id, "try": self.attempt, "score": self.result["score"], "of": self.result["of"],
                "secs": self.result["secs"], "first_score": first["score"], "lessons": lessons,
                "results": dict(self.result["results"]), "auto": self.result["auto"]}

    def explain(self, cid):
        if self.result is None:
            raise MockError("제출한 뒤 해설을 볼 수 있습니다.")
        item = self.items[cid]
        return {"question": self.question(self.draft["order"].index(cid)), "result": self.result["results"][cid],
                "correct": [b["answer"][0] for b in item.get("blanks") or []],
                "right": grade.right_options(item) if item["kind"] == "choice" else [],
                "explain": item.get("explain", ""), "why": {n: o.get("why", "") for n, o in enumerate(item.get("options") or [])},
                "ref": list(item.get("ref") or []),
                **({"solution": list(item["solution"])} if item["kind"] == "code" else {})}
