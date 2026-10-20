# -*- coding: utf-8 -*-
"""여정 문제의 값 처리. 타입 문법, 값 검사, 정규 JSON, 해시, 언어별 표시, 사용자 입력 해석, 시작 코드.

반환형은 int · str · bool 과 그 리스트만임. 자식 하네스가 내보낸 JSON 을 부모가 여기의 canonical 로 다시 정규화해
기대값과 바이트 단위로 비교함. harness.py 는 저장소 모듈을 import 하지 않으므로 같은 규칙을 따로 가지고 있음.
"""
import ast
import hashlib
import json
import math

SAFE_MAX = 2 ** 53 - 1
BASE_TYPES = ("int", "str", "bool")
MAX_DEPTH = 64  # 반환값 리스트가 겹칠 수 있는 단계. 하네스와 같은 값임
LANGS = ("python", "javascript")

NONE_NOTE = "None 을 반환했습니다. return 을 빠뜨렸는지 확인하세요."
TUPLE_NOTE = "튜플을 반환했습니다. 리스트로 바꿔 반환하세요."
SET_NOTE = "집합을 반환했습니다. 리스트로 바꿔 반환하세요."
DICT_NOTE = "딕셔너리를 반환했습니다. 리스트로 바꿔 반환하세요."
GENERATOR_NOTE = "제너레이터를 반환했습니다. list(...) 로 감싸 반환하세요."
FLOAT_NOTE = "유한하지 않은 실수(%s)를 반환했습니다."
OTHER_NOTE = "%s 타입은 반환할 수 없습니다. 정수·문자열·불리언이나 그 리스트로 반환하세요."
DEPTH_NOTE = "리스트가 64겹을 넘게 겹쳐 있습니다. 반복문 안에서 answer = [answer, x] 처럼 리스트를 다시 감싸고 있는지 확인하세요."
LITERAL_NOTE = '값을 읽지 못했습니다. JSON 이나 파이썬 리터럴로 적어 주세요. 예) [1, 2, 3], "abc", true'
LITERAL_KIND_NOTE = "딕셔너리와 집합은 쓸 수 없습니다. 정수·문자열·불리언이나 그 리스트만 적어 주세요."


# 타입 문법

def parse_type(text):
    """`int | str | bool | list[T]` 를 읽어 "int" 같은 글자나 ("list", 안쪽) 튜플로 돌려줌. 틀리면 ValueError."""
    text = text.strip()
    if text in BASE_TYPES:
        return text
    if text.startswith("list[") and text.endswith("]"):
        return ("list", parse_type(text[5:-1]))
    raise ValueError("타입을 읽지 못했습니다: %r (int, str, bool, list[...] 만 쓸 수 있습니다)" % text)


def type_text(kind):
    if isinstance(kind, tuple):
        return "list[%s]" % type_text(kind[1])
    return kind


def check(value, kind, where=""):
    """값이 타입에 맞으면 None, 아니면 어긴 점의 문구. 정수는 bool 이 아니고 |x| <= 2^53-1 이어야 함."""
    if isinstance(kind, str):
        kind = parse_type(kind)
    if isinstance(kind, tuple):
        if not isinstance(value, list):
            return "%s리스트가 아닙니다: %s" % (where, show(value, "python", 60))
        for index, item in enumerate(value):
            problem = check(item, kind[1], "%s%d번째 원소: " % (where, index + 1))
            if problem:
                return problem
        return None
    if kind == "int":
        if isinstance(value, bool):
            return "%s정수 자리에 불리언이 있습니다: %s" % (where, show(value, "python", 60))
        if not isinstance(value, int):
            return "%s정수가 아닙니다: %s" % (where, show(value, "python", 60))
        if abs(value) > SAFE_MAX:
            return "%s정수의 절댓값이 2^53-1 을 넘습니다: %d" % (where, value)
        return None
    if kind == "str":
        if not isinstance(value, str):
            return "%s문자열이 아닙니다: %s" % (where, show(value, "python", 60))
        return None
    if not isinstance(value, bool):
        return "%s불리언이 아닙니다: %s" % (where, show(value, "python", 60))
    return None


# 정규 JSON 과 해시

