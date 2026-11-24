"""판별기 출력 두 값으로 GAN 손실을, 이미지 크기와 블록 수로 판별기 Linear 입력 길이를, 잠재 차원마다 평균과 로그 분산을 바꿔 VAE KL 항의 합을 묻는 생성기."""
import math

from aiprep.gen import Retry, blank, fixed, gen, num


_TAKEN_D = {(80, 30), (90, 30), (90, 20), (65, 30), (60, 10)}
_TAKEN_G = {30, 20, 10}


@gen("a07-g01", unit="a7a", level=2, tags=["app.a7a"], ref=["응용 7차시 노트북 03 [23]", "응용 7차시 노트북 01 [10]"],
     facts=["FA07-a3", "FA07-a4"], basis="lecture-formula", step="a7a/3", family="a07-gan-loss")
def gan_loss(r):
    """판별기가 진짜 사진과 가짜 사진에 낸 값을 주고 판별기 손실의 합·평균이나 생성기 손실을 물음."""
    form = r.pick(["sum", "mean", "gen"])
    real = r.int(11, 19) * 5
    fake = r.int(1, 9) * 5
    p, q = real / 100, fake / 100
    if form == "gen":
        if fake in _TAKEN_G:
            raise Retry("본문·고정 문항과 같은 값")
        value = -math.log(q)
        answer = fixed(value, 4)
        stem = ("판별기가 진짜 사진에 낸 값은 %s, 생성기의 가짜 사진에 낸 값은 %s입니다. 생성기 손실은 가짜 사진에 대한 판별기 출력을 정답 1과 비교한 BCE입니다. "
                "생성기 손실은 소수 넷째 자리까지 ____ 입니다." % (num(p), num(q)))
        explain = "생성기 손실은 가짜 사진에 낸 값만 씁니다. 정답이 1이라 BCE는 −ln p이고, −ln %s = %s입니다." % (num(q), answer)
        params = {"form": form, "real": real, "fake": fake}
    else:
        if (real, fake) in _TAKEN_D:
            raise Retry("본문·고정 문항과 같은 값")
        a, b = -math.log(p), -math.log(1 - q)
        value = a + b if form == "sum" else (a + b) / 2
        answer = fixed(value, 4)
        how = "두 BCE를 더한" if form == "sum" else "두 BCE의 평균으로 계산한"
        stem = ("판별기가 진짜 사진에 낸 값은 %s, 가짜 사진에 낸 값은 %s입니다. 진짜 사진의 정답은 1, 가짜 사진의 정답은 0입니다. "
                "%s 판별기 손실은 소수 넷째 자리까지 ____ 입니다." % (num(p), num(q), how))
        tail = "둘을 더하면" if form == "sum" else "둘을 더해 2로 나누면"
        explain = ("진짜 쪽은 −ln %s, 가짜 쪽은 −ln(1 − %s) = −ln %s입니다. %s %s입니다."
                   % (num(p), num(q), num(round(1 - q, 2)), tail, answer))
        params = {"form": form, "real": real, "fake": fake}
    return blank(stem=stem, blanks=[{"answer": [answer], "mode": "number", "places": 4}], explain=explain, params=params)


gan_loss.gen_spec.meta.update(template_revision="gan-loss-1", author_difficulty=2, display_params=["form", "real", "fake"])


_SIZES = [32, 48, 64, 96, 128, 192, 256]
_TAKEN_DS = {(32, 4, 16), (64, 4, 16), (128, 5, 16), (256, 5, 16)}


@gen("a07-g02", unit="a7d", level=2, tags=["app.a7d"], ref=["응용 7차시 노트북 01 [5]"], facts=["FA07-d1"],
     basis="lecture-formula", step="a7d/4", family="a07-disc-linear")
def disc_linear(r):
    """이미지 크기, 블록 수, 첫 블록 채널을 주고 ds_size 와 Linear 입력 길이를 물음. 블록마다 채널은 두 배."""
    size = r.pick(_SIZES)
    blocks = r.int(3, 5)
    first = r.pick([8, 16, 32])
    if size % (2 ** blocks):
        raise Retry("가로세로가 블록마다 정확히 반이 되지 않음")
    if (size, blocks, first) in _TAKEN_DS:
        raise Retry("본문·고정 문항과 같은 조건")
    chans = [first * 2 ** k for k in range(blocks)]
    ds = size // 2 ** blocks
    length = chans[-1] * ds * ds
    shown = ", ".join(str(c) for c in chans)
    stem = ("판별기 블록이 %d개이고, 블록마다 첫 층은 `nn.Conv2d(…, 3, 2, 1)`이라 가로세로가 반으로 줄어듭니다. 블록의 출력 채널은 차례로 %s입니다. "
            "ds_size는 `image_sz // 2 ** %d`입니다. image_sz가 %d이면 ds_size는 ____ 이고, 마지막 블록 뒤 Linear 층의 입력 길이는 ____ 입니다."
            % (blocks, shown, blocks, size))
    explain = ("ds_size = %d // 2 ** %d = %d // %d = %d입니다. Linear 층의 입력 길이는 마지막 블록의 출력 채널 %d에 ds_size를 두 번 곱한 %d × %d × %d = %s입니다."
               % (size, blocks, size, 2 ** blocks, ds, chans[-1], chans[-1], ds, ds, num(length)))
    return blank(stem=stem, blanks=[{"answer": [str(ds)], "mode": "number"}, {"answer": [str(length)], "mode": "number"}],
                 explain=explain, params={"size": size, "blocks": blocks, "first": first})


