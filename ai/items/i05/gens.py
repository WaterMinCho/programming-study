# -*- coding: utf-8 -*-
"""5차시 생성기. Linear 층 모델의 파라미터 수, 층마다 같은 수를 곱한 기울기 크기, 한 에폭의 배치 수, 특징 하나의 배치 정규화 계산,
k번마다 기록한 마지막 손실의 반복 번호.

표준 라이브러리와 aiprep.gen 만 씀. 실수는 Decimal 로 계산해 글로 바꿈.
"""
from decimal import Decimal, ROUND_HALF_UP

from aiprep.gen import Retry, blank, fixed, gen, num

MINUS = "−"


def dec(value):
    """Decimal 을 지수 표기 없이 짧은 글로. 1.50 은 1.5, 2.0 은 2."""
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    out = format(value.normalize(), "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return "0" if out in ("-0", "") else out


def shown(value):
    """화면에 보일 숫자. 빼기는 빼기표로."""
    return dec(value).replace("-", MINUS)


def paren(value):
    out = shown(value)
    return "(%s)" % out if out.startswith(MINUS) else out


@gen("i05-g01", unit="5a", level=2, tags=["파라미터 수"], ref=["5차시 슬 p6", "5차시 과제 5번"],
     step="5a/4", facts=["F05-61"], basis="lecture-formula", family="linear-params", prio=2)
def linear_params(r):
    """Linear 층 둘이나 셋을 ReLU 로 이은 모델의 학습 파라미터 수. 층마다 입력 수 × 출력 수 + 출력 수를 더함.
    입력 8·16·20·32·64·784, 은닉 16·32·64·128·256, 출력 1·2·3·5·10. 과제 5번의 20-64-32-1 은 다시 뽑음."""
    sizes = [r.pick([8, 16, 20, 32, 64, 784]), r.pick([16, 32, 64, 128, 256])]
    if r.chance(0.5):
        sizes.append(r.pick([16, 32, 64, 128]))
    sizes.append(r.pick([1, 2, 3, 5, 10]))
    if sizes == [20, 64, 32, 1]:
        raise Retry("과제 5번과 같은 모델")
    layers = list(zip(sizes, sizes[1:]))
    parts = [a * b + b for a, b in layers]
    total = sum(parts)
    lines = []
    for k, (a, b) in enumerate(layers):
        lines.append("    nn.Linear(%d, %d)," % (a, b))
        if k < len(layers) - 1:
            lines.append("    nn.ReLU(),")
    code = "```python\nnet = nn.Sequential(\n%s\n)\n```" % "\n".join(lines)
    work = " + ".join("(%d × %d + %d)" % (a, b, b) for a, b in layers)
    no_bias = sum(a * b for a, b in layers)
    return blank(
        stem="다음 모델의 학습 파라미터는 모두 ____ 개입니다.\n\n%s" % code,
        blanks=[{"answer": [str(total)], "mode": "number", "unit": "개", "hint": "숫자"}],
        explain="Linear 층마다 weight 입력 수 × 출력 수 개와 bias 출력 수 개를 더하고, ReLU에는 파라미터가 없습니다. %s = %s입니다. "
                "bias를 빼면 %s개가 나옵니다." % (work, num(total), num(no_bias)),
        params={"sizes": sizes})


@gen("i05-g02", unit="5c", level=2, tags=["기울기 소실", "기울기 폭발"], ref=["5차시 슬 p18"],
     step="5c/3", facts=["F05-22", "F05-52"], basis="lecture-example", family="grad-power", prio=3)
def grad_power(r):
    """역전파에서 층마다 기울기가 r배가 될 때 n층 뒤의 기울기 크기 r^n(처음 1). r 은 0.5·0.8·0.9(소실)나 1.1·1.2(폭발),
    n 은 2~10. 정답은 소수 넷째 자리까지 반올림하고 버리는 첫 자리가 4·5·6 이면 다시 뽑음."""
    r_text = r.pick(["0.5", "0.8", "0.9", "1.1", "1.2"])
    n = r.int(2, 10)
    value = Decimal(r_text) ** n
    answer = fixed(value, 4)
    kind = "기울기 소실" if Decimal(r_text) < 1 else "기울기 폭발"
    return blank(
        stem="역전파에서 층을 하나 지날 때마다 기울기가 %s배가 됩니다. 출력 쪽 기울기를 1로 두면 %d층을 거꾸로 지난 뒤 기울기는 ____ 입니다. "
             "소수 넷째 자리까지 반올림해 쓰세요." % (r_text, n),
        blanks=[{"answer": [answer], "mode": "number", "places": 4, "hint": "숫자"}],
        explain="층마다 %s배가 되므로 %d층 뒤 기울기는 %s의 %d제곱인 %s이고, 반올림하면 %s입니다. 곱하는 수가 1보다 %s 층이 늘수록 %s %s입니다. "
                "%s × %d = %s처럼 층 수를 곱하면 틀립니다."
                % (r_text, n, r_text, n, dec(value), answer, "작아서" if kind == "기울기 소실" else "커서",
                   "0에 가까워지는" if kind == "기울기 소실" else "커지는", kind, r_text, n, dec(Decimal(r_text) * n)),
        params={"r": r_text, "n": n})


@gen("i05-g03", unit="5d", level=2, tags=["미니배치", "배치 수"], ref=["5차시 슬 p26", "5차시 노트북 03 [12]"],
     step="5d/3", facts=["F05-35", "F05-62"], basis="lecture-example", family="batches", prio=3)
def batches(r):
    """훈련 데이터 N 개를 배치 크기 B 로 나눌 때 한 에폭의 배치 수(N ÷ B 를 올림), 마지막 배치의 데이터 수, E 에폭의 전체 갱신 수.
    틀이 셋이고 시드로 고름. N 은 600~60,000, B 는 8~512, E 는 2~10. B 가 N 의 절반보다 크면 다시 뽑음."""
    n = r.pick([600, 800, 1000, 1200, 2000, 5000, 10000, 50000, 60000])
    b = r.pick([8, 16, 32, 64, 100, 128, 256, 512])
    if b * 2 > n:
        raise Retry("배치가 너무 큼")
    count = -(-n // b)
    last = n - (count - 1) * b
    ask = r.pick(["count", "last", "total"])
    head = "학습 데이터 %s개를 `DataLoader(..., batch_size=%d)`로 나눠 미니배치 경사하강법으로 학습합니다." % (num(n), b)
    floor_note = "%s ÷ %d = %s이고, 이 값을 올리면 배치는 %d개입니다." % (num(n), b, dec(Decimal(n) / b), count)
    if ask == "count":
        return blank(stem=head + " 한 에폭에 파라미터를 ____ 번 갱신합니다.",
                     blanks=[{"answer": [str(count)], "mode": "number", "unit": "번", "hint": "숫자"}],
                     explain="배치마다 한 번 갱신합니다. %s 마지막 배치에는 %d개가 들어갑니다." % (floor_note, last),
                     params={"ask": ask, "N": n, "B": b})
    if ask == "last":
        return blank(stem=head + " 한 에폭의 마지막 배치에 든 데이터는 ____ 개입니다.",
                     blanks=[{"answer": [str(last)], "mode": "number", "unit": "개", "hint": "숫자"}],
                     explain="%s 앞의 %d개 배치에 %d × %d = %s개가 들어가고 남은 %s − %s = %d개가 마지막 배치입니다."
                             % (floor_note, count - 1, count - 1, b, num((count - 1) * b), num(n), num((count - 1) * b), last),
                     params={"ask": ask, "N": n, "B": b})
    epochs = r.int(2, 10)
    return blank(stem=head + " %d 에폭 동안 파라미터를 모두 ____ 번 갱신합니다." % epochs,
                 blanks=[{"answer": [str(count * epochs)], "mode": "number", "unit": "번", "hint": "숫자"}],
                 explain="%s 한 에폭의 갱신 수는 배치 수와 같아서 %d × %d = %s번입니다."
                         % (floor_note, count, epochs, num(count * epochs)),
                 params={"ask": ask, "N": n, "B": b, "E": epochs})


@gen("i05-g04", unit="5f", level=2, tags=["배치 정규화"], ref=["5차시 슬 p28"],
     step="5f/2", facts=["F05-40", "F05-64"], basis="lecture-formula", family="bn-calc", prio=2)
def bn_value(r):
    """특징 하나의 배치 정규화 계산(ε 은 빼고 분산은 데이터 수로 나눔). 값은 평균 m 에 k × [−3, −1, 0, 1, 3] 이나 k × [−2, −2, 2, 2] 를
    더한 것이라 표준편차가 2k 로 떨어짐. 틀이 셋이고 시드로 고름: 분산, 한 값의 x̂, γ·β 를 쓴 y."""
    pattern = r.pick([[-3, -1, 0, 1, 3], [-2, -2, 2, 2]])
    k = r.int(1, 3)
    m = r.int(2, 9)
    values = [m + k * d for d in pattern]
    r.shuffle(values)
    n = len(values)
    mean = Decimal(sum(values)) / n
    var = sum((Decimal(v) - mean) ** 2 for v in values) / n
    sd = var.sqrt()
    pick = r.pick([v for v in values if v != m])
    xhat = (Decimal(pick) - mean) / sd
    shown_values = "[" + ", ".join(shown(v) for v in values) + "]"
    head = "데이터 %d개로 된 배치가 한 특징에 낸 값은 %s입니다. ε은 빼고 분산은 데이터 수로 나눕니다." % (n, shown_values)
    ask = r.pick(["var", "xhat", "y"])
    if ask == "var":
        return blank(stem=head + " 배치 정규화가 쓰는 분산 σ²은 ____ 입니다.",
                     blanks=[{"answer": [dec(var)], "mode": "number", "hint": "숫자"}],
                     explain="평균은 %s입니다. 값마다 평균을 빼고 제곱해 더하면 %s이고, 데이터 수 %d로 나누면 %s입니다. %d − 1로 나누면 틀립니다."
                             % (dec(mean), dec(var * n), n, dec(var), n),
                     params={"ask": ask, "values": values})
    if ask == "xhat":
        return blank(stem=head + " 값 %s의 x̂는 ____ 입니다." % shown(pick),
                     blanks=[{"answer": [dec(xhat)], "mode": "number", "hint": "숫자"}],
                     explain="평균은 %s, 분산은 %s, 표준편차는 %s입니다. (%s − %s) ÷ %s = %s입니다. 표준편차 대신 분산으로 나누면 틀립니다."
                             % (dec(mean), dec(var), dec(sd), shown(pick), dec(mean), dec(sd), shown(xhat)),
                     params={"ask": ask, "values": values, "pick": pick})
    gamma = r.pick([2, 3])
    beta = Decimal(r.pick(["-1", "0.5", "1"]))
    y = gamma * xhat + beta
    return blank(stem=head + " γ = %d, β = %s일 때 값 %s의 y는 ____ 입니다." % (gamma, shown(beta), shown(pick)),
                 blanks=[{"answer": [dec(y)], "mode": "number", "hint": "숫자"}],
                 explain="평균은 %s, 표준편차는 %s입니다. x̂ = (%s − %s) ÷ %s = %s이고, y = %d × %s + %s = %s입니다. "
                         "γ와 β를 쓰기 전의 x̂에서 멈추면 틀립니다."
                         % (dec(mean), dec(sd), shown(pick), dec(mean), dec(sd), shown(xhat), gamma, paren(xhat), paren(beta), shown(y)),
                 params={"ask": ask, "values": values, "pick": pick, "gamma": gamma, "beta": dec(beta)})


@gen("i05-g05", unit="5g", level=3, tags=["손실 기록"], ref=["5차시 과제 4번", "4차시 노트북 01 [39]"],
     step="5g/5", facts=["F05-101"], basis="lecture-example", family="last-record", prio=3, errata=["X05-20"])
def last_record(r):
    """range(E) 루프에서 epoch % k == 0 일 때 갱신 전 손실을 기록할 때, 마지막 기록의 반복 번호 k × ⌊(E − 1) ÷ k⌋ 나 기록 개수
    ⌊(E − 1) ÷ k⌋ + 1. E 는 100~1000(10 간격), k 는 10·20·25·30·40·50·100. 틀이 둘이고 시드로 고름.
    정정 주제임: 주차별 과제 1주차 5차시 2번은 마지막 기록을 최종 손실로 찍음(X05-20). 모의고사에 넣지 않음."""
    e = r.int(10, 100) * 10
    k = r.pick([10, 20, 25, 30, 40, 50, 100])
    if k * 2 > e:
        raise Retry("기록이 너무 적음")
    last = k * ((e - 1) // k)
    count = (e - 1) // k + 1
    code = ("```python\nhistory = []\nfor epoch in range(%d):\n    loss = mse(pred(X), Y)    # 이번 갱신 전의 손실\n    loss.backward()\n"
            "    with torch.no_grad():\n        W -= lr * W.grad\n    W.grad.zero_()\n    if epoch %% %d == 0:\n"
            "        history.append(loss.item())\nprint(history[-1])\n```" % (e, k))
    if r.chance(0.6):
        return blank(stem="다음 코드의 마지막 줄은 `epoch` 값이 ____ 일 때 갱신하기 전에 잰 손실을 찍습니다.\n\n%s" % code,
                     blanks=[{"answer": [str(last)], "mode": "number", "hint": "반복 번호"}],
                     explain="epoch는 0부터 %d까지이고 %d의 배수일 때 기록합니다. 마지막 배수가 %d입니다. 그 반복에서 갱신하기 전에 잰 손실이 찍히고, "
                             "그 뒤로 %d번 더 갱신합니다. %d라고 답했다면 마지막 반복이 늘 기록된다고 본 것입니다."
                             % (e - 1, k, last, e - last, e - 1),
                     params={"ask": "last", "E": e, "k": k})
    return blank(stem="다음 코드가 끝났을 때 `history`에 든 손실은 ____ 개입니다.\n\n%s" % code,
                 blanks=[{"answer": [str(count)], "mode": "number", "unit": "개", "hint": "숫자"}],
                 explain="epoch가 0, %d, %d, …, %d일 때 기록하므로 %d ÷ %d의 소수점 아래를 버린 %d에 epoch가 0일 때 남긴 기록 하나를 더해 %d개입니다."
                         % (k, 2 * k, last, e - 1, k, (e - 1) // k, count),
                 params={"ask": "count", "E": e, "k": k})
