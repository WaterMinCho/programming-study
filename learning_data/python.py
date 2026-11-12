# -*- coding: utf-8 -*-
"""공통 수집부에 파이썬의 실제 입력 변경과 채점 결과를 연결함."""
import json
import os
import uuid

import adaptive
import study
from learning_data.collection import Collection, CollectionError, digest, question, stamp


def home_dir():
    return os.environ.get("STUDY_PYTHON_HOME") or os.path.join(os.path.expanduser("~"), ".rokey-study", "python")


class PythonCollection(Collection):
    def __init__(self, home, repository):
        super().__init__(home, repository, track="python")

    def _failure(self, error):
        self.missed += 1
        self.error = "추가 학습 데이터를 저장하지 못했습니다. 기존 풀이 기록은 유지됩니다. %s" % error

    def _question(self, item):
        if item["kind"] == "quiz":
            body = adaptive.quiz_section(item["set"], item["q"]["id"])
            grading = item["q"]
            extra = {}
        else:
            body = adaptive.problem_body(item["spec"])
            grading = {k: v for k, v in item["spec"].items() if k != "dir"}
            extra = {"starter": study.read_text(os.path.join(item["spec"]["dir"], "starter.py"))}
        return question({"stem": body, "kind": item["kind"]}, track="python", card=item["key"],
                        unit=item["unit"], tags=item["tags"], question_type=item["type"],
                        level=item["level"], grading_revision=digest(grading), **extra)

    def observe(self, rnd, item, value):
        """저장 값이 바뀌었을 때만 호출함. 외부 편집 시각을 소급하지 않음."""
        context = self.observation_context()
        if not context:
            return
        try:
            shown = self._question(item)
            prediction_at = None
            with self._connect() as conn:
                for revision, payload in conn.execute("SELECT item_revision, payload FROM events WHERE kind='question_returned' ORDER BY seq DESC"):
                    previous = json.loads(payload)
                    if previous.get("set") == rnd["id"] and previous.get("card") == item["key"]:
                        if previous.get("consent_epoch") == context["epoch"] and revision == shown["revision"]:
                            prediction_at = previous["observed_at"]
                        break
            self.emit("python_input", {"set": rnd["id"], "card": item["key"], "response": value,
                                       "consent_epoch": context["epoch"], "observed_at": context["observed_at"],
                                       "prediction_at": prediction_at}, shown, observation_context=context)
        except (OSError, ValueError, KeyError, TypeError, CollectionError) as error:
            self._failure(error)

    def returned(self, sess, rid, item_id):
        """화면에 실제 선택한 문항만 기록함. 회차 자료를 읽는 동작과 구분함."""
        context = self.observation_context()
        if not context:
            return
        try:
            rnd, _, item = sess._find(rid, item_id)
            self.emit("question_returned", {"set": rnd["id"], "card": item["key"], "consent_epoch": context["epoch"]},
                      self._question(item), observation_context=context)
        except (OSError, ValueError, KeyError, TypeError, CollectionError) as error:
            self._failure(error)

    def _inputs(self, rid):
        result = {}
        with self._connect() as conn:
            for eid, revision, payload in conn.execute(
                    "SELECT event_id, item_revision, payload FROM events WHERE kind='python_input' ORDER BY seq DESC"):
                data = json.loads(payload)
                if data.get("set") == rid and data.get("card") not in result:
                    result[data["card"]] = dict(data, event_id=eid, item_revision=revision)
        return result

    @staticmethod
    def _file_stamp(sess, rnd, key):
        item = sess.cat[key]
        name = "quiz" if item["kind"] == "quiz" else adaptive.fname_of(key)
        path = sess._code_path(rnd["id"], name)
        stat = os.stat(path)
        return stat.st_mtime_ns, stat.st_size

    @staticmethod
    def _value(sess, rnd, key):
        item = sess.cat[key]
        name = adaptive.fname_of(key)
        if item["kind"] == "quiz":
            path = sess._code_path(rnd["id"], "quiz")
            if not os.path.isfile(path):
                return None
            answers, error = study.parse_quiz_answers(path)
            if error:
                raise CollectionError("채점 전 입력 파일을 확인하지 못했습니다.")
            return answers.get(name)
        path = sess._code_path(rnd["id"], name)
        return study.read_text(path) if os.path.isfile(path) else None

    def before_grade(self, sess, rnd):
        """채점 전에 실제 파일과 동의 중 관찰한 입력이 같은지 확인함."""
        context = self.observation_context()
        if not context:
            return None
        try:
            inputs = self._inputs(rnd["id"])
            selected = {}
            for key in sess._keys(rnd):
                row = inputs.get(key)
                if row and row["consent_epoch"] == context["epoch"] and row["response"] == self._value(sess, rnd, key):
                    row = dict(row, file_stamp=self._file_stamp(sess, rnd, key),
                               first_in_set=not any(a["round"] == rnd["id"] and a["item"] == key for a in sess.prof["attempts"]))
                    selected[key] = row
            return {"inputs": selected, "context": context, "batch": str(uuid.uuid4())}
        except (OSError, ValueError, KeyError, TypeError, CollectionError) as error:
            self._failure(error)
            return None

    def after_grade(self, sess, rnd, items, snapshot):
        """채점 중 바뀐 입력을 제외하고 같은 입력의 반복 채점을 중복 저장하지 않음."""
        if snapshot is None:
            return
        try:
            current = self.observation_context()
            if not current or current["epoch"] != snapshot["context"]["epoch"]:
                return
            latest = self._inputs(rnd["id"])
            with self._connect() as conn:
                graded = {json.loads(payload).get("input_event") for payload, in conn.execute("SELECT payload FROM events WHERE kind='answer'")}
            batch = snapshot["batch"]
            selected = []
            for item in items:
                key = item["key"]
                row = snapshot["inputs"].get(key)
                if item["state"] not in ("ok", "wrong") or not row or row["event_id"] in graded or latest.get(key, {}).get("event_id") != row["event_id"]:
                    continue
                if row["response"] != self._value(sess, rnd, key):
                    continue
                if row["file_stamp"] != self._file_stamp(sess, rnd, key):
                    continue
                shown = self._question(sess.cat[key])
                if shown["revision"] != row["item_revision"]:
                    continue
                selected.append((item, row, shown))
            if not selected:
                return
            self.emit("batch_start", {"batch": batch, "set": rnd["id"]})
            for item, row, shown in selected:
                context = {"epoch": row["consent_epoch"], "goal": row.get("goal"), "observed_at": row["observed_at"]}
                self.emit("answer", {"set": rnd["id"], "card": item["key"], "batch": batch,
                                     "again": 0 if row["first_in_set"] else 1, "first_in_set": row["first_in_set"],
                                     "prediction_at": row.get("prediction_at"),
                                     "result": item["state"], "response": row["response"], "input_event": row["event_id"]},
                          shown, key="python-grade:" + row["event_id"], at=stamp(), observation_context=context)
        except (OSError, ValueError, KeyError, TypeError, CollectionError) as error:
            self._failure(error)
