# -*- coding: utf-8 -*-
"""8차시 생성기. 확률을 판정 줄로 잘라 구한 정확도, 결정 경계 위의 점, pos_weight 와 모두 음성 예측의 정확도,
scikit-learn 혼동 행렬로 구한 지표.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Fraction 으로 계산해 글로 바꾸고, 답이 정한 자리 안에서 끝나지 않는 조합은
Retry 로 다시 뽑음. 숫자 뒤 조사는 받침과 상관없는 꼴(입니다)만 씀.
"""
from decimal import Decimal
from fractions import Fraction

from aiprep.gen import Retry, blank, fixed, gen, num

MINUS = "−"


def dec(value, places=4):
    """Fraction 이 소수 places 자리 안에서 끝나면 그 글, 아니면 Retry. 1.20 은 1.2, 2.0 은 2."""
    scaled = value * 10 ** places
    if scaled.denominator != 1:
        raise Retry("유한소수가 아님")
    out = format((Decimal(scaled.numerator) / (Decimal(10) ** places)).normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return "0" if out in ("-0", "") else out


def shown(text):
    return str(text).replace("-", MINUS)


def paren(value):
    """식 가운데 음수는 괄호로 감쌈. −4 는 (−4), 4 는 4."""
    return "(%s)" % shown(value) if value < 0 else shown(value)


def listing(values):
    return "[" + ", ".join(shown(v) for v in values) + "]"


RULES = {
    "where": ("pred = torch.where(p < 0.5, 0, 1)", "`torch.where(p < 0.5, 0, 1)`은 0.5 미만만 0으로 바꿔 0.5는 1이 됩니다."),
    "gt": ("pred = (p > 0.5).float()", "`>`는 0.5를 0.5보다 크다고 보지 않아 0.5는 0이 됩니다."),
    "ge": ("pred = (p >= 0.5).float()", "`>=`는 0.5를 포함해 0.5는 1이 됩니다."),
}


@gen("i08-g01", unit="8b", level=2, tags=["정확도", "판정 줄"], ref=["8차시 과제 5번", "8차시 노트북 01 [45]"],
     step="8b/4", facts=["F08-21", "F08-60", "F08-61"], basis="lecture-example", family="prob-accuracy", prio=3)
def prob_accuracy(r):
    """확률 n 개(n = 4, 5, 8)를 판정 줄 셋(torch.where(p < 0.5, 0, 1), p > 0.5, p >= 0.5) 가운데 하나로 잘라 정답과
    견준 정확도. 확률은 0.1~0.9 의 0.1 간격이고 절반의 시드에서 0.5 를 하나 넣음. 정답은 0 과 1."""
    n = r.pick([4, 5, 8])
    probs = [r.pick([1, 2, 3, 4, 6, 7, 8, 9]) for _ in range(n)]
    if r.chance(0.5):
        probs[r.int(0, n - 1)] = 5
    ys = [r.int(0, 1) for _ in range(n)]
    rule = r.pick(["where", "gt", "ge"])
    if rule == "gt":
        preds = [1 if k > 5 else 0 for k in probs]
    else:
        preds = [1 if k >= 5 else 0 for k in probs]
    right = sum(1 for a, b in zip(preds, ys) if a == b)
    acc = Fraction(right, n)
    text = dec(acc)
    ps = [dec(Fraction(k, 10)) for k in probs]
    code, note = RULES[rule]
    return blank(
        stem="확률 p가 %s이고 정답이 %s입니다. `%s`로 예측하면 정확도는 ____ 입니다." % (listing(ps), listing(ys), code),
        blanks=[{"answer": [text, "%d/%d" % (right, n)], "mode": "number", "hint": "숫자"}],
        explain="%s 예측은 %s이고 정답과 같은 자리가 %d개라 %d ÷ %d = %s입니다." % (note, listing(preds), right, right, n, text),
        params={"p": ps, "y": ys, "rule": rule})


@gen("i08-g02", unit="8f", level=2, tags=["혼동 행렬", "분류 지표"], ref=["8차시 노트북 02 [44]", "8차시 노트북 02 [41]"],
     step="8f/3", facts=["F08-39", "F08-40", "F08-41", "F08-42"], basis="lecture-example", family="cm-sklearn-metric", prio=3)
def sklearn_metric(r):
    """scikit-learn 배치 [[TN, FP], [FN, TP]] 의 이진 혼동 행렬(TN 50~900, FP·FN 1~60, TP 10~200)로 정확도·정밀도·
    재현율·F1 점수 가운데 하나를 소수 셋째 자리로. 반올림 경계는 fixed 가 피함."""
    tn, fp, fn, tp = r.int(50, 900), r.int(1, 60), r.int(1, 60), r.int(10, 200)
    key = r.pick(["acc", "prec", "rec", "f1"])
    total = tn + fp + fn + tp
    value = {"acc": Fraction(tp + tn, total), "prec": Fraction(tp, tp + fp), "rec": Fraction(tp, tp + fn),
             "f1": Fraction(2 * tp, 2 * tp + fp + fn)}[key]
    answer = fixed(Decimal(value.numerator) / Decimal(value.denominator), 3)
    name = {"acc": "정확도를", "prec": "정밀도를", "rec": "재현율을", "f1": "F1 점수를"}[key]
    how = {"acc": "정확도는 (TP + TN) ÷ 전체 = (%s + %s) ÷ %s입니다." % (num(tp), num(tn), num(total)),
           "prec": "정밀도는 TP ÷ (TP + FP) = %s ÷ %s입니다. 분모에 FN을 넣으면 재현율이 됩니다." % (num(tp), num(tp + fp)),
           "rec": "재현율은 TP ÷ (TP + FN) = %s ÷ %s입니다. 분모에 FP를 넣으면 정밀도가 됩니다." % (num(tp), num(tp + fn)),
           "f1": "F1 점수는 2 × TP ÷ (2 × TP + FP + FN) = %s ÷ %s입니다. 정밀도와 재현율을 먼저 반올림하면 셋째 자리가 달라질 수 있습니다."
                 % (num(2 * tp), num(2 * tp + fp + fn))}[key]
    return blank(
        stem="scikit-learn의 `confusion_matrix(y_true, y_pred)`가 이진 분류에서 `[[%d, %d], [%d, %d]]`를 냈습니다. %s 끝까지 계산한 뒤 소수 셋째 자리로 반올림하면 ____ 입니다."
             % (tn, fp, fn, tp, name),
        blanks=[{"answer": [answer], "mode": "number", "places": 3, "hint": "소수 셋째 자리"}],
        explain="scikit-learn은 [[TN, FP], [FN, TP]] 순서라 TN %s, FP %s, FN %s, TP %s입니다. %s 반올림하면 %s입니다."
                % (num(tn), num(fp), num(fn), num(tp), how, answer),
        params={"cm": [[tn, fp], [fn, tp]], "metric": key})


@gen("i08-g03", unit="8e", level=2, tags=["pos_weight", "클래스 불균형"], ref=["8차시 노트북 02 [30]", "8차시 노트북 02 [7]"],
     step="8e/4", facts=["F08-35", "F08-23"], basis="lecture-example", family="imbalance-count", prio=2)
def imbalance_count(r):
    """정상 거래 neg 건(1,000~9,800, 100 간격)과 사기 거래 pos 건(40·50·80·100·125·200·250·400·500)으로 pos_weight =
    neg ÷ pos(소수 둘째 자리 안에서 끝나는 조합만)나 모두 정상이라고 답한 정확도 neg ÷ (neg + pos)(소수 셋째 자리,
    반올림 경계는 fixed 가 피함). 틀이 둘이고 시드로 고름."""
    pos = r.pick([40, 50, 80, 100, 125, 200, 250, 400, 500])
    neg = r.int(10, 98) * 100
    if neg <= pos * 4:
        raise Retry("불균형이 작음")
    if r.chance(0.5):
        weight = dec(Fraction(neg, pos), 2)
        return blank(
            stem="별도의 훈련 데이터에 정상 거래 %s건, 사기 거래 %s건이 있습니다. 이 훈련 정답의 음성 수 ÷ 양성 수로 정한 `pos_weight`는 ____ 입니다."
                 % (num(neg), num(pos)),
            blanks=[{"answer": [weight], "mode": "number", "hint": "숫자"}],
            explain="사기 거래가 양성이므로 훈련 음성 수 ÷ 훈련 양성 수 = %s ÷ %s = %s입니다. 가중한 양성 건수 %s × %s = %s는 음성 건수와 같습니다. 실제 손실 합은 각 예측값에도 달려 있습니다."
                    % (num(neg), num(pos), weight, num(pos), weight, num(neg)),
            params={"neg": neg, "pos": pos, "ask": "weight"})
    value = Fraction(neg, neg + pos)
    answer = fixed(Decimal(value.numerator) / Decimal(value.denominator), 3)
    return blank(
        stem="테스트 데이터에 정상 거래 %s건, 사기 거래 %s건이 있습니다. 모든 거래를 정상이라고 답하는 모델의 정확도를 소수 셋째 자리로 반올림하면 ____ 입니다."
             % (num(neg), num(pos)),
        blanks=[{"answer": [answer], "mode": "number", "places": 3, "hint": "소수 셋째 자리"}],
        explain="정상 거래만 맞히므로 %s ÷ %s ≈ %s입니다. 이 모델은 사기 거래를 하나도 찾지 못해 재현율이 0입니다."
                % (num(neg), num(neg + pos), answer),
        params={"neg": neg, "pos": pos, "ask": "all-negative"})


@gen("i08-g04", unit="8c", level=2, tags=["결정 경계"], ref=["8차시 노트북 01 [55]", "8차시 슬 p14"],
     step="8c/3", facts=["F08-26", "F08-25"], basis="lecture-formula", family="boundary", prio=3)
def boundary_point(r):
    """w1·x1 + w2·x2 + b = 0 인 결정 경계에서 x1 이 주어질 때 x2 = −(b + w1·x1) ÷ w2. w1, w2 는 0 이 아닌 −5~5 정수,
    b 는 −6~6 정수, x1 은 1~6 정수. 답이 소수 둘째 자리 안에서 끝나는 조합만 씀."""
    w1 = r.pick([k for k in range(-5, 6) if k])
    w2 = r.pick([k for k in range(-5, 6) if k])
    b = r.int(-6, 6)
    x1 = r.int(1, 6)
    x2 = Fraction(-(b + w1 * x1), w2)
    answer = dec(x2, 2)
    return blank(
        stem="w1 = %s, w2 = %s, b = %s인 이진 로지스틱 회귀 모델의 결정 경계에서 x1 = %d이면 x2는 ____ 입니다."
             % (shown(w1), shown(w2), shown(b), x1),
        blanks=[{"answer": [answer], "mode": "number", "hint": "숫자"}],
        explain="결정 경계는 w1 × x1 + w2 × x2 + b = 0이라 x2 = −(b + w1 × x1) ÷ w2입니다. −(%s + %s × %d) ÷ %s = %s ÷ %s = %s입니다."
                % (shown(b), paren(w1), x1, paren(w2), shown(-(b + w1 * x1)), paren(w2), shown(answer)),
        params={"w1": w1, "w2": w2, "b": b, "x1": x1})
