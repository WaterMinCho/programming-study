# -*- coding: utf-8 -*-
"""4차시 생성기. 평균 제곱 오차, 경사하강법 한 걸음(새 W 와 거꾸로 W.grad), 연쇄법칙으로 한 데이터가 W.grad 에 보태는 값.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Decimal 로 계산해 글로 바꿈. 모든 답이 유한소수가 되게 숫자 범위를 고름.
"""
from decimal import Decimal

from aiprep.gen import gen, blank

MINUS = "−"


def dec(value):
    """Decimal 을 지수 표기 없이 짧은 글로. 1.20 은 1.2, 2.0 은 2."""
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    out = format(value.normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return "0" if out in ("-0", "") else out


def shown(value):
    """화면에 보일 숫자. 빼기는 빼기표로."""
    return dec(value).replace("-", MINUS)


def paren(value):
    """음수면 괄호로 감싼 화면 숫자."""
    out = shown(value)
    return "(%s)" % out if out.startswith(MINUS) else out


def one(value):
    """배열 칸에 넣는 소수 한 자리 글(코드 안이라 빼기는 붙임표)."""
    return "%.1f" % float(value)


@gen("i04-g01", unit="4a", level=2, tags=["MSE"], ref=["4차시 슬 p32", "4차시 과제 2번"],
     step="4a/4", facts=["F04-28"], basis="lecture-formula", family="mse-calc", prio=2)
def mse_value(r):
    """예측과 정답 n 쌍(n = 2, 4, 5)의 평균 제곱 오차. 정답은 1.0~9.0(0.5 간격), 오차는 −2~2(0.5 간격, 0 제외)."""
    n = r.pick([2, 4, 5])
    errs = [Decimal(r.pick([-4, -3, -2, -1, 1, 2, 3, 4])) / 2 for _ in range(n)]
    ys = [Decimal(r.int(2, 18)) / 2 for _ in range(n)]
    yps = [y + e for y, e in zip(ys, errs)]
    squares = [e * e for e in errs]
    total = sum(squares)
    mse = total / n
    return blank(
        stem="예측 `Yp = [%s]`, 정답 `Y = [%s]`의 평균 제곱 오차(MSE)는 ____ 입니다."
             % (", ".join(one(v) for v in yps), ", ".join(one(v) for v in ys)),
        blanks=[{"answer": [dec(mse)], "mode": "number", "hint": "숫자"}],
        explain="오차를 제곱해 평균 냅니다. 오차는 %s이고 제곱은 %s입니다. 제곱의 합은 %s이고, %d로 나누면 %s입니다. "
                "평균 대신 합을 내면 %s입니다."
                % (", ".join(shown(e) for e in errs), ", ".join(shown(s) for s in squares), shown(total), n, shown(mse),
                   shown(total)),
        params={"Yp": [one(v) for v in yps], "Y": [one(v) for v in ys]})


@gen("i04-g02", unit="4b", level=2, tags=["경사하강법", "갱신식"], ref=["4차시 슬 p34", "5차시 슬 p20", "1차시 슬 p7"],
     step="4b/3", facts=["F04-11"], basis="lecture-formula", family="update", prio=3)
def gd_step(r):
    """경사하강법 한 걸음 새 W = W − 학습률 × W.grad. 틀이 둘이고 시드로 고름: 새 W 를 묻거나(정방향), 고치기 전후의 W 로
    W.grad 를 묻거나(거꾸로). W 는 −2~3(0.5 간격), 경사는 −8~8(0.5 간격, 0 제외), 학습률 0.1·0.01."""
    w = Decimal(r.int(-4, 6)) / 2
    g = Decimal(r.pick([k for k in range(-16, 17) if k != 0])) / 2
    lr = Decimal(r.pick(["0.1", "0.01"]))
    new = w - lr * g
    if r.chance(0.5):
        return blank(
            stem="W = %s, `W.grad` = %s, 학습률 %s로 경사하강법을 한 번 하면 새 W는 ____ 입니다." % (shown(w), shown(g), shown(lr)),
            blanks=[{"answer": [dec(new)], "mode": "number", "hint": "숫자"}],
            explain="경사의 반대쪽으로 가므로 학습률 × 경사를 뺍니다. %s − %s × %s = %s입니다. "
                    "빼기 대신 더하면 경사 쪽으로 간 값(%s)이 나옵니다."
                    % (shown(w), shown(lr), paren(g), shown(new), shown(w + lr * g)),
            params={"ask": "new", "W": dec(w), "gW": dec(g), "lr": dec(lr)})
    return blank(
        stem="경사하강법을 한 번 하기 전 W = %s, 한 뒤 W = %s, 학습률 = %s일 때 `W.grad`는 ____ 입니다."
             % (shown(w), shown(new), shown(lr)),
        blanks=[{"answer": [dec(g)], "mode": "number", "hint": "숫자"}],
        explain="새 W = W − 학습률 × `W.grad`이므로 `W.grad` = (W − 새 W) ÷ 학습률입니다. (%s − %s) ÷ %s = %s입니다. "
                "%s"
                % (shown(w), paren(new), shown(lr), shown(g),
                   "W가 줄었으니 경사는 양수입니다." if new < w else "W가 커졌으니 경사는 음수입니다."),
        params={"ask": "grad", "W": dec(w), "new": dec(new), "lr": dec(lr)})


@gen("i04-g03", unit="4c", level=3, tags=["연쇄법칙"], ref=["4차시 슬 p21~p22"],
     step="4c/2", facts=["F04-15", "F04-65"], basis="lecture-formula", family="chain-contrib", prio=2)
def chain_part(r):
    """데이터 n 개(n = 2, 4, 5)의 MSE 에서 한 데이터가 W.grad 에 보태는 값 (1/n) × 2e × 1 × X.
    오차 e 는 −3~3(0.5 간격, 0 제외), X 는 −3~3 정수(0·1 제외, 1 이면 X 를 빠뜨린 값이 정답과 같아짐). 단계마다의 미분을 표로 주고 곱만 시킴."""
    n = r.pick([2, 4, 5])
    e = Decimal(r.pick([k for k in range(-6, 7) if k != 0])) / 2
    x = Decimal(r.pick([-3, -2, -1, 2, 3]))
    inv = Decimal(1) / n
    part = inv * 2 * e * x
    terms = " + ".join("s%s" % sub for sub in ("₁", "₂", "₃", "₄", "₅")[:n]) if n < 5 else "s₁ + … + s₅"
    table = ("| 단계 | 그 단계의 미분 |\n|---|---|\n"
             "| L = (%s) ÷ %d | L을 s로 미분하면 %s |\n"
             "| s = e², e = %s | s를 e로 미분하면 2e |\n"
             "| e = Yp − Y | e를 Yp로 미분하면 1 |\n"
             "| Yp = W × X + B, X = %s | Yp를 W로 미분하면 X |" % (terms, n, shown(inv), shown(e), shown(x)))
    return blank(
        stem="데이터 %d개의 MSE를 손실로 쓰는 선형 모델이 있습니다. 그중 한 데이터에 대해 단계마다의 미분을 구했습니다.\n\n%s\n\n"
             "이 데이터가 `W.grad`에 보태는 값은 ____ 입니다." % (n, table),
        blanks=[{"answer": [dec(part)], "mode": "number", "hint": "숫자"}],
        explain="연쇄법칙으로 단계마다의 미분을 곱합니다. %s × (2 × %s) × 1 × %s = %s입니다. X를 빠뜨린 값(%s)은 정답이 아닙니다."
                % (shown(inv), paren(e), paren(x), shown(part), shown(inv * 2 * e)),
        params={"n": n, "e": dec(e), "X": dec(x)})
