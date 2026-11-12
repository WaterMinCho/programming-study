# -*- coding: utf-8 -*-
"""상황별 코드 뼈대(ai/patterns/S*.json)와 뼈대 카드(설계 3.7, 3.7.1, 3.7.2). 화면과 서비스, verify_ai, ai_seal, ai_overlap 이
같이 씀. 코드는 실행하지 않고 줄 글만 다룸.

뼈대 하나는 코드 예제(variants)마다 상황 글(situation)과 줄(lines)을 갖고, 카드 넷을 적음. slot 은 코드 예제 전체를 보이고 주 자리와 점차
지우기 단계만큼의 다른 자리를 가린 빈칸, order 는 줄 순서 고르기, pick 은 그 자리에 맞는 줄 고르기, change 는 한 코드 예제를 다른 코드 예제로
바꿀 때 고칠 줄 모두 고르기임. 카드 id 는 pc-k01(slot), pc-o01(order), pc-p01(pick), pc-x01(change). 보기를 섞는 난수는
gen.Rng 라 파이썬 버전이 달라도 같은 시드면 같은 보기가 나옴.
"""
import difflib
import os
import re

import study
from aiprep import bank
from aiprep.gen import Rng

PART_LETTER = {"slot": "k", "order": "o", "pick": "p", "change": "x"}
PART_CHIP = {"slot": "코드 빈칸", "order": "순서 고르기", "pick": "고르기", "change": "고르기"}
PART_KEY = {"slot": "slots", "order": "orders", "pick": "picks", "change": "changes"}
CARD_ORDER = ("order", "pick", "change", "slot")  # 같은 코드 예제 고르기 카드가 slot 카드보다 먼저 나오게 매기는 순서
SIMILAR = 0.5  # diff 짝 풀기 기준
ROTATE_GAP = 3  # 돌려 가며 빈칸에서 틀린 자리를 다시 넣는 거리
PATTERN_FILE = re.compile(r"(S\d+)\.json\Z")
SLOT_STEM = "빈칸에 들어갈 코드를 쓰세요."
ORDER_STEM = "줄의 순서로 **옳은** 것을 고르세요."
ORDER_HEAD = "줄 순서로 옳은 것 고르기"
LINE_HINT = "코드 한 줄"
SAME_WHY = "고친 뒤의 코드에도 같은 줄이 있어 고치지 않습니다."
CHANGE_REV = 2  # 반복 줄을 원본 위치와 블록으로 구분하는 보기 버전


def token_re(token):
    """낱말 경계로 토큰 하나를 찾는 정규식. 앞뒤가 영문·숫자·밑줄이면 다른 낱말로 봄."""
    return re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(str(token)))


def _number(sid):
    found = re.search(r"\d+", sid)
    return (int(found.group(0)) if found else 0, sid)


def _list(value):
    return [str(v) for v in (value or [])]


# 읽기

def load_patterns(root=None):
    """ai/patterns/S*.json 을 {"S1": 뼈대 dict} 로. 폴더가 없으면 {}. 못 읽거나 id 가 파일 이름과 다르거나 코드 예제가 꼴에 맞지
    않으면 bank.AiBankError. 카드 필드의 뜻은 verify_ai 가 보고 여기서는 화면이 멈추지 않을 만큼만 봄."""
    folder = os.path.join(root or bank.AI_DIR, "patterns")
    if not os.path.isdir(folder):
        return {}
    out = {}
    names = [n for n in os.listdir(folder) if PATTERN_FILE.match(n)]
    for name in sorted(names, key=lambda n: _number(n[:-5])):
        sid = PATTERN_FILE.match(name).group(1)
        try:
            data = study.read_json(os.path.join(folder, name))
        except (OSError, ValueError) as error:
            raise bank.AiBankError("patterns/%s 을 읽을 수 없습니다: %s" % (name, error))
        if not isinstance(data, dict) or data.get("id") != sid:
            raise bank.AiBankError("patterns/%s 의 id 가 파일 이름과 다릅니다: %r" % (name, data.get("id") if isinstance(data, dict) else None))
        variants = data.get("variants")
        if not isinstance(variants, dict) or not variants:
            raise bank.AiBankError("patterns/%s 에 코드 예제(variants)이 없습니다." % name)
        for vname, variant in variants.items():
            lines = variant.get("lines") if isinstance(variant, dict) else None
            if not isinstance(lines, list) or not lines or not all(isinstance(line, str) for line in lines):
                raise bank.AiBankError("patterns/%s 의 %s 코드 예제 lines 는 글 목록이어야 합니다." % (name, vname))
        for key in PART_KEY.values():
            entries = data.get(key) or []
            if not isinstance(entries, list) or not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in entries):
                raise bank.AiBankError("patterns/%s 의 %s 는 id 가 있는 객체 목록이어야 합니다." % (name, key))
        out[sid] = data
    return out


