# -*- coding: utf-8 -*-
"""4차시 생성기. 평균 제곱 오차, 경사하강법으로 한 번 갱신(새 W 와 거꾸로 W.grad), 연쇄법칙으로 한 데이터가 W.grad 에 보태는 값,
퍼셉트론의 z 와 출력, 활성화 함수의 값과 미분값, 모멘텀 두 번 갱신, 데이터 나누기와 K-Fold 개수, 혼동 행렬 지표.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Decimal 로 계산해 글로 바꿈. 모든 답이 유한소수가 되게 숫자 범위를 고름.
"""
from decimal import Decimal

from aiprep.gen import gen, blank, fixed, num

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
    """경사하강법으로 한 번 갱신: 새 W = W − 학습률 × W.grad. 틀이 둘이고 시드로 고름: 새 W 를 묻거나(정방향), 갱신 전후의 W 로
    W.grad 를 묻거나(거꾸로). W 는 −2~3(0.5 간격), 기울기는 −8~8(0.5 간격, 0 제외), 학습률 0.1·0.01."""
    w = Decimal(r.int(-4, 6)) / 2
    g = Decimal(r.pick([k for k in range(-16, 17) if k != 0])) / 2
    lr = Decimal(r.pick(["0.1", "0.01"]))
    new = w - lr * g
    if r.chance(0.5):
        return blank(
            stem="W = %s, `W.grad` = %s, 학습률 %s로 경사하강법을 써서 한 번 갱신하면 새 W는 ____ 입니다." % (shown(w), shown(g), shown(lr)),
            blanks=[{"answer": [dec(new)], "mode": "number", "hint": "숫자"}],
            explain="기울기의 반대쪽으로 바꾸므로 학습률 × 기울기를 뺍니다. %s − %s × %s = %s입니다. "
                    "빼기 대신 더하면 기울기 쪽으로 바꾼 값(%s)이 나옵니다."
                    % (shown(w), shown(lr), paren(g), shown(new), shown(w + lr * g)),
            params={"ask": "new", "W": dec(w), "gW": dec(g), "lr": dec(lr)})
    return blank(
        stem="경사하강법으로 한 번 갱신하기 전 W = %s, 갱신한 뒤 W = %s, 학습률 = %s일 때 `W.grad`는 ____ 입니다."
             % (shown(w), shown(new), shown(lr)),
        blanks=[{"answer": [dec(g)], "mode": "number", "hint": "숫자"}],
        explain="새 W = W − 학습률 × `W.grad`이므로 `W.grad` = (W − 새 W) ÷ 학습률입니다. (%s − %s) ÷ %s = %s입니다. "
                "%s"
                % (shown(w), paren(new), shown(lr), shown(g),
                   "W가 줄었으니 기울기는 양수입니다." if new < w else "W가 커졌으니 기울기는 음수입니다."),
        params={"ask": "grad", "W": dec(w), "new": dec(new), "lr": dec(lr)})


@gen("i04-g03", unit="4c", level=3, tags=["연쇄법칙"], ref=["4차시 슬 p21~p22"],
     step="4c/2", facts=["F04-15", "F04-65"], basis="lecture-formula", family="chain-contrib", prio=2)
