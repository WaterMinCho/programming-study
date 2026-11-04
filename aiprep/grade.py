# -*- coding: utf-8 -*-
"""빈칸·고르기 채점(설계 3.2, 3.4, 3.9). 서비스, 학습 단원의 떠올리기, verify_ai 의 블라인드 대조, 생성기 대조가 모두 이 함수를 씀.

빈칸은 모드마다 입력과 정답을 같은 규칙으로 정규화해 비교함. word 는 낱말(공백·붙임표·조사 차이를 받음), code 는 코드 토큰
(대소문자 그대로, 빈칸 좌우 문맥과 끝의 () 를 받음), number 는 계산 값(Fraction 으로 비교, places 면 반올림), shape 는 텐서
모양(정수 튜플), values 는 배열 값(중첩 목록, True·False 는 1·0 과 다름), exact 는 앞뒤 공백만 뗀 글임. 읽지 못한 입력은
None 으로 정규화되어 틀림이 됨.
"""
import decimal
import fractions
import re
import unicodedata

BLANK = re.compile(r"_{4,}")
MODES = ("word", "code", "number", "shape", "values", "exact")
PARTICLES = ("입니다", "이다", "으로", "을", "를", "이", "가", "은", "는", "의", "와", "과", "로")  # 긴 것부터 뗌
QUOTES = "'\"`‘’“”「」『』"
WORD_JOIN = re.compile("[\\s\\-‐‑–\u2014·・‧_]+")
MINUS = {"−": "-", "–": "-"}
CURLY = {"‘": "'", "’": "'", "“": '"', "”": '"'}
NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\Z")
RATIO = re.compile(r"[+-]?\d+/\d+\Z")
SHELL = re.compile(r"dtype\s*=\s*[\w.]+|requires_grad\s*=\s*\w+|device\s*=\s*'[^']*'")


def _nfkc(text):
    return unicodedata.normalize("NFKC", str(text or ""))


def _minus(text):
    for bad, good in MINUS.items():
        text = text.replace(bad, good)
    return text


# 모드별 정규화

def _word(text):
    s = _nfkc(text).strip()
    s = s.strip(QUOTES + " \t\r\n")
    s = s.rstrip(".。").strip(QUOTES + " ")
    s = s.casefold()
    return WORD_JOIN.sub("", s)


def _code(text):
    s = _nfkc(text).replace("`", "")
    for bad, good in CURLY.items():
        s = s.replace(bad, good)
    s = s.replace('"', "'")
    return re.sub(r"\s+", "", s)


NUMBER_MAX = 40  # 숫자 하나로 받는 입력 길이와 지수의 상한. 1e100000000 같은 입력이 화면을 멈추지 않게 함


def _fraction(s):
    if len(s) > NUMBER_MAX:
        return None
    if RATIO.match(s):
        top, bottom = s.split("/")
        if int(bottom) == 0:
            return None
        return fractions.Fraction(int(top), int(bottom))
    if NUMBER.match(s):
        number = decimal.Decimal(s)
        return fractions.Fraction(number) if abs(number.adjusted()) <= NUMBER_MAX else None
    return None


def _number(text, unit=None):
    s = _minus(_nfkc(text)).strip()
    s = re.sub(r"\s+", "", s)
    if unit:
        tail = re.sub(r"\s+", "", _nfkc(unit))
        if tail and s.endswith(tail):
            s = s[:-len(tail)]
    s = s.replace(",", "")
    return _fraction(s) if s else None


def _round(value, places):
    """Fraction 을 소수 places 자리로 반올림(ROUND_HALF_UP)한 Decimal."""
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        exact = decimal.Decimal(value.numerator) / decimal.Decimal(value.denominator)
        return exact.quantize(decimal.Decimal(1).scaleb(-int(places)), rounding=decimal.ROUND_HALF_UP)