def variant_of(skeleton, name):
    """코드 예제 dict. 모르는 코드 예제이면 AiBankError."""
    variant = (skeleton.get("variants") or {}).get(name)
    if not isinstance(variant, dict):
        raise bank.AiBankError("뼈대 %s 에 %s 코드 예제가 없습니다." % (skeleton.get("id"), name))
    return variant


def lines_of(skeleton, name):
    return [str(line) for line in variant_of(skeleton, name).get("lines") or []]


def entry_of(skeleton, part, cid):
    """뼈대에서 그 카드의 원본 dict. 없으면 None."""
    return next((e for e in skeleton.get(PART_KEY[part]) or [] if e.get("id") == cid), None)


def slot_spots(skeleton, variant):
    """그 코드 예제 자리들의 위치 {자리 id: (줄, 시작, 끝, 원본)}. 줄이 코드 예제 밖이거나 토큰이 그 줄에 없으면 AiBankError."""
    lines = lines_of(skeleton, variant)
    out = {}
    for entry in skeleton.get("slots") or []:
        if entry.get("variant") != variant:
            continue
        no = entry.get("line")
        if not isinstance(no, int) or not 0 <= no < len(lines):
            raise bank.AiBankError("자리 %s 의 줄 번호가 %s 코드 예제 밖입니다: %r" % (entry.get("id"), variant, no))
        found = token_re(entry.get("token", "")).search(lines[no]) if entry.get("token") else None
        if found is None:
            raise bank.AiBankError("자리 %s 의 토큰 %r 가 %s 코드 예제 %d번 줄에 없습니다." % (entry.get("id"), entry.get("token"), variant, no))
        out[entry["id"]] = (no, found.start(), found.end(), entry)
    return out


def dedent(lines):
    """여러 줄에 공통인 들여쓰기를 뗀 목록."""
    pads = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    pad = min(pads) if pads else 0
    return [line[pad:] if line.strip() else "" for line in lines]


def _situation(skeleton, variant):
    return str(variant_of(skeleton, variant).get("situation") or "").strip()


def _head(part, entry, skeleton):
    """오답 노트 줄 첫머리. slot 은 주 자리 줄의 토큰만 ____ 로 가리고 들여쓰기를 뗀 것, pick·change 는 지문 첫 줄,
    order 는 지문이 있으면 그 첫 줄 아니면 ORDER_HEAD. 굵게 표시(**)는 뗌."""
    if part == "slot":
        try:
            line = lines_of(skeleton, entry.get("variant"))[entry["line"]]
        except (bank.AiBankError, KeyError, IndexError, TypeError):
            return str(entry.get("token", ""))
        return token_re(entry.get("token", "")).sub("____", line, count=1).strip() if entry.get("token") else line.strip()
    stem = str(entry.get("stem") or "").strip()
    if not stem:
        return ORDER_HEAD if part == "order" else ""
    return stem.split("\n")[0].replace("**", "").strip()


