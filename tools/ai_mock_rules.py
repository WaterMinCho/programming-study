# -*- coding: utf-8 -*-
"""모의고사의 회차별 배분과 문항 구성·겹침을 계산함. 코드와 강의 내용을 실행하지 않음."""
import ast
import collections
import re
import unicodedata


LESSON_COUNTS = {
    "m1": (1, 2, 2, 4, 2, 2, 2, 3, 2, 4, 3, 3, 0, 0, 0, 0, 0),
    "m2": (1, 2, 2, 3, 2, 2, 1, 2, 2, 2, 2, 2, 2, 2, 1, 2, 0),
    "m3": (2, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 1, 2, 2, 2, 2, 1),
}
TOKEN = re.compile(r"\d+(?:\.\d+)?(?:e[+-]?\d+)?|[^\W\d]\w*", re.UNICODE)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([^\s]*)\s*$")
BLANK = re.compile(r"_{4,}")


def normalized(text):
    return unicodedata.normalize("NFKC", str(text)).casefold()


def tokens(text):
    """지문의 어절·식별자·숫자를 집합으로 만들며 빈칸 표시는 뺌."""
    return frozenset(word for word in TOKEN.findall(normalized(text)) if word.strip("_"))


def jaccard(left, right):
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def overlap(left, right):
    """경계 3/5를 부동소수점 오차 없이 비교함."""
    return bool(left or right) and 5 * len(left & right) >= 3 * len(left | right)


