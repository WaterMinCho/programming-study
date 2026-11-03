# -*- coding: utf-8 -*-
"""1차시 생성기. 파라미터 갱신, 대입과 copy, 합성 함수, 리스트 슬라이스 계산.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Decimal 로 계산해 글로 바꿈.
"""
from decimal import Decimal

from aiprep.gen import gen, blank, num

MINUS = "−"


def dec(text):
    """Decimal 을 지수 표기 없이 짧은 글로. 1.20 은 1.2, 2.0 은 2."""
    value = Decimal(text) if not isinstance(text, Decimal) else text
    out = format(value.normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return "0" if out in ("-0", "") else out


def shown(text):
    """화면에 보일 숫자. 빼기는 빼기표로."""
    return dec(text).replace("-", MINUS)


def paren(text):
    """음수면 괄호로 감싼 화면 숫자."""
    out = shown(text)
    return "(%s)" % out if out.startswith(MINUS) else out


@gen("i01-g01", unit="1a", level=2, tags=["갱신식"], ref=["1차시 슬 p7"],
     step="1a/3", facts=["F01-05"], basis="lecture-formula", family="update", prio=3)
def update(r):
    """갱신식 Param − lr × grad 한 번. Param 은 −2~2(0.5 간격, 0 제외), lr 0.1·0.01·0.5, grad −10~10(0 제외 정수)."""
    p = Decimal(r.pick(["-2", "-1.5", "-1", "-0.5", "0.5", "1", "1.5", "2"]))
    lr = Decimal(r.pick(["0.1", "0.01", "0.5"]))
    g = Decimal(r.pick([k for k in range(-10, 11) if k != 0]))
    right = p - lr * g
    wrong = p + lr * g
    return blank(
        stem="파라미터 갱신식 Param = Param − (lr × grad) 에서 Param = %s, grad = %s, lr = %s 이면 갱신한 Param은 ____ 입니다."
             % (shown(p), shown(g), shown(lr)),
        blanks=[{"answer": [dec(right)], "mode": "number", "hint": "숫자"}],
        explain="기울기의 반대 방향으로 학습률만큼 옮깁니다. %s − %s × %s = %s 입니다. 빼기 대신 더하기를 쓰면 기울기 쪽으로 가서 틀린 값(%s)이 나옵니다."
                % (shown(p), shown(lr), paren(g), shown(right), shown(wrong)),
        params={"p": dec(p), "lr": dec(lr), "g": dec(g)})


@gen("i01-g02", unit="1c", level=2, tags=["대입과 copy"], ref=["1차시 슬 p12", "1차시 슬 p13"],
     step="1c/3", facts=["F01-13", "F01-14"], basis="lecture-example", family="alias", prio=2)
def alias(r):
    """길이 3~5 정수 배열 a 를 b = a 또는 b = a.copy() 로 받은 뒤 a[i] = v 로 고쳤을 때 b 의 값."""
    n = r.int(3, 5)
    a = [r.int(1, 9) for _ in range(n)]
    copied = r.chance(0.5)
    i = r.int(0, n - 1)
    v = r.int(10, 99)
    after = list(a)
    after[i] = v
    b = list(a) if copied else after
    line = "b = a.copy()" if copied else "b = a"
    stem = ("아래 코드를 차례로 실행한 뒤 `b`의 값은 ____ 입니다.\n\n```python\n"
            "a = np.array(%s)\n%s\na[%d] = %d\n```" % (a, line, i, v))
    if copied:
        why = "b = a.copy() 는 a의 값을 새 배열로 복사하므로 a[%d] = %d 로 a를 고쳐도 b는 처음 값 %s 로 남습니다." % (i, v, a)
    else:
        why = "b = a 는 새 배열을 만들지 않고 같은 배열에 이름을 하나 더 붙이므로 a[%d] = %d 로 고친 값이 b에도 보여 %s 입니다." % (i, v, after)
    return blank(
        stem=stem,
        blanks=[{"answer": [str(b)], "mode": "values", "hint": "배열 값"}],
        explain=why,
        params={"a": a, "copied": copied, "i": i, "v": v})


KINDS = ("square", "mul", "add")


def expr(kind, k):
    if kind == "square":
        return "x ** 2"
    if kind == "mul":
        return "x * %d" % k
    return "x + %d" % k if k > 0 else "x - %d" % -k


def apply(kind, k, x):
    if kind == "square":
        return x * x
    if kind == "mul":
        return x * k
    return x + k


@gen("i01-g03", unit="1d", level=2, tags=["합성 함수"], ref=["1차시 슬 p15"],
     step="1d/2", facts=["F01-20"], basis="lecture-example", family="compose", prio=2)
def compose(r):
    """제곱, k배, +c 세 함수를 섞은 순서로 f1, f2, f3 에 두고 f3(f2(f1(x))) 값. x −3~4, k 2~3, c −3~5(0 제외)."""
    order = list(KINDS)
    r.shuffle(order)
    k = r.int(2, 3)
    c = r.pick([v for v in range(-3, 6) if v != 0])
    x = r.int(-3, 4)
    args = [k if kind == "mul" else c if kind == "add" else 0 for kind in order]
    lines = ["def f%d(x): return %s" % (n + 1, expr(kind, a)) for n, (kind, a) in enumerate(zip(order, args))]
    steps, value = [], x
    for n, (kind, a) in enumerate(zip(order, args)):
        before, value = value, apply(kind, a, value)
        steps.append("f%d(%s) = %s" % (n + 1, num(before).replace("-", MINUS), num(value).replace("-", MINUS)))
    return blank(
        stem="다음 함수로 `f3(f2(f1(%d)))` 를 계산하면 ____ 입니다.\n\n```python\n%s\n```" % (x, "\n".join(lines)),
        blanks=[{"answer": [str(value)], "mode": "number", "hint": "숫자"}],
        explain="합성 함수는 안쪽 함수부터 계산합니다. %s 입니다." % ", ".join(steps),
        params={"order": order, "k": k, "c": c, "x": x})


FORMS = ("range", "tail", "head", "rev", "step2", "inner")


@gen("i01-g04", unit="1g", level=2, tags=["슬라이스"], ref=["1차시 노트북 03 [17]"],
     step="1g/4", facts=["F01-39", "F01-40", "F01-81"], basis="lecture-example", family="slice", prio=1)
def slicing(r):
    """길이 5~8 리스트(첫 값 1~9, 간격 3·4·6·7)에 l[a:b], l[-k:], l[:k], l[::-1], l[::2], l[1:-1] 가운데 하나를 쓴 결과."""
    n = r.int(5, 8)
    first = r.int(1, 9)
    gap = r.pick([3, 4, 6, 7])
    data = [first + gap * j for j in range(n)]
    form = r.pick(list(FORMS))
    if form == "range":
        a = r.int(0, n - 2)
        b = r.int(a + 1, n - 1)
        code, out = "l[%d:%d]" % (a, b), data[a:b]
        why = "시작 인덱스 %d 의 원소는 넣고 끝 인덱스 %d 의 원소는 빼서 %s 입니다." % (a, b, data[a:b])
    elif form == "tail":
        k = r.int(2, n - 1)
        code, out = "l[-%d:]" % k, data[-k:]
        why = "-%d 는 뒤에서 %d번째 자리이고 끝까지 잘라 마지막 %d개 %s 입니다." % (k, k, k, data[-k:])
    elif form == "head":
        k = r.int(2, n - 1)
        code, out = "l[:%d]" % k, data[:k]
        why = "처음부터 인덱스 %d 앞까지라서 앞의 %d개 %s 입니다." % (k, k, data[:k])
    elif form == "rev":
        code, out = "l[::-1]", data[::-1]
        why = "[::-1] 은 정렬하지 않고 순서만 뒤집은 새 리스트 %s 입니다." % data[::-1]
    elif form == "step2":
        code, out = "l[::2]", data[::2]
        why = "처음부터 끝까지 두 칸씩 건너뛰며 인덱스 0, 2, 4 … 의 원소 %s 입니다." % data[::2]
    else:
        code, out = "l[1:-1]", data[1:-1]
        why = "인덱스 1 부터 맨 뒤 원소(-1) 앞까지라서 첫 원소와 마지막 원소를 뺀 %s 입니다." % data[1:-1]
    return blank(
        stem="`l = %s` 일 때 `%s` 의 결과는 ____ 입니다." % (data, code),
        blanks=[{"answer": [str(out)], "mode": "values", "hint": "리스트 값"}],
        explain=why,
        params={"data": data, "form": form, "code": code})
