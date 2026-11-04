# -*- coding: utf-8 -*-
"""7차시 생성기. nn.Linear 출력값, MSE 기울기와 SGD 한 번 갱신, R².

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Fraction 으로 계산해 글로 바꿈. 답이 소수 넷째 자리 안에서 끝나지 않는 조합은
Retry 로 다시 뽑음. 숫자 뒤 조사는 받침과 상관없는 꼴(입니다, 의)만 씀.
"""
from fractions import Fraction

from aiprep.gen import Retry, blank, gen

MINUS = "−"


def dec(value):
    """Fraction 을 소수 넷째 자리 안에서 끝나는 글로. 끝나지 않으면 Retry."""
    value = Fraction(value)
    scaled = value * 10 ** 4
    if scaled.denominator != 1:
        raise Retry("유한소수가 아님")
    sign = "-" if value < 0 else ""
    whole, frac = divmod(abs(scaled.numerator), 10 ** 4)
    text = "%s%d" % (sign, whole)
    if frac:
        text += "." + ("%04d" % frac).rstrip("0")
    return "0" if text == "-0" else text


def shown(value):
    """화면에 보일 숫자. 빼기는 빼기표로."""
    return dec(value).replace("-", MINUS)


def paren(value):
    """식 안에 넣을 숫자. 음수는 괄호로 감쌈."""
    return "(%s)" % shown(value) if value < 0 else shown(value)


def row(values):
    return "[" + ", ".join(shown(v) for v in values) + "]"


@gen("i07-g01", unit="7a", level=2, tags=["nn.Linear", "y = xWᵀ + b"],
     ref=["7차시 노트북 01 [21]", "7차시 슬 p14", "PyTorch 문서 Linear"], facts=["F07-07", "F07-17"],
     basis="lecture-example", step="7a/3", family="linear-out", prio=3)
def linear_out(r):
    """nn.Linear(n_in, n_out) 에 입력 한 행 x 를 넣은 출력. 출력 j = (weight j번 행 · x) + bias j.
    n_in 은 2·3, n_out 은 2·3, weight 와 x 는 −2~3 정수, bias 는 −3~3 정수. 행이 모두 같거나 x 가 모두 0 이면 다시 뽑음."""
    n_in, n_out = r.pick([2, 3]), r.pick([2, 3])
    weight = [[r.int(-2, 3) for _ in range(n_in)] for _ in range(n_out)]
    bias = [r.int(-3, 3) for _ in range(n_out)]
    x = [r.int(-2, 3) for _ in range(n_in)]
    if all(v == 0 for v in x) or len(set(tuple(w) for w in weight)) < n_out:
        raise Retry("행이 겹치거나 입력이 0")
    out = [sum(w * v for w, v in zip(wr, x)) + b for wr, b in zip(weight, bias)]
    plain = [sum(w * v for w, v in zip(wr, x)) for wr in weight]
    lines = []
    for j, (wr, b) in enumerate(zip(weight, bias)):
        terms = " + ".join("%s × %s" % (paren(w), paren(v)) for w, v in zip(wr, x))
        lines.append("%d번 출력은 %s + %s = %s" % (j, terms, paren(b), shown(out[j])))
    answer = "[[" + ", ".join(dec(v) for v in out) + "]]"
    return blank(
        stem="`nn.Linear(%d, %d)`의 weight가 [%s], bias가 %s입니다. 입력 [%s]의 출력은 ____ 입니다."
             % (n_in, n_out, ", ".join(row(w) for w in weight), row(bias), row(x)),
        blanks=[{"answer": [answer], "mode": "values", "hint": "값"}],
        explain="weight의 행 하나가 출력 하나를 만들고 y = xWᵀ + b입니다. %s입니다. "
                "bias를 더하지 않으면 [[%s]]입니다." % (", ".join(lines), ", ".join(shown(v) for v in plain)),
        params={"weight": weight, "bias": bias, "x": x})


@gen("i07-g02", unit="7e", level=2, tags=["MSE 기울기", "SGD"],
     ref=["7차시 노트북 01 [56]", "7차시 노트북 01 [57]", "7차시 슬 p26"], facts=["F07-53", "F07-54", "F07-103"],
     basis="lecture-example", step="7e/3", family="sgd-step", prio=2)