def _shape(text):
    s = _nfkc(text).strip()
    s = re.sub(r"^torch\s*\.\s*Size", "", s)
    s = re.sub("[xX×*]", ",", s)
    s = re.sub(r"[\[\]()]", " ", s)
    parts = [p for p in re.split(r"[,\s]+", s) if p]
    if not all(re.fullmatch(r"\d+", p) for p in parts):
        return None
    if not parts and not re.fullmatch(r"(?:torch\.Size)?(?:\(\)|\[\]|\(\[\]\))", re.sub(r"\s+", "", _nfkc(text))):
        return None  # 빈 모양은 () 나 [] 처럼 괄호를 쓴 답만 받음. x·쉼표·* 만 쓴 답은 틀림
    return tuple(int(p) for p in parts)


class _Values(object):
    """배열 값 글을 중첩 목록으로 읽는 작은 파서. tensor(…)·array(…) 같은 껍데기는 첫 인자만 남기고 dtype= 같은 키워드는 버림.
    원소는 ("n", Decimal) 이나 ("b", True/False) 로 둬서 True 와 1 을 다르게 봄."""

    TOKEN = re.compile(r"\s*(?:(?P<num>[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)|(?P<name>[A-Za-z_][\w.]*)|(?P<op>[\[\](),=]))")

    def __init__(self, text):
        self.tokens = []
        pos, text = 0, text.strip()
        while pos < len(text):
            found = self.TOKEN.match(text, pos)
            if not found or found.end() == pos:
                raise ValueError(text[pos:pos + 10])
            kind = found.lastgroup
            self.tokens.append((kind, found.group(kind)))
            pos = found.end()
            while pos < len(text) and text[pos].isspace():
                pos += 1
        self.at = 0

    def peek(self):
        return self.tokens[self.at] if self.at < len(self.tokens) else (None, None)

    def take(self, op=None):
        token = self.peek()
        if token[0] is None or (op is not None and token != ("op", op)):
            raise ValueError("expected %r" % op)
        self.at += 1
        return token

    def items(self, close):
        out, comma = [], False
        while self.peek() != ("op", close):
            out.append(self.value())
            comma = False
            if self.peek() == ("op", ","):
                self.take(",")
                comma = True
        self.take(close)
        return out, comma

    def value(self):
        kind, text = self.peek()
        if kind == "num":
            self.take()
            number = decimal.Decimal(text)
            if abs(number.adjusted()) > NUMBER_MAX:
                raise ValueError(text)
            return ("n", number)
        if kind == "name":
            self.take()
            if text in ("True", "False"):
                return ("b", text == "True")
            if self.peek() != ("op", "("):
                raise ValueError(text)
            self.take("(")
            args = []
            while self.peek() != ("op", ")"):
                if self.peek()[0] == "name" and self.tokens[self.at + 1:self.at + 2] == [("op", "=")]:
                    self.take()
                    self.take("=")
                    self.value()
                else:
                    args.append(self.value())
                if self.peek() == ("op", ","):
                    self.take(",")
            self.take(")")
            if len(args) != 1:
                raise ValueError("shell")
            return args[0]
        if (kind, text) == ("op", "["):
            self.take("[")
            return self.items("]")[0]
        if (kind, text) == ("op", "("):
            self.take("(")
            out, comma = self.items(")")
            return out[0] if len(out) == 1 and not comma else out
        raise ValueError(text)

    def parse(self):
        first = self.value()
        if self.peek() == ("op", ","):
            out = [first]
            while self.peek() == ("op", ","):
                self.take(",")
                if self.peek()[0] is None:
                    break
                out.append(self.value())
            first = out
        if self.peek()[0] is not None:
            raise ValueError("trailing")
        return first


def _values(text):
    s = _minus(_nfkc(text)).strip()
    s = SHELL.sub("", s)
    if not s:
        return None
    try:
        return _Values(s).parse()
    except (ValueError, IndexError, decimal.InvalidOperation, RecursionError):  # 괄호를 수백 겹 연 입력은 틀린 답
        return None


