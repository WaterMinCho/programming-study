# -*- coding: utf-8 -*-
"""4차시 생성기의 정답을 생성기 코드를 보지 않고 공개본의 독스트링과 params 만으로 다시 계산함. 표준 라이브러리만 씀.

함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것이고, params 를 받아 칸마다 정답 글의 목록을 돌려줌.
"""
from decimal import Decimal


def _text(value):
    """Decimal 을 지수 표기 없는 글로 바꿈. 정수면 소수점을 붙이지 않음."""
    value = value.normalize()
    if value == value.to_integral_value():
        return str(int(value))
    return format(value, "f")


def i04_g01(params):
    """예측과 정답의 평균 제곱 오차."""
    yp = [Decimal(v) for v in params["Yp"]]
    y = [Decimal(v) for v in params["Y"]]
    return [_text(sum((a - b) ** 2 for a, b in zip(yp, y)) / len(y))]


def i04_g02(params):
    """경사하강법으로 한 번 갱신. ask 가 new 면 새 W, grad 면 (W − 새 W) ÷ 학습률."""
    w, lr = Decimal(params["W"]), Decimal(params["lr"])
    if params["ask"] == "new":
        return [_text(w - lr * Decimal(params["gW"]))]
    return [_text((w - Decimal(params["new"])) / lr)]


def i04_g03(params):
    """한 데이터가 W.grad 에 보태는 값 (1/n) × 2e × 1 × X."""
    n, e, x = Decimal(params["n"]), Decimal(params["e"]), Decimal(params["X"])
    return [_text(2 * e * x / n)]


def i04_g04(params):
    """퍼셉트론의 z 와 출력(z 가 0 보다 크면 1)."""
    z = Decimal(params["w1"]) * params["x1"] + Decimal(params["w2"]) * params["x2"] + Decimal(params["b"])
    return [_text(z), "1" if z > 0 else "0"]


def i04_g05(params):
    """활성화 함수의 값(f) 이나 미분값(df). relu·leaky 는 x 가 0 이 아닌 정수, sig·tanh 는 x = 0."""
    f, x = params["f"], Decimal(params["x"])
    fixed_zero = {"sig": "0.5", "dsig": "0.25", "tanh": "0", "dtanh": "1"}
    if f in fixed_zero:
        return [fixed_zero[f]]
    a = Decimal(params.get("a") or "0")
    if f in ("relu", "leaky"):
        return [_text(x if x > 0 else a * x)]
    return [_text(Decimal(1) if x > 0 else a)]


def i04_g06(params):
    """PyTorch 꼴 모멘텀 두 번 갱신. ask 가 v2 면 둘째 v, w2 면 둘째 갱신 뒤 W."""
    mu, lr, w = Decimal(params["mu"]), Decimal(params["lr"]), Decimal(params["W"])
    g1, g2 = Decimal(params["g1"]), Decimal(params["g2"])
    v = g1
    w = w - lr * v
    v = mu * v + g2
    if params["ask"] == "v2":
        return [_text(v)]
    return [_text(w - lr * v)]


def i04_g07(params):
    """강의 비율로 나눈 개수, 또는 K-Fold 의 덩어리 크기·학습에 쓰는 수·학습 횟수."""
    if params["ask"] == "split":
        n = params["n"]
        share = {"학습": 8, "검증": 1, "테스트": 1} if n >= 100000 else {"학습": 6, "검증": 2, "테스트": 2}
        return [str(n * share[params["part"]] // 10)]
    m, k = params["m"], params["k"]
    return [str({"fold": m // k, "train": m - m // k, "rounds": k}[params["ask"]])]


def i04_g08(params):
    """혼동 행렬 지표를 소수 둘째 자리로 반올림(ROUND_HALF_UP)."""
    from decimal import ROUND_HALF_UP
    tp, fp, fn, tn = (Decimal(params[k]) for k in ("TP", "FP", "FN", "TN"))
    value = {"acc": (tp + tn) / (tp + fp + fn + tn), "prec": tp / (tp + fp), "rec": tp / (tp + fn),
             "f1": 2 * tp / (2 * tp + fp + fn)}[params["metric"]]
    return [str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))]