def cards(group, skeletons, units):
    """뼈대들에서 카드 목록을 만듦. group 은 bank.read_index 의 patterns 항목, units 는 {단원 키: {"after", "name", "title"}}
    (l18 meta 에 공개된 단원만). step 의 단원이 units 에 없는 카드는 만들지 않음.

    카드는 bank.cards_of 와 같은 키(id, kind "skel", lesson=무리 id, unit, step, facts, core, prio, family, confuse, level, tags,
    deep, errata, ref, order)에 part, pattern(뼈대 id), variant(change 는 from), after, name(단원 이름), head, situations
    ({코드 예제 이름: 상황 글}, change 는 from·to 둘), entry(원본)를 더한 것. 머리 tags·prio 는 카드가 적지 않으면 물려받고 ref·level 은
    물려받지 않음. order 는 뼈대마다 orders → picks → changes → slots 순."""
    out = []
    for sid in sorted(skeletons, key=_number):
        skeleton = skeletons[sid]
        for part in CARD_ORDER:
            for entry in skeleton.get(PART_KEY[part]) or []:
                step = str(entry.get("step") or "")
                unit = step.split("/")[0]
                if unit not in units:
                    continue
                cid = str(entry["id"])
                variant = entry.get("from") if part == "change" else entry.get("variant")
                shown = [variant] + ([entry.get("to")] if part == "change" else [])
                situations = {}
                for name in shown:
                    if isinstance((skeleton.get("variants") or {}).get(name), dict):
                        situations[name] = _situation(skeleton, name)
                out.append({"id": cid, "kind": "skel", "lesson": group["id"], "unit": unit, "step": entry.get("step"),
                            "facts": _list(entry.get("facts")), "core": bool(entry.get("core")),
                            "prio": int(entry.get("prio") or skeleton.get("prio") or 2), "family": str(entry.get("family") or cid),
                            "confuse": _list(entry.get("confuse")), "level": int(entry.get("level") or 2),
                            "tags": _list(entry.get("tags") or skeleton.get("tags")), "deep": False,
                            "errata": _list(entry.get("errata")), "ref": _list(entry.get("ref")), "order": len(out),
                            "part": part, "pattern": sid, "variant": variant, "after": units[unit].get("after", ""),
                            "name": units[unit].get("name", ""), "head": _head(part, entry, skeleton), "situations": situations,
                            "entry": entry})
    return out


def card_texts(card):
    """카드에서 학습자에게 보이는 글 [(어디, 글, 마크다운인지)]. 코드 예제 situation, 지문, 해설, 빈칸 hint, 고르기 오답의 글(코드라
    마크다운 아님)·why·aim. verify_ai(말투·맥락·그림 참조)와 ai_overlap 이 같이 씀."""
    cid, entry = card["id"], card["entry"]
    out = [("%s:%s 코드 예제 상황" % (cid, name), text, True) for name, text in (card.get("situations") or {}).items()]
    for key in ("stem", "back", "explain"):
        if isinstance(entry.get(key), str):
            out.append(("%s:%s" % (cid, key), entry[key], True))
    if entry.get("hint"):
        out.append(("%s:hint" % cid, entry["hint"], False))
    for n, wrong in enumerate(entry.get("wrong") or [], 1):
        if isinstance(wrong, dict):
            out.append(("%s:보기%d" % (cid, n), str(wrong.get("text", "")), False))
            out.append(("%s:보기%d why" % (cid, n), str(wrong.get("why", "")), False))
            out.append(("%s:보기%d aim" % (cid, n), str(wrong.get("aim", "")), False))
    return out


# 점차 지우기와 뼈대 빈칸

def fade(boxes):
    """점차 지우기 단계 f(설계 3.7.1). boxes 는 상자 목록(None 은 0). 평균이 1 미만이면 0, 2 미만 1, 3 미만 2, 그 밖 3."""
    values = [b or 0 for b in boxes]
    if not values:
        return 0
    mean = sum(values) / float(len(values))
    if mean < 1:
        return 0
    if mean < 2:
        return 1
    if mean < 3:
        return 2
    return 3


def _unique(ids):
    out = []
    for sid in ids:
        if sid not in out:
            out.append(sid)
    return out


