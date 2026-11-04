# -*- coding: utf-8 -*-
"""9차시 생성기. Linear 층의 weight 모양과 파라미터 수, 소프트맥스 확률, NLLLoss, 예측 클래스와 정확도, 3 × 3 혼동 행렬의 지표.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Decimal·Fraction 으로 계산해 글로 바꿈. 반올림해서 묻는 값은 fixed 가 경계를 피하고,
g02 는 지문에 준 반올림 값으로 계산한 답과 참값으로 계산한 답이 다르면 Retry 로 다시 뽑음. 숫자와 대괄호 뒤 조사는 받침과 상관없는 꼴(의, 처럼)만 씀.
"""
import math
from decimal import Decimal
from fractions import Fraction

from aiprep.gen import Retry, blank, fixed, gen, num

MINUS = "−"
E_POW = {0: Decimal("1"), 1: Decimal("2.718"), 2: Decimal("7.389"), 3: Decimal("20.086")}
E_TEXT = "e⁰ = 1, e¹ ≈ 2.718, e² ≈ 7.389, e³ ≈ 20.086"


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


def vec(values):
    return "[%s]" % ", ".join(shown(v) for v in values)


def mat(rows):
    return "[%s]" % ", ".join(vec(row) for row in rows)


@gen("i09-g01", unit="9a", level=2, tags=["가중치 행렬", "Linear 파라미터 수"],
     ref=["9차시 노트북 01 [25]", "9차시 노트북 01 [27]", "PyTorch 문서 Linear"],
     step="9a/3", facts=["F09-05", "F09-82"], basis="lecture-example", family="linear-params", prio=2)
def linear_matrix(r):
    """특징 F 개를 받아 클래스 C 개의 logit 을 내는 nn.Linear(F, C). 틀이 둘이고 시드로 고름: weight 모양 [C, F] 나 학습 파라미터 수
    F × C + C. F 는 2~64 의 목록, C 는 3~10 이고 F 와 C 가 같으면 다시 뽑음(모양의 순서를 가릴 수 없음)."""
    f = r.pick([2, 3, 4, 5, 6, 8, 10, 12, 13, 16, 20, 32, 64])
    c = r.int(3, 10)
    if f == c:
        raise Retry("입력 수와 출력 수가 같음")
    layer = "`nn.Linear(%d, %d)`" % (f, c)
    if r.chance(0.5):
        return blank(
            stem="특징 %d개를 받아 클래스 %d개의 logit을 내는 층 %s의 weight 모양은 ____ 입니다." % (f, c, layer),
            blanks=[{"answer": ["[%d, %d]" % (c, f)], "mode": "shape", "hint": "모양"}],
            explain="weight는 [출력 수, 입력 수]라서 행이 클래스 수 %d, 열이 특징 수 %d입니다. 행 하나가 클래스 하나의 logit을 만듭니다. "
                    "[%d, %d]처럼 답했다면 인자 순서대로 모양을 적은 것입니다." % (c, f, f, c),
            params={"form": "shape", "F": f, "C": c})
    total = f * c + c
    return blank(
        stem="특징 %d개를 받아 클래스 %d개의 logit을 내는 층 %s의 학습 파라미터는 ____ 개입니다." % (f, c, layer),
        blanks=[{"answer": [str(total)], "mode": "number", "unit": "개", "hint": "숫자"}],
        explain="weight [%d, %d]에 %s개, bias에 클래스마다 하나씩 %d개가 있어 %d × %d + %d = %s개입니다. bias를 빼면 %s개가 나옵니다."
                % (c, f, num(f * c), c, f, c, c, num(total), num(f * c)),
        params={"form": "params", "F": f, "C": c})


@gen("i09-g02", unit="9b", level=2, tags=["소프트맥스"], ref=["9차시 슬 p7", "9차시 노트북 02 [4]"],
     step="9b/2", facts=["F09-07", "F09-65"], basis="lecture-formula", family="softmax-prob", prio=3)
