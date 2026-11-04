# -*- coding: utf-8 -*-
"""6차시 생성기. MSE·MAE, Huber 손실, 라벨 스무딩 목표값, 클래스 가중치.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Decimal·Fraction 으로 계산해 글로 바꿈. 모든 답이 유한소수가 되게 숫자 범위를 고르고,
그렇지 않은 조합은 Retry 로 다시 뽑음. 숫자 뒤 조사는 받침과 상관없는 꼴(입니다, 의, 인)만 씀.
"""
from decimal import Decimal
from fractions import Fraction

from aiprep.gen import Retry, blank, gen

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


def frac_dec(value, places=4):
    """Fraction 이 소수 places 자리 안에서 끝나면 Decimal, 아니면 Retry."""
    scaled = value * 10 ** places
    if scaled.denominator != 1:
        raise Retry("유한소수가 아님")
    return Decimal(scaled.numerator) / (Decimal(10) ** places)


@gen("i06-g01", unit="6a", level=2, tags=["MSE", "MAE"], ref=["6차시 슬 p5~p6", "6차시 노트북 02 [5]"],
     step="6a/4", facts=["F06-03", "F06-05"], basis="lecture-example", family="reg-loss-calc", prio=2)
def reg_loss(r):
    """정답과 예측 n 쌍(n = 2, 4, 5)의 MSE 나 MAE. 틀이 둘이고 시드로 고름. 정답은 6~30 정수, 오차는 −5~5 정수.
    MSE 와 MAE 가 같아지는 조합(모든 오차의 절댓값이 0 이나 1)은 다시 뽑음."""
    n = r.pick([2, 4, 5])
    ys = [r.int(6, 30) for _ in range(n)]
    errs = [r.int(-5, 5) for _ in range(n)]
    if all(abs(e) <= 1 for e in errs):
        raise Retry("MSE 와 MAE 가 같음")
    yps = [y + e for y, e in zip(ys, errs)]
    squares = [e * e for e in errs]
    absolutes = [abs(e) for e in errs]
    mse = Decimal(sum(squares)) / n
    mae = Decimal(sum(absolutes)) / n
    pairs = "정답 `[%s]`, 예측 `[%s]`" % (", ".join(str(y) for y in ys), ", ".join(str(p) for p in yps))
    if r.chance(0.5):
        return blank(
            stem="%s의 평균 제곱 오차(MSE)는 ____ 입니다." % pairs,
            blanks=[{"answer": [dec(mse)], "mode": "number", "hint": "숫자"}],
            explain="오차를 제곱해 평균 냅니다. 오차 e = 예측 − 정답은 [%s]이고 제곱은 [%s]입니다. 제곱의 합은 %s이고, 데이터 수 %d로 "
                    "나누면 %s입니다. 절댓값을 평균 낸 MAE는 %s입니다."
                    % (", ".join(shown(e) for e in errs), ", ".join(str(s) for s in squares), sum(squares), n, shown(mse),
                       shown(mae)),
            params={"ask": "mse", "yt": ys, "yp": yps})
    return blank(
        stem="%s의 평균 절대 오차(MAE)는 ____ 입니다." % pairs,
        blanks=[{"answer": [dec(mae)], "mode": "number", "hint": "숫자"}],
        explain="오차의 절댓값을 평균 냅니다. 오차 e = 예측 − 정답은 [%s]이고 절댓값은 [%s]입니다. 절댓값의 합은 %s이고, 데이터 수 %d로 "
                "나누면 %s입니다. 제곱을 평균 낸 MSE는 %s입니다."
                % (", ".join(shown(e) for e in errs), ", ".join(str(a) for a in absolutes), sum(absolutes), n, shown(mae),
                   shown(mse)),
        params={"ask": "mae", "yt": ys, "yp": yps})


@gen("i06-g02", unit="6b", level=3, tags=["Huber 손실"], ref=["6차시 과제 4번", "6차시 노트북 02 [4]", "PyTorch 문서 HuberLoss"],
     step="6b/3", facts=["F06-12", "F06-69"], basis="lecture-formula", family="huber-calc", prio=2)
def huber_mean(r):
    """δ(0.5, 1, 2) 인 Huber 손실의 평균. 오차 n 개(n = 2, 4)는 −4~4 의 0.5 간격(0 제외)이고, 제곱 구간(|e| ≤ δ)과 직선 구간
    (|e| > δ)에 하나 이상씩 들어가게 뽑음. |e| ≤ δ 이면 0.5e², 아니면 δ(|e| − 0.5δ)."""
    delta = Decimal(r.pick(["0.5", "1", "2"]))
    n = r.pick([2, 4])
    errs = [Decimal(r.pick([k for k in range(-8, 9) if k != 0])) / 2 for _ in range(n)]
    inside = [abs(e) <= delta for e in errs]
    if all(inside) or not any(inside):
        raise Retry("한 구간에만 듦")
    half = delta / 2
    values, lines, plain = [], [], []
    for e, small in zip(errs, inside):
        if small:
            v = e * e / 2
            lines.append("오차 %s의 절댓값이 δ 이하라서 0.5 × %s² = %s입니다." % (shown(e), shown(abs(e)), shown(v)))
            plain.append(v)
        else:
            v = delta * (abs(e) - half)
            lines.append("오차 %s의 절댓값이 δ보다 커서 %s × (%s − %s) = %s입니다."
                         % (shown(e), shown(delta), shown(abs(e)), shown(half), shown(v)))
            plain.append(delta * abs(e))
        values.append(v)
    total = sum(values)
    mean = total / n
    wrong = sum(plain) / n
    return blank(
        stem="δ = %s인 Huber 손실로 오차 [%s]의 손실을 계산하면 ____ 입니다. 원소마다 계산한 값을 평균 냅니다."
             % (shown(delta), ", ".join(shown(e) for e in errs)),
        blanks=[{"answer": [dec(mean)], "mode": "number", "hint": "숫자"}],
        explain="%s 모두 더하면 %s이고, %d로 나누면 %s입니다. δ보다 큰 오차에서 0.5δ를 빼지 않은 값은 %s입니다."
                % (" ".join(lines), shown(total), n, shown(mean), shown(wrong)),
        params={"delta": dec(delta), "errors": [dec(e) for e in errs]})


