"""공개한 조건으로 GAN 손실, 판별기 Linear 입력 길이, VAE KL 항의 합을 생성기와 따로 계산함."""
import decimal
import math


def a07_g01(params):
    real, fake = params["real"] / 100.0, params["fake"] / 100.0
    if params["form"] == "gen":
        value = math.log(1.0 / fake)
    else:
        total = math.log(1.0 / real) + math.log(1.0 / (1.0 - fake))
        value = total if params["form"] == "sum" else total / 2.0
    return ["%.4f" % value]


def a07_g02(params):
    side = params["size"]
    channels = params["first"]
    for block in range(params["blocks"]):
        side = (side + 2 * 1 - 3) // 2 + 1
        if block:
            channels *= 2
    return [str(side), str(channels * side * side)]


def _log_var(text):
    if text == "0":
        return 0.0
    return math.log(float(text.split()[1]))


def a07_g03(params):
    total = 0.0
    for m, text in params["dims"]:
        lv = _log_var(text)
        total += 0.5 * (m * m + math.exp(lv) - 1 - lv)
    rounded = decimal.Decimal(repr(total)).quantize(decimal.Decimal("0.001"), rounding=decimal.ROUND_HALF_UP)
    return [str(rounded)]