disc_linear.gen_spec.meta.update(template_revision="disc-linear-1", author_difficulty=2, display_params=["size", "blocks", "first"])


_LOG_VAR = {"0": 0.0, "ln 4": math.log(4), "ln 0.25": math.log(0.25), "ln 9": math.log(9)}
_SHOWN_LN = {"ln 4": "ln 4 = 1.3863", "ln 0.25": "ln 0.25 = −1.3863", "ln 9": "ln 9 = 2.1972"}
_ROUNDED = {"0": 0.0, "ln 4": 1.3863, "ln 0.25": -1.3863, "ln 9": 2.1972}
_VARIANCE = {"0": 1, "ln 4": 4, "ln 0.25": 0.25, "ln 9": 9}
_TAKEN_KL = {
    ((1, "0"),),
    ((2, "0"),),
    ((0, "ln 4"),),
    ((0, "ln 0.25"),),
    ((0, "ln 9"),),
    ((1, "ln 4"),),
    ((1, "0"), (0, "ln 4")),
    ((1, "0"), (0, "ln 0.25")),
}


def _signed(m):
    return "−%d" % -m if m < 0 else str(m)


def _term(m, log_var):
    return -0.5 * (1 + _LOG_VAR[log_var] - m * m - math.exp(_LOG_VAR[log_var]))


def _hand_term(m, log_var):
    return -0.5 * (1 + _ROUNDED[log_var] - m * m - _VARIANCE[log_var])


@gen("a07-g03", unit="a7f", level=2, tags=["app.a7f"], ref=["응용 7차시 노트북 02 [11]", "arXiv 문서 1312.6114"],
     facts=["FA07-f1"], basis="lecture-formula", step="a7f/3", family="a07-kl-term")
def kl_term(r):
    """잠재 차원 1~3개의 (μ, log σ²)를 주고 KL 항의 합을 소수 셋째 자리까지 물음."""
    k = r.int(1, 3)
    dims = [(r.int(-2, 2), r.pick(sorted(_LOG_VAR))) for _ in range(k)]
    if tuple(dims) in _TAKEN_KL:
        raise Retry("본문·고정 문항과 같은 값")
    if all(m == 0 and lv == "0" for m, lv in dims):
        raise Retry("KL 항이 0")
    exact = sum(_term(m, lv) for m, lv in dims)
    hand = sum(_hand_term(m, lv) for m, lv in dims)
    answer = fixed(exact, 3)
    if fixed(hand, 3) != answer:
        raise Retry("ln 을 넷째 자리로 반올림한 손계산과 답이 갈림")
    pairs = ", ".join("(%s, %s)" % (_signed(m), lv) for m, lv in dims)
    used = [_SHOWN_LN[lv] for lv in sorted({lv for _, lv in dims}) if lv in _SHOWN_LN]
    given = (" %s입니다." % ", ".join(used)) if used else ""
    stem = ("VAE 인코더가 잠재 차원 %d개에 낸 (μ, log σ²)가 차례로 %s입니다.%s "
            "KL 항 −0.5 × Σ(1 + log σ² − μ² − σ²)로 모든 차원을 더한 값은 소수 셋째 자리까지 ____ 입니다." % (k, pairs, given))
    steps = []
    for m, lv in dims:
        ln = _ROUNDED[lv]
        shown = "(−%s)" % num(-ln) if ln < 0 else num(ln)
        steps.append("(%s, %s)에서 σ² = %s이고 −0.5 × (1 + %s − %s − %s) = %.4f" % (
            _signed(m), lv, num(_VARIANCE[lv]), shown, num(m * m), num(_VARIANCE[lv]), _hand_term(m, lv)))
    if k == 1:
        explain = "%s입니다. 소수 셋째 자리까지 쓰면 %s입니다." % (steps[0], answer)
    else:
        explain = "차원마다 계산해 더합니다. %s입니다. 모두 더하면 %s입니다." % ("입니다. ".join(steps), answer)
    return blank(stem=stem, blanks=[{"answer": [answer], "mode": "number", "places": 3}], explain=explain,
                 params={"dims": [[m, lv] for m, lv in dims]})


kl_term.gen_spec.meta.update(template_revision="vae-kl-1", author_difficulty=2, display_params=["dims"])