def slot_view(card, skeleton, boxes, again=0, masked=None, whole=None):
    """뼈대 빈칸 문항. boxes 는 {같은 코드 예제 slot 카드 가운데 주 자리와 열린 자리의 id: 상자 또는 None}(주 자리를 꼭 넣음, 빠지면
    None 으로 넣음). f = fade(boxes.values()). 함께 가릴 후보는 주 자리 말고 나머지를 (상자, 주 자리에서 떨어진 줄 수, id) 순으로 세운
    것이고, start = (again * f) % 후보 수 에서 min(f, 후보 수)개를 고리처럼 고름. whole 은 f 가 3 이고 주 자리 상자가 4 이상이고
    line_answer 가 있을 때 참이며, 그러면 주 자리 줄 전체를 가리고(들여쓰기는 남김) 같은 줄의 다른 자리는 masked 에서 뺌.
    masked·whole 을 주면(오답 노트, 기록 다시 그리기) 그 값으로 다시 만들고 코드 예제에 없는 자리 id 는 버림.

    돌려주는 값 {"kind": "blank", "stem", "blanks": [{"answer", "mode", "hint", "slot", "main"}](코드 안 위치 순), "explain",
    "skel": {"part": "slot", "fade", "masked", "whole"}}."""
    entry = card["entry"]
    main = card["id"]
    variant = entry.get("variant")
    lines = lines_of(skeleton, variant)
    spots = slot_spots(skeleton, variant)
    if main not in spots:
        raise bank.AiBankError("자리 %s 가 뼈대 %s 의 %s 코드 예제에 없습니다." % (main, skeleton.get("id"), variant))
    boxes = {sid: box for sid, box in (boxes or {}).items() if sid in spots}
    boxes.setdefault(main, None)
    f = fade(list(boxes.values()))
    main_line = spots[main][0]
    can_whole = bool(entry.get("line_answer"))
    if masked is None:
        others = sorted((sid for sid in boxes if sid != main),
                        key=lambda sid: (boxes[sid] or 0, abs(spots[sid][0] - main_line), sid))
        if others:
            start = (int(again) * f) % len(others)
            masked = (others + others)[start:start + min(f, len(others))]
        else:
            masked = []
        whole = f == 3 and (boxes[main] or 0) >= 4 and can_whole
    else:
        masked = [sid for sid in _unique(masked) if sid in spots and sid != main]
        whole = bool(whole) and can_whole
    if whole:
        masked = [sid for sid in masked if spots[sid][0] != main_line]
    by_line = {}
    for sid in [main] + masked:
        by_line.setdefault(spots[sid][0], []).append(sid)
    shown = list(lines)
    marks = []
    for no, ids in by_line.items():
        line = lines[no]
        if whole and no == main_line:
            indent = line[:len(line) - len(line.lstrip(" "))]
            shown[no] = indent + "____"
            marks.append((no, len(indent), main, True))
            continue
        spans = sorted((spots[sid][1], spots[sid][2], sid) for sid in ids)
        text = line
        for start, end, sid in reversed(spans):
            text = text[:start] + "____" + text[end:]
        shown[no] = text
        marks += [(no, start, sid, False) for start, _, sid in spans]
    blanks = []
    for no, _, sid, full in sorted(marks):
        source = spots[sid][3]
        if full:
            blanks.append({"answer": _list(source.get("line_answer")), "mode": "code", "hint": LINE_HINT, "slot": sid, "main": True})
        else:
            blanks.append({"answer": _list(source.get("answer")), "mode": source.get("mode") or "code", "hint": source.get("hint", ""),
                           "slot": sid, "main": sid == main})
    head = _situation(skeleton, variant)
    stem = "%s\n\n```python\n%s\n```" % (SLOT_STEM, "\n".join(shown))
    return {"kind": "blank", "stem": (head + "\n\n" + stem) if head else stem, "blanks": blanks,
            "explain": str(entry.get("explain") or ""), "skel": {"part": "slot", "fade": f, "masked": masked, "whole": whole}}


# 고르기 카드

