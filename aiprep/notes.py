# -*- coding: utf-8 -*-
"""오답 노트 갈래(설계 2.11). 기록에서 매번 계산함.

갈래는 셋: wrong(틀린 문항), skipped(미응답 문항), fixed(다시 맞힌 문항). 학습일마다 그 카드의 첫 답 하나만 봄.
연습에서 그날 첫 답이 틀리거나 일부 맞으면 wrong, [모르겠어요]면 skipped. 단원을 처음 읽은 날의 답은 빼되 확신 오답은 넣음.
모의고사(첫 풀이)의 틀린 문항은 wrong, 비운 문항은 skipped. 마지막으로 틀린 날 뒤 다른 날 첫 답을 맞히면 fixed, 그 뒤
또 다른 날 한 번 더 맞히면 목록에서 내려감. 다시 틀리면 wrong 으로 돌아감.
"""
from aiprep.skel import PART_CHIP

STATES = ("wrong", "skipped", "fixed")
KIND_LABEL = {"blank": "빈칸", "choice": "고르기", "stmt": "고르기", "gen": "숫자 바뀜", "skel": "코드", "mock": "모의고사"}


def card_note(events, read_day=None):
    """한 카드의 갈래. {"state", "sure", "fails"(틀린 학습일 수), "days"(그 학습일들), "at"(마지막 답 시각), "mock"}.
    목록에 없으면 state 가 None."""
    state, last_fail, fixed_day, sure, mock = None, None, None, False, None
    fail_days = []
    days = []
    for event in events:
        if event["src"] not in ("answer", "mock"):
            continue
        if days and days[-1][0] == event["day"]:
            continue  # 그날 첫 답만 봄
        days.append((event["day"], event))
    for day, event in days:
        failed = event["result"] != "pass"
        if failed:
            sure_wrong = bool(event.get("sure")) and event["result"] == "stuck" and not event.get("dontknow")
            if event["src"] == "answer" and day == read_day and not sure_wrong:
                continue
            state = "skipped" if event.get("dontknow") else "wrong"
            last_fail, sure = day, sure_wrong
            if event["src"] == "mock":
                mock = event.get("mock")
            if day not in fail_days:
                fail_days.append(day)
        elif state in ("wrong", "skipped") and last_fail is not None and day > last_fail:
            state, fixed_day = "fixed", day
        elif state == "fixed" and fixed_day is not None and day > fixed_day:
            state, sure = None, False
    last_at = events[-1]["at"] if events else None
    return {"state": state, "sure": sure if state in ("wrong", "skipped") else False, "fails": len(fail_days), "days": fail_days,
            "at": last_at, "mock": mock}


def group_title(card, lessons, mocks, patterns_title="상황별 코드"):
    """카드가 들어갈 묶음 제목과 정렬 키. 모의고사 카드는 그 회차, 상황별 코드 카드는 한 묶음, 나머지는 차시."""
    cid = card["id"]
    if card.get("kind") == "mock" or cid.startswith("m"):
        mid = cid.split("-")[0]
        mock = mocks.get(mid, {})
        return mock.get("title", mid), (0, mid)
    if cid.startswith("pc-"):
        return patterns_title, (2, "pc")  # 상황별 코드 카드는 한 묶음(카드 id 를 키로 두면 카드마다 묶음이 갈림)
    lesson = lessons.get(card.get("lesson"), {})
    return "%d차시 %s" % (lesson.get("no", 0), lesson.get("title", "")), (1, lesson.get("no", 0))


def wrong_notes(events, cards, read_days, lessons, mocks, leeches=(), mock_order=()):
    """오답 노트 묶음과 갈래 수. events 는 review.card_events 결과, cards 는 {카드 id: 카드}(모의고사 카드는 kind "mock"),
    read_days 는 {카드 id: 그 단원을 처음 읽은 학습일}, lessons·mocks 는 {id: index 항목}, leeches 는 자주 틀리는 카드 id,
    mock_order 는 최근에 낸 회차부터의 id 목록. 돌려주는 값 ([{"title", "items"}], {"wrong", "skipped", "fixed"})."""
    groups, counts = {}, {state: 0 for state in STATES}
    rank = {mid: n for n, mid in enumerate(mock_order)}
    leeches = set(leeches)
    for cid, rows in events.items():
        card = cards.get(cid)
        if card is None:
            continue
        note = card_note(rows, read_days.get(cid))
        if note["state"] is None:
            continue
        counts[note["state"]] += 1
        title, order = group_title(card, lessons, mocks)
        if order[0] == 0:
            order = (0, rank.get(order[1], len(rank)), order[1])
        where = "%d차시" % lessons.get(card.get("lesson"), {}).get("no", 0) if order[0] == 1 else title
        kind = PART_CHIP.get(card.get("part")) if card.get("kind") == "skel" else None  # 뼈대 카드는 꼴(코드 빈칸·순서 고르기·고르기)
        item = {"key": cid, "label": "%s · %s" % (kind or KIND_LABEL.get(card.get("kind"), "문항"), where), "state": note["state"],
                "sure": note["sure"], "leech": cid in leeches, "deep": bool(card.get("deep")), "fails": note["fails"],
                "days": [d.isoformat() for d in note["days"]], "at": note["at"]}
        groups.setdefault((order, title), []).append(item)
    out = []
    for (order, title), items in sorted(groups.items(), key=lambda pair: pair[0][0]):
        items.sort(key=lambda i: str(i["at"] or ""), reverse=True)
        items.sort(key=lambda i: (not i["sure"], not i["leech"]))
        out.append({"title": title, "items": items})
    return out, counts