def chain_part(r):
    """데이터 n 개(n = 2, 4, 5)의 MSE 에서 한 데이터가 W.grad 에 보태는 값 (1/n) × 2e × 1 × X.
    오차 e 는 −3~3(0.5 간격, 0 제외), X 는 −3~3 정수(0·1 제외, 1 이면 X 를 빠뜨린 값이 정답과 같아짐). 단계마다의 미분값을 표로 주고 곱만 시킴."""
    n = r.pick([2, 4, 5])
    e = Decimal(r.pick([k for k in range(-6, 7) if k != 0])) / 2
    x = Decimal(r.pick([-3, -2, -1, 2, 3]))
    inv = Decimal(1) / n
    part = inv * 2 * e * x
    terms = " + ".join("s%s" % sub for sub in ("₁", "₂", "₃", "₄", "₅")[:n]) if n < 5 else "s₁ + … + s₅"
    table = ("| 단계 | 그 단계의 미분값 |\n|---|---|\n"
             "| L = (%s) ÷ %d | L을 s로 미분하면 %s |\n"
             "| s = e², e = %s | s를 e로 미분하면 2e |\n"
             "| e = Yp − Y | e를 Yp로 미분하면 1 |\n"
             "| Yp = W × X + B, X = %s | Yp를 W로 미분하면 X |" % (terms, n, shown(inv), shown(e), shown(x)))
    return blank(
        stem="데이터 %d개의 MSE를 손실로 쓰는 선형 모델이 있습니다. 그중 한 데이터에 대해 단계마다의 미분값을 구했습니다.\n\n%s\n\n"
             "이 데이터가 `W.grad`에 보태는 값은 ____ 입니다." % (n, table),
        blanks=[{"answer": [dec(part)], "mode": "number", "hint": "숫자"}],
        explain="연쇄법칙으로 단계마다의 미분값을 곱합니다. %s × (2 × %s) × 1 × %s = %s입니다. X를 빠뜨린 값(%s)은 정답이 아닙니다."
                % (shown(inv), paren(e), paren(x), shown(part), shown(inv * 2 * e)),
        params={"n": n, "e": dec(e), "X": dec(x)})


@gen("i04-g04", unit="4d", level=2, tags=["퍼셉트론"], ref=["요약 1주차 p15", "대학원 02 p31"],
     step="4d/4", facts=["F04-82"], basis="lecture-formula", family="perceptron", prio=3)
def perceptron(r):
    """계단 함수 퍼셉트론의 z = w1 × x1 + w2 × x2 + b 와 출력(z 가 0 보다 크면 1). w1, w2 는 −2·−1·1·2, b 는 −2.5·−1.5·−0.5·
    0.5·1.5 가운데 하나라 z 가 늘 정수 더하기 0.5 꼴이 되어 0 이 되지 않음. 입력은 네 점 가운데 하나."""
    w1, w2 = r.pick([-2, -1, 1, 2]), r.pick([-2, -1, 1, 2])
    b = Decimal(r.pick([-5, -3, -1, 1, 3])) / 2
    x1, x2 = r.pick([(0, 0), (0, 1), (1, 0), (1, 1)])
    z = w1 * x1 + w2 * x2 + b
    out = 1 if z > 0 else 0
    no_b = w1 * x1 + w2 * x2
    return blank(
        stem="퍼셉트론의 가중치가 w1 = %s, w2 = %s이고 편향이 b = %s입니다. z = w1 × x1 + w2 × x2 + b가 0보다 크면 1, 0 이하이면 "
             "0을 냅니다. (x1, x2) = (%d, %d)일 때 z는 ____ 이고, 출력은 ____ 입니다." % (shown(w1), shown(w2), shown(b), x1, x2),
        blanks=[{"answer": [dec(z)], "mode": "number", "hint": "z 의 값"}, {"answer": [str(out)], "mode": "number", "hint": "0 또는 1"}],
        explain="가중치를 곱해 더하고 편향을 더합니다. %s × %d + %s × %d + %s = %s이고, %s. 편향을 빠뜨리면 z는 %s입니다."
                % (shown(w1), x1, paren(w2), x2, paren(b), shown(z), "0보다 커서 1을 냅니다" if out else "0보다 크지 않아 0을 냅니다",
                   shown(no_b)),
        params={"w1": w1, "w2": w2, "b": dec(b), "x1": x1, "x2": x2})


ACT_NAMES = {"relu": "ReLU", "leaky": "Leaky ReLU", "sig": "시그모이드", "tanh": "tanh"}


@gen("i04-g05", unit="4e", level=2, tags=["활성화 함수", "미분값"], ref=["4차시 슬 p26", "요약 1주차 p17", "요약 1주차 p18"],
     step="4e/3", facts=["F04-23", "F04-84", "F04-86", "F04-101"], basis="lecture-formula", family="act-value", prio=3)