def softmax_prob(r):
    """logit 셋(0~3 정수, 셋이 모두 같지는 않음)의 소프트맥스에서 클래스 k 의 확률을 소수 셋째 자리로. 지문에 준 e 의 거듭제곱
    값(e⁰ = 1, e¹ ≈ 2.718, e² ≈ 7.389, e³ ≈ 20.086)으로 계산함. 틀이 둘이고 시드로 고름: logit 을 그대로 주거나, 모두 같은 수
    c(4~9)를 더한 logit 을 줌. 더한 logit 의 소프트맥스는 더하기 전과 같음."""
    z = [r.int(0, 3) for _ in range(3)]
    if len(set(z)) == 1:
        raise Retry("logit 이 모두 같음")
    k = r.int(0, 2)
    powers = [E_POW[v] for v in z]
    total = sum(powers)
    answer = fixed(powers[k] / total, 3)
    exact = math.exp(z[k]) / sum(math.exp(v) for v in z)
    if fixed(exact, 3) != answer:
        raise Retry("어림한 e 로 구한 값과 참값의 반올림이 다름")
    shift = r.int(4, 9) if r.chance(0.5) else 0
    logits = [v + shift for v in z]
    lead = ("logit [%s]의 각 값은 [%s]에 %d씩 더한 값이라 소프트맥스가 [%s]의 소프트맥스와 같습니다. "
            % (", ".join(str(v) for v in logits), ", ".join(str(v) for v in z), shift,
               ", ".join(str(v) for v in z))) if shift else ""
    return blank(
        stem="logit [%s]의 소프트맥스에서 클래스 %d의 확률을 소수 셋째 자리까지 쓰면 ____ 입니다. 클래스 번호는 0부터 세고, %s입니다."
             % (", ".join(str(v) for v in logits), k, E_TEXT),
        blanks=[{"answer": [answer], "mode": "number", "places": 3, "hint": "소수 셋째 자리"}],
        explain="%s%se^(logit)은 [%s]이고 합은 %s입니다. 클래스 %d의 확률은 %s ÷ %s ≈ %s입니다."
                % (lead, "[%s]의 " % ", ".join(str(v) for v in z) if shift else "클래스마다 ",
                   ", ".join(dec(p) for p in powers), dec(total), k, dec(powers[k]), dec(total), answer),
        params={"z": z, "k": k, "c": shift})


@gen("i09-g03", unit="9c", level=2, tags=["NLLLoss"], ref=["9차시 노트북 02 [13]", "9차시 슬 p15", "PyTorch 문서 NLLLoss"],
     step="9c/3", facts=["F09-26", "F09-61"], basis="lecture-example", family="nll-pick", prio=3)
def nll_pick(r):
    """데이터 2개나 4개, 클래스 3개의 로그 확률(정수 logit −1~3 의 로그 소프트맥스를 소수 둘째 자리로 반올림한 값)과 정답으로
    nn.NLLLoss 의 값. 틀이 둘이고 시드로 고름: reduction 기본값 'mean'(정답 칸 값의 부호를 바꿔 평균)과 reduction='sum'(합).
    로그 확률은 행마다 logit − log(e^(logit) 의 합). 답은 지문에 준 반올림 값으로 계산한 값을 반올림하지 않고 씀(지문에 밝힘)."""
    n = r.pick([2, 4])
    rows, labels = [], []
    for _ in range(n):
        z = [r.int(-1, 3) for _ in range(3)]
        top = max(z)
        lse = top + math.log(sum(math.exp(v - top) for v in z))
        rows.append([Decimal(str(round(v - lse, 2))) for v in z])
        labels.append(r.int(0, 2))
    picked = [-rows[i][labels[i]] for i in range(n)]
    reduce = "sum" if r.chance(0.5) else "mean"
    total = sum(picked)
    value = total if reduce == "sum" else total / n
    call = "`nn.NLLLoss(reduction='sum')`" if reduce == "sum" else "`nn.NLLLoss()`"
    if any(p == 0 for p in picked):
        raise Retry("정답 칸 값이 0")
    how = ("합" if reduce == "sum" else "평균")
    other = total / n if reduce == "sum" else total
    return blank(
        stem="데이터 %d개의 로그 소프트맥스 값을 소수 둘째 자리로 반올림하면 %s입니다. 정답이 [%s]일 때 이 반올림한 값으로 "
             "계산한 %s의 값은 ____ 입니다. 계산한 값은 반올림하지 않고 씁니다. 클래스 번호는 0부터 셉니다."
             % (n, mat(rows), ", ".join(str(v) for v in labels), call),
        blanks=[{"answer": [dec(value)], "mode": "number", "hint": "숫자"}],
        explain="데이터마다 정답 칸에서 고른 값은 [%s]이고, 부호를 바꾸면 [%s]입니다. %s의 %s은 %s입니다. %s을 구하면 %s입니다."
                % (", ".join(shown(rows[i][labels[i]]) for i in range(n)), ", ".join(shown(p) for p in picked), call, how,
                   shown(value), "평균" if reduce == "sum" else "합", shown(other)),
        params={"logp": [[dec(v) for v in row] for row in rows], "y": labels, "reduction": reduce})