def _moves(perm):
    """순열 하나에서 이웃 두 줄 바꾸기나 한 줄 옮기기로 닿는 순열 집합."""
    out = set()
    n = len(perm)
    for i in range(n - 1):
        swapped = list(perm)
        swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
        out.add(tuple(swapped))
    for i in range(n):
        for j in range(n):
            if i != j:
                moved = list(perm)
                moved.insert(j, moved.pop(i))
                out.add(tuple(moved))
    out.discard(tuple(perm))
    return out


def order_wrongs(valid):
    """valid 순열들에서 한 번 바꾸기·옮기기로 닿고 valid 가 아닌 순열 목록(정렬함)."""
    valid = {tuple(p) for p in valid}
    pool = set()
    for perm in valid:
        pool |= _moves(perm)
    return sorted(pool - valid)


def _stem(skeleton, variant, text):
    head = _situation(skeleton, variant)
    return (head + "\n\n" + text) if head else text


def order_view(card, skeleton, seed):
    """줄 순서 고르기. Rng("<id> <seed>") 로 정답은 valid 하나, 오답 셋은 valid 하나에서 이웃 두 줄 바꾸기나 한 줄 옮기기로
    만든 것 가운데 valid 가 아니고 서로 다른 것. 보기 글은 줄을 \\n 으로 이은 것(공통 들여쓰기 뺌), 보기 순서도 같은 Rng 로 섞음."""
    entry = card["entry"]
    lines = lines_of(skeleton, entry.get("variant"))
    picked = [lines[k] for k in entry.get("lines") or []]
    valid = [tuple(p) for p in entry.get("valid") or []]
    rng = Rng("%s %d" % (card["id"], int(seed)))
    if not valid:
        raise bank.AiBankError("%s 에 valid 가 없습니다." % card["id"])
    right = rng.pick(valid)
    pool = order_wrongs(valid)
    if len(pool) < 3:
        raise bank.AiBankError("%s 의 오답 보기를 셋 만들 수 없습니다." % card["id"])
    perms = rng.shuffle([right] + rng.sample(pool, 3))
    options = [{"text": "\n".join(dedent([picked[k] for k in perm])), "ok": perm in valid, "why": ""} for perm in perms]
    return {"kind": "choice", "stem": _stem(skeleton, entry.get("variant"), str(entry.get("stem") or ORDER_STEM)), "options": options,
            "pick": "right", "multi": False, "explain": str(entry.get("explain") or ""), "code_options": True, "grid": 2,
            "keep_order": False, "skel": {"part": "order", "seed": int(seed)}}


def pick_view(card, skeleton):
    """상황에 맞는 줄 고르기. 보기는 정답 줄(들여쓰기 뺌, why 는 빈 글)과 wrong 셋(why·aim)이고 순서 섞기는 연습 묶음이 함."""
    entry = card["entry"]
    line = lines_of(skeleton, entry.get("variant"))[entry["line"]].strip()
    options = [{"text": line, "ok": True, "why": ""}]
    for wrong in entry.get("wrong") or []:
        text = "\n".join(dedent(str(wrong.get("text", "")).splitlines()))
        options.append({"text": text, "ok": False, "why": str(wrong.get("why", "")),
                        "aim": str(wrong.get("aim", ""))})
    return {"kind": "choice", "stem": _stem(skeleton, entry.get("variant"), str(entry.get("stem") or "")), "options": options,
            "pick": "right", "multi": False, "explain": str(entry.get("explain") or ""), "code_options": True, "grid": 1,
            "keep_order": False, "skel": {"part": "pick"}}