def activation(r):
    """활성화 함수의 값이나 미분값. ReLU·Leaky ReLU 는 x 가 −5~5(0 제외) 정수, Leaky ReLU 의 a 는 0.1·0.01·0.2.
    시그모이드와 tanh 는 끝이 깔끔한 x = 0 의 값과 미분값만 냄(σ(0) = 0.5, σ'(0) = 0.25, tanh(0) = 0, tanh'(0) = 1)."""
    kind = r.pick(["relu", "relu", "leaky", "leaky", "leaky", "zero"])
    grad = r.chance(0.5)
    if kind == "zero":
        name = r.pick(["sig", "tanh"])
        value = {("sig", False): "0.5", ("sig", True): "0.25", ("tanh", False): "0", ("tanh", True): "1"}[(name, grad)]
        how = {("sig", False): "1 / (1 + e⁰) = 1 / 2 = 0.5입니다. 시그모이드는 늘 0과 1 사이를 냅니다.",
               ("sig", True): "시그모이드의 미분값은 σ(x)(1 − σ(x))라 0.5 × 0.5 = 0.25이고, 이 값이 미분값의 최댓값입니다.",
               ("tanh", False): "tanh는 x와 −x에 크기가 같고 부호가 반대인 값을 내서, x = 0에서 0입니다. 같은 자리의 시그모이드는 0.5입니다.",
               ("tanh", True): "tanh의 미분값은 1 − tanh(x)²이고 tanh(0) = 0이라 1입니다. 시그모이드의 미분값은 같은 자리에서 0.25입니다."}[
            (name, grad)]
        stem = ("%s를 x로 미분한 값은 x = 0일 때 ____ 입니다." if grad else "%s에 x = 0을 넣은 값은 ____ 입니다.") % ACT_NAMES[name]
        return blank(stem=stem, blanks=[{"answer": [value], "mode": "number", "hint": "숫자"}], explain=how,
                     params={"f": ("d" if grad else "") + name, "x": "0"})
    x = r.pick([k for k in range(-5, 6) if k != 0])
    a = Decimal(r.pick(["0.1", "0.01", "0.2"])) if kind == "leaky" else Decimal(0)
    if grad:
        value = Decimal(1) if x > 0 else a
        how = ("입력이 양수라 미분값은 1입니다." if x > 0 else
               ("입력이 음수라 미분값은 0입니다. 이 노드로는 기울기가 전해지지 않습니다." if kind == "relu" else
                "입력이 음수라 미분값은 a = %s이고, 같은 입력에서 ReLU의 미분값은 0입니다." % shown(a)))
    else:
        value = Decimal(x) if x > 0 else a * x
        how = ("입력이 양수라 출력은 입력과 같은 %s입니다." % shown(value) if x > 0 else
               ("입력이 음수라 0을 냅니다." if kind == "relu" else
                "입력이 음수라 출력은 a × x = %s × %s = %s이고, 같은 입력에 ReLU는 0을 냅니다." % (shown(a), paren(x), shown(value))))
    head = "ReLU" if kind == "relu" else "a = %s인 Leaky ReLU" % shown(a)
    stem = ("%s를 x로 미분한 값은 x = %s일 때 ____ 입니다." if grad else "%s에 넣는 값이 x = %s일 때 출력은 ____ 입니다.") % (head, shown(x))
    return blank(stem=stem, blanks=[{"answer": [dec(value)], "mode": "number", "hint": "숫자"}], explain=how,
                 params={"f": ("d" if grad else "") + kind, "x": str(x), "a": dec(a)})


@gen("i04-g06", unit="4f", level=2, tags=["모멘텀"], ref=["4차시 슬 p43", "대학원 02 p22", "문서 SGD"],
     step="4f/3", facts=["F04-88"], basis="lecture-formula", family="momentum", prio=2)