@gen("i06-g03", unit="6d", level=2, tags=["라벨 스무딩"], ref=["6차시 슬 p16", "6차시 노트북 01 [0]"],
     step="6d/4", facts=["F06-33"], basis="lecture-formula", family="ls-target", prio=2)
def smoothing_target(r):
    """라벨 스무딩 목표 y × (1 − α) + α ÷ K. K 는 2, 4, 5, 8, 10(α ÷ K 가 유한소수), α 는 0.05, 0.1, 0.2. 틀이 둘이고 시드로 고름:
    정답 클래스의 목표값을 묻거나, 정답이 아닌 클래스 하나의 목표값을 묻거나."""
    k = r.pick([2, 4, 5, 8, 10])
    alpha = Decimal(r.pick(["0.05", "0.1", "0.2"]))
    keep = 1 - alpha
    other = alpha / k
    right = keep + other
    if r.chance(0.5):
        return blank(
            stem="클래스 %d개, α = %s로 라벨 스무딩을 하면 정답 클래스의 목표는 ____ 입니다." % (k, shown(alpha)),
            blanks=[{"answer": [dec(right)], "mode": "number", "hint": "숫자"}],
            explain="목표 = y × (1 − α) + α ÷ K입니다. 정답 칸은 1 × %s + %s ÷ %d = %s, 나머지 칸은 0 × %s + %s ÷ %d = %s입니다. "
                    "α ÷ K를 더하지 않은 값은 %s입니다."
                    % (shown(keep), shown(alpha), k, shown(right), shown(keep), shown(alpha), k, shown(other), shown(keep)),
            params={"ask": "right", "K": k, "alpha": dec(alpha)})
    return blank(
        stem="클래스 %d개, α = %s로 라벨 스무딩을 하면 정답이 아닌 클래스 하나의 목표는 ____ 입니다." % (k, shown(alpha)),
        blanks=[{"answer": [dec(other)], "mode": "number", "hint": "숫자"}],
        explain="목표 = y × (1 − α) + α ÷ K입니다. 정답이 아닌 칸은 y = 0이라 0 × %s + %s ÷ %d = %s이고, 정답 칸은 %s입니다. "
                "α를 K로 나누지 않은 값은 %s입니다."
                % (shown(keep), shown(alpha), k, shown(other), shown(right), shown(alpha)),
        params={"ask": "other", "K": k, "alpha": dec(alpha)})


@gen("i06-g04", unit="6e", level=2, tags=["가중 교차 엔트로피"], ref=["6차시 슬 p17", "6차시 노트북 01 [0]"],
     step="6e/3", facts=["F06-38"], basis="lecture-formula", family="class-weight", prio=3)
def class_weight(r):
    """가중 교차 엔트로피의 클래스 가중치 = 전체 데이터 수 ÷ (클래스 수 × 그 클래스의 데이터 수). 클래스는 2개나 3개이고 데이터 수는
    100~4000 의 목록에서 서로 다르게 뽑음. 묻는 가중치가 소수 넷째 자리 안에서 끝나고 100 이하일 때만 냄."""
    k = r.pick([2, 3])
    pool = [100, 200, 250, 300, 400, 500, 600, 750, 800, 900, 1000, 1200, 1500, 1600, 2000, 2400, 3000, 4000]
    counts = r.sample(pool, k)
    total = sum(counts)
    c = r.int(0, k - 1)
    weight = Fraction(total, k * counts[c])
    if weight > 100:
        raise Retry("가중치가 너무 큼")
    value = frac_dec(weight)
    share = frac_dec(Fraction(total, k))
    return blank(
        stem="클래스 %d개의 데이터 수가 클래스 0부터 [%s]입니다. 가중 교차 엔트로피에서 클래스 %d의 가중치는 ____ 입니다."
             % (k, ", ".join(str(x) for x in counts), c),
        blanks=[{"answer": [dec(value)], "mode": "number", "hint": "숫자"}],
        explain="가중치 = 전체 데이터 수 ÷ (클래스 수 × 그 클래스의 데이터 수)입니다. %s ÷ (%d × %s) = %s입니다. 데이터 수 × 가중치는 "
                "어느 클래스나 전체 ÷ 클래스 수인 %s입니다."
                % (total, k, counts[c], shown(value), shown(share)),
        params={"counts": counts, "cls": c})