@gen("i09-g04", unit="9f", level=2, tags=["혼동 행렬", "클래스별 지표"], ref=["요약 2주차 p6", "4차시 슬 p57~p60"],
     step="9f/3", facts=["F09-73", "F09-74"], basis="lecture-formula", family="metric-multi", prio=3)
def class_metric(r):
    """행이 실제, 열이 예측인 3 × 3 혼동 행렬(대각선 8~30, 나머지 0~6)에서 정확도나 클래스 k 의 정밀도·재현율·F1 점수를 소수 셋째
    자리로. 정밀도는 k 열, 재현율은 k 행으로 셈. F1 점수는 반올림한 정밀도·재현율로 계산해도 같은 답일 때만 냄."""
    m = [[r.int(8, 30) if i == j else r.int(0, 6) for j in range(3)] for i in range(3)]
    key = r.pick(["acc", "prec", "rec", "f1"])
    k = r.int(0, 2)
    tp = m[k][k]
    col = sum(m[i][k] for i in range(3))
    row = sum(m[k])
    total = sum(sum(line) for line in m)
    diag = sum(m[i][i] for i in range(3))
    if key == "acc":
        value = Fraction(diag, total)
    elif key == "prec":
        value = Fraction(tp, col)
    elif key == "rec":
        value = Fraction(tp, row)
    else:
        value = Fraction(2 * tp, col + row)
    answer = fixed(Decimal(value.numerator) / Decimal(value.denominator), 3)
    if key == "f1":
        p = Decimal(fixed(Decimal(tp) / Decimal(col), 3))
        q = Decimal(fixed(Decimal(tp) / Decimal(row), 3))
        if p + q == 0 or fixed(2 * p * q / (p + q), 3) != answer:
            raise Retry("반올림한 정밀도·재현율로 구한 F1 이 다름")
    name = {"acc": "정확도를", "prec": "클래스 %d의 정밀도를" % k, "rec": "클래스 %d의 재현율을" % k, "f1": "클래스 %d의 F1 점수를" % k}[key]
    how = {"acc": "정확도는 대각선 칸의 합 ÷ 전체 = (%s) ÷ %d입니다." % (" + ".join(str(m[i][i]) for i in range(3)), total),
           "prec": "정밀도는 예측이 클래스 %d인 %d번 열만 봅니다. 대각선 칸 ÷ 열의 합 = %d ÷ (%s)입니다. %d번 행의 합으로 나누면 "
                   "재현율이 됩니다." % (k, k, tp, " + ".join(str(m[i][k]) for i in range(3)), k),
           "rec": "재현율은 실제가 클래스 %d인 %d번 행만 봅니다. 대각선 칸 ÷ 행의 합 = %d ÷ (%s)입니다. %d번 열의 합으로 나누면 "
                  "정밀도가 됩니다." % (k, k, tp, " + ".join(str(v) for v in m[k]), k),
           "f1": "정밀도는 %d번 열에서 %d ÷ %d, 재현율은 %d번 행에서 %d ÷ %d입니다. F1 점수는 둘의 조화평균이고 2 × %d ÷ (%d + %d)의 "
                 "값과 같습니다." % (k, tp, col, k, tp, row, tp, col, row)}[key]
    return blank(
        stem="행이 실제, 열이 예측인 혼동 행렬 %s에서 %s 소수 셋째 자리까지 쓰면 ____ 입니다. 클래스 번호는 0부터 셉니다."
             % (mat(m), name),
        blanks=[{"answer": [answer], "mode": "number", "places": 3, "hint": "소수 셋째 자리"}],
        explain="%s 소수 셋째 자리로 반올림하면 %s입니다." % (how, answer),
        params={"m": m, "metric": key, "k": k})