def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(text):
    """정규 JSON 글의 sha256. 학생이 짝 없는 서로게이트('\\ud800')를 반환해도 예외 없이 해시가 나오게 surrogatepass 로 바꿈."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def result_text(values, bundle):
    """자식이 돌려준 정규 JSON 목록을 기대값과 비교할 글로 합침. 묶음은 결과 목록 전체의 정규 JSON 임."""
    if bundle:
        return "[" + ",".join(values) + "]"
    return values[0]


def matches(text, expected=None, expected_sha=None):
    """정규 JSON 글이 기대값(정규 JSON 글)이나 그 sha256 과 같은지."""
    if expected is not None:
        return text == expected
    if expected_sha is not None:
        return digest(text) == expected_sha
    return True


def reject_py(value, depth=1):
    """하네스와 같은 규칙으로 허용하지 않는 반환값의 이유를 돌려줌. 허용하면 빈 글. depth 는 value 가 리스트일 때 몇 겹째인지."""
    if value is None or isinstance(value, (bool, int, str)):
        return ""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return FLOAT_NOTE % repr(value)
        return ""
    if isinstance(value, list):
        if depth > MAX_DEPTH:
            return DEPTH_NOTE
        for item in value:
            bad = reject_py(item, depth + 1)
            if bad:
                return bad
        return ""
    if isinstance(value, tuple):
        return TUPLE_NOTE
    if isinstance(value, (set, frozenset)):
        return SET_NOTE
    if isinstance(value, dict):
        return DICT_NOTE
    if hasattr(value, "__next__"):
        return GENERATOR_NOTE
    return OTHER_NOTE % type(value).__name__


def encode_py(value):
    """반환값을 (정규 JSON, 참고 문구) 로. 허용하지 않는 값이면 (None, 이유). 최상위 None 은 return 을 빠뜨린 것으로 봄."""
    if value is None:
        return None, NONE_NOTE
    bad = reject_py(value)
    if bad:
        return None, bad
    return canonical(value), ""


# 표시

def show(value, lang, limit=300):
    """값을 그 언어의 글로. Python 은 repr 꼴(['a', 'b'], True, None), JS 는 JSON 꼴(["a", "b"], true, null)."""
    if lang == "javascript":
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        except (TypeError, ValueError):
            text = repr(value)
    else:
        text = repr(value)
    if len(text) > limit:
        return text[:limit] + "… (전체 %d자)" % len(text)
    return text


def show_args(args, lang, limit=300):
    """solution 의 인자들을 쉼표로 이어 보여 줌. 화면의 "입력값 〉" 줄에 씀."""
    return ", ".join(show(arg, lang, limit) for arg in args)


# 사용자 입력

def parse_literal(text):
    """JSON 으로 먼저 읽고, 안 되면 파이썬 리터럴(True/False/None, 작은따옴표)로 읽음. 튜플은 리스트로 바꾸고 딕셔너리·집합은 거부."""
    text = text.strip()
    if not text:
        raise ValueError(LITERAL_NOTE)
    try:
        value = json.loads(text)
    except ValueError:
        try:
            value = ast.literal_eval(text)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            raise ValueError(LITERAL_NOTE)
    return _plain(value)


def _plain(value):
    if isinstance(value, (dict, set, frozenset)):
        raise ValueError(LITERAL_KIND_NOTE)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValueError(LITERAL_NOTE)
    if isinstance(value, (bytes, complex)):
        raise ValueError(LITERAL_NOTE)
    return value


# 시작 코드

INITIAL = {
    "python": {"int": "0", "str": "''", "bool": "True", "list": "[]"},
    "javascript": {"int": "0", "str": "''", "bool": "true", "list": "[]"},
}


def starter(signature, lang):
    """problem.json 의 signature 로 두 언어의 시작 코드를 만듦. answer 초깃값은 반환형으로 정함."""
    names = ", ".join(param["name"] for param in signature["params"])
    returns = parse_type(signature["returns"])
    initial = INITIAL[lang]["list" if isinstance(returns, tuple) else returns]
    if lang == "javascript":
        return "function solution(%s) {\n    var answer = %s;\n    return answer;\n}\n" % (names, initial)
    return "def solution(%s):\n    answer = %s\n    return answer\n" % (names, initial)
