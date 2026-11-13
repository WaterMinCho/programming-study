# -*- coding: utf-8 -*-
"""혼합 모의고사의 과정·배분과 공통 초안 소유 위치를 확인함."""
import collections
import os
import threading
import weakref

from aiprep import bank

_LOCKS = {}
_EXAMS = weakref.WeakValueDictionary()


def candidate(spec):
    return spec.get("id") == "m4" or spec.get("scope") == "mixed"


def validate(spec, meta, items=None, lessons=None):
    """파서가 보존한 명시적 계약만 받음. 원본 index를 우회해 읽지 않음."""
    if (spec.get("scope") != "mixed" or spec.get("courses") != ["intro", "app"]
            or spec.get("count") != 32 or not isinstance(spec.get("blueprint_revision"), str)
            or not spec["blueprint_revision"].strip()
            or spec.get("course_counts") != {"intro": 16, "app": 16}
            or not isinstance(spec.get("blueprint"), dict)):
        raise ValueError("혼합 모의고사의 과정·배분 메타데이터 연결을 준비하고 있습니다.")
    if not isinstance(meta, dict):
        raise ValueError("혼합 모의고사의 배분 자료를 읽을 수 없습니다.")
    for key in ("scope", "courses", "count", "minutes", "blueprint_revision", "course_counts", "blueprint"):
        if meta.get(key) != spec.get(key):
            raise ValueError("혼합 모의고사의 목록과 배분 자료가 일치하지 않습니다.")
    if meta.get("draft") is not False:
        raise ValueError("혼합 모의고사 문항을 검토하고 있습니다.")
    if items is not None:
        if collections.Counter(i.get("course") for i in items) != spec["course_counts"]:
            raise ValueError("개론·응용 문항 수가 배분과 일치하지 않습니다.")
        if dict(collections.Counter(i.get("lesson") for i in items)) != spec["blueprint"]:
            raise ValueError("문항의 실제 차시 배분이 목록과 일치하지 않습니다.")
        for item in items:
            entry = (lessons or {}).get(item.get("lesson"))
            if (not entry or entry["course"] != item.get("course")
                    or bank.course_of(item["lesson"]) != item["course"]
                    or not isinstance(item.get("family"), str) or not item["family"].strip()):
                raise ValueError("혼합 문항의 과정·차시·family를 확인해 주세요.")


def identity(sess, mid):
    return (os.path.realpath(sess.record.path), os.path.realpath(sess.root),
            os.path.realpath(sess.mock_home), mid)


def lock(sess, mid):
    return _LOCKS.setdefault(identity(sess, mid), threading.RLock())


def cached(sess, mid):
    return _EXAMS.get(identity(sess, mid))


def remember(sess, exam):
    _EXAMS[identity(sess, exam.id)] = exam


def course_entry(row, course):
    """같은 제출을 과정별 복습 입력으로 나눔. 원본 기록은 바꾸지 않음."""
    if row.get("scope") != "mixed":
        return row if row.get("course", bank.course_of(row.get("lesson") or row.get("card"))) == course else None
    if row.get("kind") not in ("mock_start", "mock_submit") or course not in row.get("courses", []):
        return None
    out = dict(row, course=course)
    if "results" in row:
        out["results"] = {cid: result for cid, result in row["results"].items()
                          if row.get("item_courses", {}).get(cid) == course}
        out["related"] = [cid for cid in row.get("related", []) if bank.course_of(cid) == course]
    return out


def related_cards(sess):
    """혼합 오답의 후보만 따로 읽음. 일반 연습 목록에는 추가하지 않음."""
    cards = {}
    for entry in sess.mock_lessons.values():
        if not bank.is_ready(entry, sess.root):
            continue
        try:
            note = bank.load_note({"id": entry["page"], "title": entry["title"]}, sess.root)
            data = bank.load_items(entry, sess.root, with_gens=False)
        except bank.AiBankError as error:
            sess.errors[entry["id"]] = str(error)
            continue
        cards.update((card["id"], card) for card in bank.cards_of(entry, data) if card["unit"] in note["visible"])
    return cards


def collection_course(exam, sess, kind, data):
    """실제 회차 객체와 검증한 문항에서만 수집 과정을 가져옴."""
    from aiprep.mock import MockExam
    if (not isinstance(exam, MockExam) or exam.sess is not sess or not candidate(exam.spec)
            or sess.mocks.get(exam.id) != exam.spec or data.get("mock") != exam.id
            or data.get("try") != exam.attempt):
        raise ValueError("혼합 수집의 회차 문맥을 확인할 수 없습니다.")
    if kind in ("mock_question_returned", "mock_answer", "ai_input"):
        cid = data.get("card")
        if cid not in exam.items:
            raise ValueError("혼합 수집의 문항을 확인할 수 없습니다.")
        item = exam.items[cid]
        entry = sess.mock_lessons.get(item.get("lesson"))
        if not entry or item.get("course") != entry["course"] or bank.course_of(item["lesson"]) != item["course"]:
            raise ValueError("혼합 수집의 문항 분류가 바뀌었습니다.")
        return item["course"]
    if kind in ("mock_start", "mock_submit") and data.get("course") in exam.spec["courses"]:
        course = data["course"]
        for item in exam.items.values():
            entry = sess.mock_lessons.get(item.get("lesson"))
            if not entry or item.get("course") != entry["course"] or bank.course_of(item["lesson"]) != item["course"]:
                raise ValueError("혼합 수집의 문항 분류가 바뀌었습니다.")
        if kind == "mock_submit" and any(exam.items.get(cid, {}).get("course") != course for cid in data.get("results", {})):
            raise ValueError("제출 집계에 다른 과정의 문항이 섞였습니다.")
        return course
    raise ValueError("혼합 수집의 이벤트 종류를 확인해 주세요.")


def description(spec):
    return "%d문항 · 개론 %d · 응용 %d · 연습 기본 %d분" % (
        spec["count"], spec["course_counts"]["intro"], spec["course_counts"]["app"], spec["minutes"])