def _pairs(left, right):
    """두 코드 예제 줄의 짝 [(왼쪽 번호|None, 오른쪽 번호|None, 같은지)]. 같은 줄은 한 행. replace 묶음은 앞에서부터 zip 으로 짝짓고
    짝의 글자 유사도(들여쓰기 뺀 줄의 SequenceMatcher ratio)가 SIMILAR 미만이면 왼쪽만 있는 행과 오른쪽만 있는 행으로 나눔.
    zip 에서 남는 줄과 delete·insert 묶음의 줄은 한쪽만 있는 행."""
    out = []
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            out += [(i1 + k, j1 + k, True) for k in range(i2 - i1)]
            continue
        n = min(i2 - i1, j2 - j1) if op == "replace" else 0
        for k in range(n):
            i, j = i1 + k, j1 + k
            if difflib.SequenceMatcher(None, left[i].strip(), right[j].strip(), autojunk=False).ratio() >= SIMILAR:
                out.append((i, j, False))
            else:
                out += [(i, None, False), (None, j, False)]
        out += [(i, None, False) for i in range(i1 + n, i2)]
        out += [(None, j, False) for j in range(j1 + n, j2)]
    return out


def _change_line(lines, at):
    """같은 대입문이 여러 곳에 있으면 원본 위치와 감싼 블록을 함께 보여 줌."""
    text = lines[at].strip()
    if sum(line.strip() == text for line in lines) < 2:
        return text
    context = [lines[at]]
    indent = len(lines[at]) - len(lines[at].lstrip())
    for line in reversed(lines[:at]):
        depth = len(line) - len(line.lstrip())
        if line.strip() and depth < indent:
            context.insert(0, line)
            indent = depth
            if not indent:
                break
    return "# 원본 %d번째 줄\n%s" % (at + 1, "\n".join(dedent(context)))


def change_view(card, skeleton, seed, back=False, revision=CHANGE_REV):
    """고칠 줄 모두 고르기. from 코드 예제(back 이면 to 코드 예제) 줄 가운데 diff 의 다른 줄 k 개(2~3, 다른 줄 수 이하)를 정답으로 하고 같은 줄을
    더해 보기 4~5개를 코드 순서로 둠. 버전 1은 같은 글의 줄을 합치고 버전 2는 위치와 블록으로 구분함. 난수 키는 id·seed·back임."""
    if revision not in (1, CHANGE_REV):
        raise bank.AiBankError("고칠 줄 보기 버전을 읽을 수 없습니다: %r" % revision)
    entry = card["entry"]
    src, dst = (entry.get("to"), entry.get("from")) if back else (entry.get("from"), entry.get("to"))
    left, right = lines_of(skeleton, src), lines_of(skeleton, dst)

    def line_text(at):
        return left[at].strip() if revision == 1 else _change_line(left, at)

    pairs = _pairs(left, right)
    seen, differ = set(), []
    for i, _, same in pairs:
        if not same and i is not None and left[i].strip() and line_text(i) not in seen:
            seen.add(line_text(i))
            differ.append(i)
    if len(differ) < 2:
        raise bank.AiBankError("%s 의 두 코드 예제는 다른 줄이 %d개입니다(2개 이상)." % (card["id"], len(differ)))
    rng = Rng("%s %d%s" % (card["id"], int(seed), " back" if back else ""))
    k = rng.int(2, min(3, len(differ)))
    chosen = rng.sample(differ, k)
    taken = {line_text(i) for i in chosen}
    pool = []
    for i, _, same in pairs:
        text = line_text(i) if i is not None else ""
        if same and text and text not in taken:
            taken.add(text)
            pool.append(i)
    want = min(len(pool), rng.int(max(0, 4 - k), 5 - k))
    rows = sorted(chosen + rng.sample(pool, want))
    options = [{"text": line_text(i), "ok": i in chosen, "why": "" if i in chosen else SAME_WHY} for i in rows]
    text = entry.get("back") if back else entry.get("stem")
    return {"kind": "choice", "stem": _stem(skeleton, src, str(text or "")), "options": options, "pick": "right", "multi": True,
            "explain": str(entry.get("explain") or ""), "code_options": True, "grid": 1, "keep_order": True,
            "skel": {"part": "change", "seed": int(seed), "back": bool(back), "change_rev": revision}}


