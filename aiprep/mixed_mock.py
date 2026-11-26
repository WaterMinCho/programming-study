# -*- coding: utf-8 -*-
"""혼합 모의고사의 과정·배분과 공통 초안 소유 위치를 확인함."""
import collections
import os
import threading
import weakref

from aiprep import bank

_LOCKS = {}
_EXAMS = weakref.WeakValueDictionary()
PUBLISHED_IDS = ("m4", "m5", "m6")
_MIXED32 = {"count": 32, "minutes": 120, "course_counts": {"intro": 16, "app": 16}}
# 배분 버전마다 문항 수·시간·과정별 문항 수를 둠. 표에 없는 배분 버전은 학습자 목록에서 숨김
CONTRACTS = {"mixed32-blueprint-v1": _MIXED32, "mixed32-transfer-v1": _MIXED32, "mixed32-applied04-v1": _MIXED32,
             "all44-v1": {"count": 44, "minutes": 120, "course_counts": {"intro": 31, "app": 13}, "all_lessons": True},
             "all46-v1": {"count": 46, "minutes": 120, "course_counts": {"intro": 32, "app": 14}, "all_lessons": True},
             "all50-v1": {"count": 50, "minutes": 120, "course_counts": {"intro": 35, "app": 15}, "all_lessons": True},
             "all52-v1": {"count": 52, "minutes": 120, "course_counts": {"intro": 36, "app": 16}, "all_lessons": True,
                          "app_through": 9},
             "all54-v1": {"count": 54, "minutes": 120, "course_counts": {"intro": 38, "app": 16}, "all_lessons": True,
                          "app_through": 10},
             "all33-v1": {"count": 33, "minutes": 60, "course_counts": {"intro": 19, "app": 14}, "all_lessons": True, "app_through": 10},
             "all42-v1": {"count": 42, "minutes": 90, "course_counts": {"intro": 24, "app": 18}, "all_lessons": True, "app_through": 10},
             "all35-v1": {"count": 35, "minutes": 60, "course_counts": {"intro": 19, "app": 16}, "all_lessons": True, "app_through": 11},
             "all44-applied11-v1": {"count": 44, "minutes": 90, "course_counts": {"intro": 24, "app": 20}, "all_lessons": True, "app_through": 11},
             'all56-applied12-v1': {'count': 56, 'minutes': 120, 'course_counts': {'intro': 36, 'app': 20}, "all_lessons": True, 'app_through': 12},
             'all57-applied12-v1': {'count': 57, 'minutes': 120, 'course_counts': {'intro': 38, 'app': 19}, "all_lessons": True, 'app_through': 12},
             'all37-applied12-v1': {'count': 37, 'minutes': 60, 'course_counts': {'intro': 19, 'app': 18}, "all_lessons": True, 'app_through': 12},
             'all46-applied12-v1': {'count': 46, 'minutes': 90, 'course_counts': {'intro': 24, 'app': 22}, "all_lessons": True, 'app_through': 12},
             'all32-applied12-v1': {'count': 32, 'minutes': 60, 'course_counts': {'intro': 17, 'app': 15}, "all_lessons": True, 'app_through': 12},
}


def candidate(spec):
    return spec.get("id") in PUBLISHED_IDS or spec.get("scope") == "mixed"


def expected_lessons(contract):
    """차시 범위를 명시한 배분 버전에서 과정별 차시 ID를 돌려줌."""
    if "app_through" not in contract:
        return None
    return {"i%02d" % no for no in range(1, 18)} | {"a%02d" % no for no in range(1, contract["app_through"] + 1)}


def validate(spec, meta, items=None, lessons=None):
    """파서가 보존한 명시적 계약만 받음. 원본 index를 우회해 읽지 않음."""
    revision = spec.get("blueprint_revision")
    contract = CONTRACTS.get(revision) if isinstance(revision, str) else None
    blueprint = spec.get("blueprint")
    if (spec.get("scope") != "mixed" or spec.get("courses") != ["intro", "app"] or contract is None
            or spec.get("count") != contract["count"] or spec.get("minutes") != contract["minutes"]
            or spec.get("course_counts") != contract["course_counts"]
            or not isinstance(blueprint, dict) or not blueprint
            or any(type(n) is not int or n < 1 for n in blueprint.values())):
        raise ValueError("혼합 모의고사의 과정·배분 메타데이터 연결을 준비하고 있습니다.")
    expected = expected_lessons(contract)
    if expected is not None and blueprint.keys() != expected:
        raise ValueError("혼합 모의고사의 차시 범위가 배분 버전과 일치하지 않습니다.")
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


def related_cards(sess, with_gens=False):
    """혼합 오답의 후보만 따로 읽음. 일반 연습 목록에는 추가하지 않음."""
    cards = {}
    for entry in sess.mock_lessons.values():
        if not bank.is_ready(entry, sess.root):
            continue
        try:
            note = bank.load_note({"id": entry["page"], "title": entry["title"]}, sess.root)
            data = bank.load_items(entry, sess.root, with_gens=with_gens)
            lesson_cards = bank.cards_of(entry, data)
        except bank.AiBankError as error:
            sess.errors[entry["id"]] = str(error)
            continue
        cards.update((card["id"], card) for card in lesson_cards if card["unit"] in note["visible"])
    return cards


def practice_candidates(item, cards, excluded=()):
    """같은 과정의 관련 문항을 고름. 같은 근거에서는 조건 변형을 먼저 둠."""
    family, facts = item.get("family"), set(item.get("facts") or [])
    tags = set(item.get("tags") or [])
    course = item.get("course") or bank.course_of(item.get("lesson"))
    ranked = []
    for card in cards.values():
        if (card["id"] in excluded or card.get("mock") or card.get("errata")
                or bank.course_of(card.get("lesson")) != course):
            continue
        same_family = bool(family and card.get("family") == family)
        overlap = len(facts & set(card.get("facts") or [])) if card.get("lesson") == item.get("lesson") else 0
        common_tags = len(tags & set(card.get("tags") or []))
        if not (same_family or overlap or common_tags and card.get("lesson") == item.get("lesson")):
            continue
        ranked.append(((not same_family, -overlap, card.get("kind") != "gen", -common_tags, card["id"]), card))
    return [card for _, card in sorted(ranked, key=lambda row: row[0])]


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
    if CONTRACTS.get(spec.get("blueprint_revision"), {}).get("all_lessons"):
        spans = []
        for course, name in (("intro", "개론"), ("app", "응용")):
            nos = sorted(int(lid[1:]) for lid in spec["blueprint"] if bank.course_of(lid) == course)
            if nos:
                spans.append("%s %d~%d차시" % (name, nos[0], nos[-1]))
        return " · ".join(["%d문항" % spec["count"], "%d분" % spec["minutes"]] + spans)
    return "%d문항 · 개론 %d · 응용 %d · 연습 기본 %d분" % (
        spec["count"], spec["course_counts"]["intro"], spec["course_counts"]["app"], spec["minutes"])