def _numeric_tree(node):
    if isinstance(node, ast.Constant):
        return type(node.value) in (int, float, complex)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return bool(node.elts) and all(_numeric_tree(n) for n in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return _numeric_tree(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
        return _numeric_tree(node.left) and _numeric_tree(node.right)
    if isinstance(node, ast.Call) and not node.keywords and len(node.args) == 1:
        name = ast.unparse(node.func)
        return name in ("tensor", "torch.tensor", "torch.Size", "array", "np.array") and _numeric_tree(node.args[0])
    return False


def numeric_answer(answer):
    """숫자 상수·숫자 배열·산술식을 식별하며 식을 계산하지 않음."""
    text = unicodedata.normalize("NFKC", str(answer)).strip().strip("`").replace("−", "-")
    text = re.sub(r"\s*(?:개|칸|배|차원|%)\s*$", "", text)
    try:
        return _numeric_tree(ast.parse(text, mode="eval").body)
    except (SyntaxError, ValueError, TypeError, RecursionError):
        return False


def numeric_blank(blank):
    answers = blank.get("answer")
    return blank.get("mode", "word") in ("number", "shape", "values") or any(
        numeric_answer(answer) for answer in (answers if isinstance(answers, list) else []) if isinstance(answer, str))


def blank_category(item):
    """섞인 빈칸도 문항 하나를 범주 하나로 셈. 값, 낱말, 코드 순서로 분류함."""
    blanks = item.get("blanks") or []
    if not isinstance(blanks, list) or not blanks or not all(isinstance(b, dict) for b in blanks):
        return None
    if any(numeric_blank(blank) for blank in blanks):
        return "value"
    if all(blank.get("mode") == "code" for blank in blanks):
        return "code"
    return "word"


def code_blocks(text):
    """울타리의 언어·내용과 닫히지 않은 울타리 여부를 돌려줌."""
    blocks, opened, body = [], None, []
    for line in str(text).splitlines():
        mark = FENCE.match(line)
        if opened is None:
            if mark:
                opened, body = (mark.group(1), mark.group(2).lower()), []
        elif mark and not mark.group(2) and mark.group(1)[0] == opened[0][0] and len(mark.group(1)) >= len(opened[0]):
            blocks.append((opened[1], "\n".join(body)))
            opened = None
        else:
            body.append(line)
    return blocks, opened is not None


def assignment_code(item):
    return item.get("kind") == "blank" and blank_category(item) == "code" and any(
        BLANK.search(body) for language, body in code_blocks(item.get("stem", ""))[0] if language in ("", "py", "python"))


def numeric_choices(item):
    options = item.get("options") or []
    return isinstance(options, list) and any(
        isinstance(o, dict) and numeric_answer(o.get("text", "")) for o in options)


def blueprint(mid):
    return {"i%02d" % n: count for n, count in enumerate(LESSON_COUNTS[mid], 1) if count}


def exam_problems(mid, entry, meta, items, pattern_ids):
    """30문항 회차의 메타와 배분을 대조해 실패 문구 목록을 돌려줌."""
    out = []
    expected = blueprint(mid)
    bounds = [1, 12 if mid == "m1" else 17]
    if type(meta.get("format")) is not int or meta.get("format") != 1 or meta.get("id") != mid:
        out.append("meta.json의 format=1과 id=%s를 확인하세요." % mid)
    for source, values in (("index", entry), ("meta.json", meta)):
        if type(values.get("count")) is not int or values.get("count") != 30:
            out.append("%s의 count는 30이어야 합니다." % source)
        if type(values.get("minutes")) is not int or values.get("minutes") != 60:
            out.append("%s의 minutes는 60이어야 합니다." % source)
    if entry.get("range") != bounds or ("range" in meta and meta["range"] != bounds):
        out.append("%s의 range는 %s여야 합니다." % (mid, bounds))
    declared = meta.get("blueprint")
    if not isinstance(declared, dict) or any(type(value) is not int or value < 0 for value in declared.values()):
        out.append("meta.json의 blueprint는 차시별 0 이상 정수 객체여야 합니다.")
    elif any(key not in {"i%02d" % n for n in range(1, 18)} for key in declared) or {
            key: value for key, value in declared.items() if value} != expected:
        out.append("meta.json의 blueprint가 %s의 차시별 원표와 일치하지 않습니다." % mid)
    lessons = collections.Counter(item.get("lesson") for item in items if isinstance(item.get("lesson"), str))
    if dict(lessons) != expected:
        out.append("%s의 차시별 문항 수가 원표와 일치하지 않습니다: %s" % (mid, dict(sorted(lessons.items()))))
    kinds = collections.Counter(item.get("kind") for item in items if isinstance(item.get("kind"), str))
    if kinds != {"blank": 14, "choice": 16}:
        out.append("빈칸 14개·고르기 16개여야 합니다: %s" % dict(kinds))
    categories = collections.Counter(blank_category(item) for item in items if item.get("kind") == "blank")
    if categories["code"] < 6 or categories["value"] < 5 or categories["word"] > 3:
        out.append("빈칸은 코드 6개 이상·계산/모양 5개 이상·낱말 3개 이하여야 합니다: %s" % dict(categories))
    picks = collections.Counter("multi" if item.get("multi") is True else str(item.get("pick")) for item in items if item.get("kind") == "choice")
    if picks != {"right": 7, "wrong": 6, "multi": 3}:
        out.append("고르기는 right 7개·wrong 6개·multi 3개여야 합니다: %s" % dict(picks))
    levels = collections.Counter(item.get("level") for item in items if type(item.get("level")) is int)
    if levels != {1: 8, 2: 15, 3: 7}:
        out.append("level 1/2/3은 8/15/7개여야 합니다: %s" % dict(levels))
    topics = collections.Counter()
    assignments = patterns = 0
    for item in items:
        cid = item.get("id", "?")
        topic = item.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            out.append("%s의 topic에 실제 개념명을 적으세요." % cid)
        else:
            topics[re.sub(r"[\s_·-]+", "", normalized(topic))] += 1
        for key in ("assignment", "deep", "multi"):
            if key in item and type(item[key]) is not bool:
                out.append("%s의 %s는 bool이어야 합니다." % (cid, key))
        if item.get("assignment") is True:
            if assignment_code(item):
                assignments += 1
            else:
                out.append("%s의 assignment=true는 코드 토큰을 채우는 코드 울타리 빈칸이어야 합니다." % cid)
        if "pattern" in item:
            pattern = item["pattern"]
            if not isinstance(pattern, str) or pattern not in pattern_ids:
                out.append("%s의 pattern이 존재하는 뼈대 ID가 아닙니다: %r" % (cid, pattern))
            else:
                patterns += 1
    if assignments < 5:
        out.append("과제형 코드 빈칸이 %d개입니다(5개 이상)." % assignments)
    if patterns < 3:
        out.append("상황별 코드 pattern 문항이 %d개입니다(3개 이상)." % patterns)
    for topic, count in sorted(topics.items()):
        if count > 2:
            out.append("topic %s가 한 회에 %d개입니다(2개 이하)." % (topic, count))
    return out


def question_key(item):
    """답·해설·보기 순서를 바꿔도 같은 지문과 보기의 문항을 식별함."""
    def text_key(text):
        return tuple(re.findall(r"\w+|[^\w\s]", normalized(text).replace("−", "-")))
    options = item.get("options") if isinstance(item.get("options"), list) else []
    return item.get("kind"), text_key(item.get("stem", "")), tuple(sorted(
        text_key(option.get("text", "")) for option in options if isinstance(option, dict)))


def cross_problems(mid, exams):
    """검사 중인 회차와 관계된 회차 간 중복·사실 사용 위반을 돌려줌."""
    out, by_fact = [], collections.defaultdict(set)
    mine = exams.get(mid, [])
    for other, items in sorted(exams.items()):
        if other == mid:
            continue
        for item in mine:
            for candidate in items:
                same_id = item.get("id") and item.get("id") == candidate.get("id")
                if same_id or (item.get("stem") and question_key(item) == question_key(candidate)):
                    out.append("회차 간 같은 문항입니다: %s / %s %s" % (item.get("id"), other, candidate.get("id")))
    for exam, items in exams.items():
        for item in items:
            facts = item.get("facts") if isinstance(item.get("facts"), list) else []
            for fid in facts:
                if isinstance(fid, str):
                    by_fact[fid].add(exam)
    for fid, owners in sorted(by_fact.items()):
        if mid in owners and len(owners) > 2:
            out.append("사실 %s를 %s에서 사용했습니다(세 회 중 2회 이하)." % (fid, ", ".join(sorted(owners))))
    return out


def practice_problems(items, practice):
    """연습 지문의 토큰 자카드가 0.6 이상인 모의고사 지문을 찾음."""
    out = []
    for item in items:
        left = tokens(item.get("stem", ""))
        best = None
        for source, right in practice:
            if overlap(left, right):
                score = jaccard(left, right)
                if best is None or score > best[0]:
                    best = score, source
        if best:
            out.append("%s의 연습 지문 토큰 자카드가 0.6 이상입니다: %s %.3f" % (item.get("id"), best[1], best[0]))
    return out