def _round_values(value, places):
    if isinstance(value, list):
        return [_round_values(v, places) for v in value]
    if value[0] == "n" and places is not None:
        return ("n", _round(fractions.Fraction(value[1]), places))
    if value[0] == "n":
        return ("n", value[1].normalize() if value[1] != 0 else decimal.Decimal(0))
    return value


def norm(mode, text, blank=None):
    """입력이나 정답 글을 모드 규칙으로 정규화함. 읽지 못하면 None(틀림). blank 는 unit·places 를 읽을 칸."""
    blank = blank or {}
    places = blank.get("places")
    if mode == "word":
        return _word(text) or None
    if mode == "code":
        return _code(text) or None
    if mode == "number":
        value = _number(text, blank.get("unit"))
        if value is None:
            return None
        return _round(value, places) if places is not None else value
    if mode == "shape":
        return _shape(text)
    if mode == "values":
        value = _values(text)
        return None if value is None else _round_values(value, places)
    if mode == "exact":
        return _nfkc(text).strip() or None
    raise ValueError("모르는 빈칸 모드: %r" % mode)


# 낱말 사전(terms.json)의 동의어

def term_map(terms):
    """terms.json 의 term·also·accept 를 {정규화한 꼴: 같은 낱말의 정규화한 꼴 묶음} 으로. terms 는 terms.json 내용이나
    그 "terms" 목록. 이미 만든 사전이면 그대로 돌려줌. 다른 낱말의 term·also 인 꼴이 accept 에 있어도 그 낱말 쪽 묶음은 넓히지
    않음(미분값의 accept 기울기가 기울기 빈칸에 미분값을 받게 하지 않음)."""
    if not terms:
        return {}
    if isinstance(terms, dict) and "terms" not in terms:
        return terms
    entries = terms["terms"] if isinstance(terms, dict) else terms
    def heads(entry):
        return {f for f in (_word(x) for x in [entry.get("term", "")] + list(entry.get("also") or [])) if f}

    named = set().union(*[heads(entry) for entry in entries])
    out = {}
    for entry in entries:
        forms = [entry.get("term", "")] + list(entry.get("also") or []) + list(entry.get("accept") or [])
        group = frozenset(f for f in (_word(x) for x in forms) if f)
        own = heads(entry)
        for form in group:
            if form in own or form not in named:
                out[form] = out.get(form, frozenset()) | group
    return out


def _code_variants(value, answers, context):
    """code 모드에서 한 번 더 비교할 입력 꼴. 빈칸 좌우 문맥을 포함한 꼴과 정답에 없는 끝의 () ·앞의 . 을 뗀 꼴."""
    out = {value}
    left, right = context or ("", "")
    left, right = _code(left), _code(right)
    for k in range(len(left), 0, -1):
        if value.startswith(left[-k:]):
            out.add(value[k:])
            break
    for v in list(out):
        for k in range(len(right), 0, -1):
            if v.endswith(right[:k]) and len(v) > k:
                out.add(v[:-k])
                break
    if not any(a.endswith("()") for a in answers):
        out |= {v[:-2] for v in out if v.endswith("()") and len(v) > 2}
    if not any(a.startswith(".") for a in answers):
        out |= {v[1:] for v in out if v.startswith(".") and len(v) > 1}
    return out