@gen("i09-g05", unit="9e", level=2, tags=["torch.max", "정확도"], ref=["9차시 슬 p12", "9차시 노트북 01 [41]", "9차시 과제 6번"],
     step="9e/2", facts=["F09-21", "F09-23"], basis="lecture-example", family="argmax-acc", prio=3)
def predict_acc(r):
    """데이터 4개나 5개, 클래스 3개나 4개의 logit(−1.0~3.0, 소수 한 자리, 행마다 가장 큰 값은 하나)과 정답. 틀이 둘이고 시드로
    고름: torch.max(outputs, 1)[1] 의 값이나, 그 예측과 정답으로 센 정확도."""
    n = r.pick([4, 5])
    c = r.pick([3, 4])
    rows = []
    for _ in range(n):
        row = [Decimal(r.int(-10, 30)) / 10 for _ in range(c)]
        if row.count(max(row)) > 1:
            raise Retry("가장 큰 값이 둘")
        rows.append(row)
    labels = [r.int(0, c - 1) for _ in range(n)]
    pred = [row.index(max(row)) for row in rows]
    hits = sum(1 for p, y in zip(pred, labels) if p == y)
    if hits in (0, n):
        raise Retry("모두 맞히거나 모두 틀림")
    tops = [max(row) for row in rows]
    if r.chance(0.5):
        return blank(
            stem="outputs가 %s일 때 `torch.max(outputs, 1)[1]`의 값은 ____ 입니다." % mat(rows),
            blanks=[{"answer": ["[%s]" % ", ".join(str(p) for p in pred)], "mode": "values", "hint": "값 목록"}],
            explain="`[1]`은 행마다 가장 큰 값의 위치(indices)입니다. 행마다 가장 큰 값 [%s]의 위치가 [%s]입니다. [%s]처럼 답했다면 "
                    "values인 `[0]`을 적은 것입니다." % (", ".join(shown(t) for t in tops), ", ".join(str(p) for p in pred),
                                                     ", ".join(shown(t) for t in tops)),
            params={"form": "pred", "rows": [[dec(v) for v in row] for row in rows], "y": labels})
    acc = Decimal(hits) / n
    return blank(
        stem="outputs가 %s이고 정답이 [%s]입니다. 예측을 `torch.max(outputs, 1)[1]`로 고르면 정확도는 ____ 입니다."
             % (mat(rows), ", ".join(str(v) for v in labels)),
        blanks=[{"answer": [dec(acc)], "mode": "number", "hint": "숫자"}],
        explain="행마다 가장 큰 값의 위치를 고르면 예측은 [%s]입니다. 예측과 정답 [%s]에서 같은 자리가 %d개라 %d ÷ %d = %s입니다."
                % (", ".join(str(p) for p in pred), ", ".join(str(v) for v in labels), hits, hits, n, shown(acc)),
        params={"form": "acc", "rows": [[dec(v) for v in row] for row in rows], "y": labels})