def momentum(r):
    """PyTorch SGD 꼴 모멘텀 두 번 갱신. 첫 갱신 v = g1, 둘째 v = μ × g1 + g2, W 는 매번 W − 학습률 × v. μ 는 0.9·0.5, 학습률은
    0.1·0.01, 처음 W 는 −2~2 정수, 기울기는 −6~6 정수(0 제외). 둘째 v 나 둘째 갱신 뒤 W 를 물음."""
    mu = Decimal(r.pick(["0.9", "0.5"]))
    lr = Decimal(r.pick(["0.1", "0.01"]))
    w0 = Decimal(r.int(-2, 2))
    g1 = Decimal(r.pick([k for k in range(-6, 7) if k != 0]))
    g2 = Decimal(r.pick([k for k in range(-6, 7) if k != 0]))
    w1 = w0 - lr * g1
    v2 = mu * g1 + g2
    w2 = w1 - lr * v2
    head = ("PyTorch의 SGD처럼 v = μ × v + 기울기, 새 W = W − 학습률 × v로 W를 갱신하고, 첫 갱신에서는 v가 기울기와 같습니다. "
            "μ = %s, 학습률 %s, 처음 W = %s이고, 첫 기울기는 %s, 둘째 기울기는 %s입니다. "
            % (shown(mu), shown(lr), shown(w0), shown(g1), shown(g2)))
    first = "첫 갱신의 v는 첫 기울기와 같은 %s입니다. W = %s − %s × %s = %s입니다." % (shown(g1), shown(w0), shown(lr), paren(g1), shown(w1))
    second = "둘째 갱신의 v = %s × %s + %s = %s입니다." % (shown(mu), paren(g1), paren(g2), shown(v2))
    if r.chance(0.5):
        return blank(stem=head + "둘째 갱신에서 쓰는 v는 ____ 입니다.",
                     blanks=[{"answer": [dec(v2)], "mode": "number", "hint": "숫자"}],
                     explain="%s %s 지난 v를 남기지 않으면 v는 둘째 기울기와 같은 %s입니다." % (first, second, shown(g2)),
                     params={"ask": "v2", "mu": dec(mu), "lr": dec(lr), "W": dec(w0), "g1": dec(g1), "g2": dec(g2)})
    plain = w1 - lr * g2
    return blank(stem=head + "둘째 갱신 뒤 W는 ____ 입니다.",
                 blanks=[{"answer": [dec(w2)], "mode": "number", "hint": "숫자"}],
                 explain="%s %s 그래서 W = %s − %s × %s = %s입니다. 모멘텀 없이 갱신하면 %s입니다."
                         % (first, second, shown(w1), shown(lr), paren(v2), shown(w2), shown(plain)),
                 params={"ask": "w2", "mu": dec(mu), "lr": dec(lr), "W": dec(w0), "g1": dec(g1), "g2": dec(g2)})


@gen("i04-g07", unit="4g", level=2, tags=["데이터 분할", "K-Fold"], ref=["4차시 슬 p50", "4차시 슬 p51"],
     step="4g/5", facts=["F04-50", "F04-51"], basis="lecture-formula", family="split-count", prio=2)