def grade_blank(blank, value, terms=None):
    """칸 하나가 맞는지. blank 는 {"answer", "mode", 선택 "term", "places", "unit", "context"}. context 는 grade_item 이 지문에서
    잘라 넣는 빈칸 좌우 글. 빈 입력은 틀림."""
    if value is None or not str(value).strip():
        return False
    mode = blank.get("mode") or "word"
    answers = [str(a) for a in blank.get("answer") or []]
    terms = term_map(terms)
    if mode == "word":
        wanted = {_word(a) for a in answers}
        for name in [blank.get("term")] + answers:
            if name:
                wanted |= terms.get(_word(name), frozenset())
        wanted.discard("")
        got = _word(value)
        if got in wanted:
            return True
        for tail in PARTICLES:
            if got.endswith(tail) and got[:-len(tail)] in wanted:
                return True
        return False
    if mode == "code":
        wanted = {_code(a) for a in answers}
        return bool(_code_variants(_code(value), wanted, blank.get("context")) & wanted)
    got = norm(mode, value, blank)
    if got is None:
        return False
    return any(got == norm(mode, a, blank) for a in answers)


def contexts(stem):
    """지문의 빈칸마다 (왼쪽, 오른쪽) 문맥. 같은 줄에서 빈칸 바로 앞뒤에 붙은 공백 없는 글자."""
    out = []
    text = stem or ""
    for found in BLANK.finditer(text):
        line_start = text.rfind("\n", 0, found.start()) + 1
        line_end = text.find("\n", found.end())
        line_end = len(text) if line_end < 0 else line_end
        left = re.search(r"(\S*)\Z", text[line_start:found.start()]).group(1)
        right = re.match(r"(\S*)", text[found.end():line_end]).group(1)
        out.append((left, right))
    return out


def grade_item(item, value, terms=None):
    """빈칸 문항 채점. value 는 칸마다 입력 글의 목록. 모두 맞으면 pass, 일부 partial, 하나도 안 맞거나 비었으면 stuck."""
    blanks = item.get("blanks") or []
    values = list(value or [])
    values += [""] * (len(blanks) - len(values))
    terms = term_map(terms)
    sides = contexts(item.get("stem", ""))
    per = []
    for n, blank in enumerate(blanks):
        if n < len(sides) and "context" not in blank:
            blank = dict(blank, context=sides[n])
        per.append(grade_blank(blank, values[n], terms))
    if per and all(per):
        result = "pass"
    elif any(per):
        result = "partial"
    else:
        result = "stuck"
    return {"result": result, "per_blank": per}


def grade_skel(view, values, terms=None):
    """뼈대 빈칸 채점(설계 3.7.1). view 는 skel.slot_view 결과(칸마다 slot·main). 칸마다 grade_item 규칙(빈칸 좌우 문맥 떼기)으로
    채점하고 result 는 주 자리(main) 칸만으로 pass·stuck 을 정함. 주 자리가 아닌 틀린 칸은 also 에 {자리 id: "stuck"} 로 넣음.
    빈 값은 그 칸 틀림이고 partial 은 없음. 첫 인자가 카드가 아니라 view 인 것은 함께 가린 칸이 view 마다 달라서임."""
    graded = grade_item(view, values, terms)
    blanks = view.get("blanks") or []
    per = graded["per_blank"]
    mains = [ok for blank, ok in zip(blanks, per) if blank.get("main")]
    also = {str(blank["slot"]): "stuck" for blank, ok in zip(blanks, per) if not blank.get("main") and not ok and blank.get("slot")}
    return {"result": "pass" if mains and all(mains) else "stuck", "per_blank": per, "also": also}


def right_options(item):
    """고르기 문항의 답 보기 번호(원래 순서, 0부터). pick 이 right 면 ok 가 참인 보기, wrong 이면 거짓인 보기."""
    want = (item.get("pick") or "right") == "right"
    return [n for n, option in enumerate(item.get("options") or []) if bool(option.get("ok")) == want]


def grade_choice(item, picked):
    """고른 보기 번호(원래 순서)의 집합이 답 집합과 같으면 pass. 부분 점수 없음."""
    right = right_options(item)
    try:
        chosen = sorted({int(p) for p in (picked or [])})
    except (TypeError, ValueError):
        chosen = []
    return {"result": "pass" if chosen and chosen == sorted(right) else "stuck", "right": right}