def view(card, skeleton, seed, boxes=None, again=0, record=None):
    """카드 한 장의 문항. record 는 기록의 답 줄(오답 노트가 다시 그릴 때)이고 slot 은 masked·whole·fade, order·change 는
    seed·back 을 그대로 씀. change_rev가 없는 기록은 버전 1로 복원함. 새 change는 버전 2이며 again ≥ 1이고 back 지문이 있으면
    반대 방향으로 냄. record와 boxes가 모두 없으면 slot은 f = 0임."""
    part = card.get("part")
    if part == "slot":
        if record is not None:
            made = slot_view(card, skeleton, boxes or {}, again, masked=list(record.get("masked") or []),
                             whole=bool(record.get("whole")))
            if isinstance(record.get("fade"), int):
                made["skel"]["fade"] = record["fade"]
            return made
        return slot_view(card, skeleton, boxes or {}, again)
    if record is not None and record.get("seed") is not None:
        seed = int(record["seed"])
    if part == "order":
        return order_view(card, skeleton, seed)
    if part == "pick":
        return pick_view(card, skeleton)
    if part == "change":
        if record is not None:
            back = bool(record.get("back"))
            revision = int(record.get("change_rev", 1))
        else:
            back = int(again) >= 1 and bool(card["entry"].get("back"))
            revision = CHANGE_REV
        return change_view(card, skeleton, seed, back, revision)
    raise bank.AiBankError("모르는 뼈대 카드 꼴입니다: %r" % part)


# 나란히 보기와 돌려 가며 빈칸

def diff(skeleton, left, right):
    """두 코드 예제를 나란히 보기(설계 3.7.2). {"skel", "left", "right", "rows": [{"left": 글|None, "right": 글|None, "same"}],
    "different": same 이 거짓인 행 수, "same": 참인 행 수}. 모르는 코드 예제이면 AiBankError."""
    a, b = lines_of(skeleton, left), lines_of(skeleton, right)
    rows = [{"left": a[i] if i is not None else None, "right": b[j] if j is not None else None, "same": same}
            for i, j, same in _pairs(a, b)]
    same = sum(1 for row in rows if row["same"])
    return {"skel": skeleton.get("id"), "left": left, "right": right, "rows": rows, "different": len(rows) - same, "same": same}


def rotate_block(skeleton, variant, slot_ids=None):
    """돌려 가며 빈칸 블록 값 {"code": 코드 예제 전체 글, "slots": [{"id", "line", "token", "hint", "mode", "code"(그 자리만 ____)}]}.
    slot_ids 가 없으면 그 코드 예제의 모든 자리. 순서는 코드 위치(줄, 줄 안 위치). 모르는 코드 예제·자리면 AiBankError."""
    lines = lines_of(skeleton, variant)
    spots = slot_spots(skeleton, variant)
    ids = list(spots) if slot_ids is None else _unique(str(s) for s in slot_ids)
    for sid in ids:
        if sid not in spots:
            raise bank.AiBankError("뼈대 %s 의 %s 코드 예제에 자리 %s 가 없습니다." % (skeleton.get("id"), variant, sid))
    ids.sort(key=lambda sid: (spots[sid][0], spots[sid][1]))
    slots = []
    for sid in ids:
        no, start, end, entry = spots[sid]
        shown = list(lines)
        shown[no] = lines[no][:start] + "____" + lines[no][end:]
        slots.append({"id": sid, "line": no, "token": str(entry.get("token")), "hint": str(entry.get("hint") or ""),
                      "mode": entry.get("mode") or "code", "code": "\n".join(shown)})
    return {"code": "\n".join(lines), "slots": slots}


def rotate_next(queue, pos, ok):
    """돌려 가며 빈칸의 다음 자리. queue 는 자리 id 목록, pos 는 지금 자리. 틀리면 queue[pos] 를 pos + 1 + ROTATE_GAP 자리에
    끼우고(남은 게 적으면 맨 끝), 맞든 틀리든 pos + 1. 새 (queue, pos) 를 돌려주며 pos >= len(queue) 면 끝."""
    queue = list(queue)
    if not ok and 0 <= pos < len(queue):
        at = pos + 1 + ROTATE_GAP
        if at >= len(queue):
            queue.append(queue[pos])
        else:
            queue.insert(at, queue[pos])
    return queue, pos + 1