def split_count(r):
    """강의가 권한 비율(10만 개 이상 80/10/10, 1만 개 이하 60/20/20)로 나눈 개수나, 학습 데이터 M 개로 K-Fold 를 할 때 검증
    덩어리 크기·한 번에 학습에 쓰는 수·학습 횟수. 모든 수가 나누어떨어지게 고름."""
    if r.chance(0.4):
        if r.chance(0.5):
            n = r.int(2, 10) * 50000
            parts = {"학습": 8, "검증": 1, "테스트": 1}
            rule = "10만 개 이상이라 80/10/10 비율"
        else:
            n = r.int(4, 20) * 500
            parts = {"학습": 6, "검증": 2, "테스트": 2}
            rule = "1만 개 이하라 60/20/20 비율"
        which = r.pick(["학습", "검증", "테스트"])
        count = n * parts[which] // 10
        return blank(stem="데이터 %s개를 학습·검증·테스트 순서로 %s 비율로 나눕니다. %s 데이터는 ____ 개입니다."
                          % (num(n), "80%·10%·10%" if parts["학습"] == 8 else "60%·20%·20%", which),
                     blanks=[{"answer": [str(count)], "mode": "number", "unit": "개", "hint": "개수"}],
                     explain="%s로 나눕니다. %s × %d%% = %s개입니다. 이 비율은 자주 쓰는 값이고 정해진 규칙은 아닙니다."
                             % (rule, num(n), parts[which] * 10, num(count)),
                     params={"ask": "split", "n": n, "part": which})
    k = r.pick([3, 4, 5, 8, 10])
    m = k * r.int(4, 30) * 10
    fold = m // k
    ask = r.pick(["fold", "train", "rounds"])
    want = {"fold": fold, "train": m - fold, "rounds": k}[ask]
    what = {"fold": "한 번 학습할 때 검증에 쓰는 데이터는 ____ 개입니다.",
            "train": "한 번 학습할 때 학습에 쓰는 데이터는 ____ 개입니다.",
            "rounds": "검증 덩어리를 바꿔 가며 학습을 모두 ____ 번 합니다."}[ask]
    return blank(stem="학습 데이터 %s개로 %d-Fold 교차 검증을 합니다. %s" % (num(m), k, what),
                 blanks=[{"answer": [str(want)], "mode": "number", "unit": "번" if ask == "rounds" else "개", "hint": "숫자"}],
                 explain="%s개를 %d개 덩어리로 나누면 한 덩어리는 %s개입니다. 한 덩어리로 검증하고 나머지 %s개로 학습하며, 이 학습을 "
                         "덩어리를 바꿔 %d번 합니다." % (num(m), k, num(fold), num(m - fold), k),
                 params={"ask": ask, "m": m, "k": k})


METRICS = {"acc": ("정확도", "정확도를"), "prec": ("정밀도", "정밀도를"), "rec": ("재현율", "재현율을"), "f1": ("F1 점수", "F1 점수를")}


@gen("i04-g08", unit="4h", level=2, tags=["혼동 행렬", "분류 지표"], ref=["4차시 슬 p57", "4차시 슬 p58", "4차시 슬 p59", "4차시 슬 p60"],
     step="4h/4", facts=["F04-55", "F04-56", "F04-57"], basis="lecture-example", family="metric-calc", prio=3)
def metric(r):
    """혼동 행렬 TP·TN(5~60), FP·FN(1~30)으로 정확도·정밀도·재현율·F1 가운데 하나를 소수 둘째 자리로. 반올림 경계는 fixed 가
    피함."""
    tp, fp, fn, tn = r.int(5, 60), r.int(1, 30), r.int(1, 30), r.int(5, 60)
    key = r.pick(["acc", "prec", "rec", "f1"])
    total = tp + fp + fn + tn
    value = {"acc": Decimal(tp + tn) / total, "prec": Decimal(tp) / (tp + fp), "rec": Decimal(tp) / (tp + fn),
             "f1": Decimal(2 * tp) / (2 * tp + fp + fn)}[key]
    answer = fixed(value, 2)
    how = {"acc": "정확도는 (TP + TN) ÷ 전체 = (%d + %d) ÷ %d입니다. 맞힌 칸 둘을 전체로 나눕니다." % (tp, tn, total),
           "prec": "정밀도는 TP ÷ (TP + FP) = %d ÷ %d입니다. 분모에 FN을 넣으면 재현율이 됩니다." % (tp, tp + fp),
           "rec": "재현율은 TP ÷ (TP + FN) = %d ÷ %d입니다. 분모에 FP를 넣으면 정밀도가 됩니다." % (tp, tp + fn),
           "f1": "F1은 정밀도와 재현율의 조화평균이고, 식을 풀어 쓰면 2 × TP ÷ (2 × TP + FP + FN) = %d ÷ %d입니다." % (2 * tp, 2 * tp + fp + fn)}[key]
    return blank(stem="혼동 행렬이 TP %d, FP %d, FN %d, TN %d입니다. %s 소수 둘째 자리로 반올림하면 ____ 입니다."
                      % (tp, fp, fn, tn, METRICS[key][1]),
                 blanks=[{"answer": [answer], "mode": "number", "places": 2, "hint": "소수 둘째 자리"}],
                 explain="%s 소수 둘째 자리로 반올림하면 %s입니다." % (how, answer),
                 params={"metric": key, "TP": tp, "FP": fp, "FN": fn, "TN": tn})