def sgd_step(r):
    """모델 y = wx + b 를 MSE 로 한 번 갱신. weight 기울기 = (2 ÷ n) × Σ(예측 − 정답) × x, 손실을 2 로 나누면(half) 그 절반.
    새 w = w − lr × 기울기. n 은 2·4·5, x 는 1~4 정수, 정답은 0~9 정수, w·b 는 0·1, lr 은 0.1·0.01. 틀이 둘이고 시드로 고름:
    weight 기울기를 묻거나, 한 번 갱신한 w 를 묻거나. 기울기가 0 이면 다시 뽑음."""
    n = r.pick([2, 4, 5])
    xs = [r.int(1, 4) for _ in range(n)]
    ys = [r.int(0, 9) for _ in range(n)]
    w, b = r.pick([0, 1]), r.pick([0, 1])
    lr = Fraction(r.pick(["0.1", "0.01"]))
    half = r.chance(0.5)
    preds = [w * x + b for x in xs]
    errs = [p - y for p, y in zip(preds, ys)]
    grad = Fraction(2, n) * sum(e * x for e, x in zip(errs, xs))
    if half:
        grad = grad / 2
    if grad == 0:
        raise Retry("기울기 0")
    new_w = w - lr * grad
    loss_text = "MSE를 2로 나눈 값을" if half else "MSE를"
    setup = ("모델 y = wx + b가 w = %d, b = %d입니다. 입력 x = %s, 정답 %s에서 손실로 %s 쓰고 `loss.backward()`를 부릅니다."
             % (w, b, row(xs), row(ys), loss_text))
    calc = ("예측은 %s, 예측 − 정답은 %s입니다. weight 기울기는 (2 ÷ %d) × (%s)%s = %s입니다."
            % (row(preds), row(errs), n, " + ".join("%s × %d" % (paren(e), x) for e, x in zip(errs, xs)),
               " ÷ 2" if half else "", shown(grad)))
    if r.chance(0.5):
        return blank(
            stem=setup + " weight의 기울기 `w.grad`는 ____ 입니다.",
            blanks=[{"answer": [dec(grad)], "mode": "number", "hint": "숫자"}],
            explain=calc + (" 손실을 2로 나누지 않으면 %s입니다." % shown(grad * 2) if half else
                            " 슬라이드처럼 손실을 2로 나누면 %s입니다." % shown(grad / 2)),
            params={"ask": "grad", "x": xs, "y": ys, "w": w, "b": b, "lr": str(lr), "half": half})
    return blank(
        stem=setup + " 이어서 `optim.SGD(..., lr=%s)`로 `optimizer.step()`을 한 번 부르면 w는 ____ 입니다." % shown(lr),
        blanks=[{"answer": [dec(new_w)], "mode": "number", "hint": "숫자"}],
        explain=calc + " 새 w = %d − %s × (%s) = %s입니다. 기울기를 빼지 않고 더하면 %s입니다."
                % (w, shown(lr), shown(grad), shown(new_w), shown(w + lr * grad)),
        params={"ask": "step", "x": xs, "y": ys, "w": w, "b": b, "lr": str(lr), "half": half})


@gen("i07-g03", unit="7f", level=2, tags=["R²"],
     ref=["7차시 슬 p31", "scikit-learn 문서 r2_score"], facts=["F07-35", "F07-36"],
     basis="lecture-formula", step="7f/2", family="r2-calc", prio=2)
def r2_value(r):
    """R² = 1 − SS_res ÷ SS_tot. SS_res = Σ(정답 − 예측)², SS_tot = Σ(정답 − 정답 평균)². 정답은 평균 3~8 정수에 합이 0 인
    차이 묶음(SS_tot 이 4, 8, 10, 16, 20, 40 이 되는 것)을 섞어 더한 4·5개이고, 예측은 정답에 −3~3 정수를 더한 값.
    예측이 정답과 모두 같으면 다시 뽑음."""
    pattern = list(r.pick([[-3, -1, 1, 3], [-2, -1, 1, 2], [-4, -2, 2, 4], [-1, -1, 1, 1], [-2, 0, 0, 2],
                           [-2, -1, 0, 1, 2], [-4, -2, 0, 2, 4], [-3, -1, 0, 1, 3], [-2, -2, 0, 2, 2]]))
    center = r.int(3, 8)
    r.shuffle(pattern)
    ys = [center + d for d in pattern]
    n = len(ys)
    preds = [y + r.int(-3, 3) for y in ys]
    if preds == ys:
        raise Retry("예측이 정답과 같음")
    mean = Fraction(sum(ys), n)
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, preds))
    ss_tot = sum((y - mean) ** 2 for y in ys)
    r2 = 1 - Fraction(ss_res) / ss_tot
    answer = dec(r2)
    return blank(
        stem="정답 %s, 예측 %s에서 R² = 1 − SS_res ÷ SS_tot은 ____ 입니다." % (row(ys), row(preds)),
        blanks=[{"answer": [answer], "mode": "number", "hint": "숫자"}],
        explain="SS_res는 잔차 %s의 제곱합 %s이고, 정답 평균 %s에서 SS_tot은 %s입니다. R² = 1 − %s ÷ %s = %s입니다.%s"
                % (row([y - p for y, p in zip(ys, preds)]), shown(ss_res), shown(mean), shown(ss_tot), shown(ss_res),
                   shown(ss_tot), shown(r2),
                   " 평균만 내는 모델보다 잔차 제곱합이 커서 음수입니다." if r2 < 0 else ""),
        params={"y": ys, "pred": preds})
