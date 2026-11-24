"""캡션의 낱말 수와 max_len, 디코더 층의 크기, METEOR 의 길이·짝·덩어리 수 조건을 바꿔 물음."""
from aiprep.gen import Retry, blank, fixed, gen, num

_TAKEN = {(3, 10), (18, 10), (18, 20), (4, 12), (3, 8), (4, 10), (1, 10), (6, 10)}
_RULE = ("캡션을 번호 줄로 바꿀 때 `<start>` 번호 1로 시작해 낱말 번호를 하나씩 붙이고, 길이가 max_len − 1이 되면 낱말 붙이기를 멈춥니다. "
         "그 뒤에 `<end>` 번호 2를 붙이고 모자란 자리를 0으로 채웁니다. ")


@gen("a08-g01", unit="a8a", level=2, tags=["app.a8a"], ref=["응용 8차시 노트북 02 [23]", "응용 8차시 노트북 02 [26]"],
     facts=["FA08-a4"], basis="lecture-example", step="a8a/3", family="a08-pad-count")
def pad_count(r):
    """낱말 수와 max_len 을 주고 끝에 붙는 0의 개수나 번호 줄에 남는 낱말 수를 물음."""
    max_len = r.int(6, 25)
    words = r.int(1, 30)
    if (words, max_len) in _TAKEN:
        raise Retry("본문·고정 문항과 같은 조건")
    form = r.pick(["zeros", "kept"])
    kept = min(words, max_len - 2)
    zeros = max_len - kept - 2
    if form == "zeros" and zeros == 0:
        raise Retry("0을 채우지 않는 조건")
    if form == "kept" and words <= max_len - 2:
        raise Retry("낱말이 잘리지 않는 조건")
    head = _RULE + "낱말이 %d개인 캡션을 max_len=%d로 바꿉니다. " % (words, max_len)
    if form == "zeros":
        stem = head + "끝에 붙는 0은 ____ 개입니다."
        answer = zeros
        explain = ("낱말 %d개는 모두 남습니다. 시작과 끝 토큰 두 자리와 낱말 %d자리를 합쳐 %d자리를 쓰므로 "
                   "남은 %d − %d = %d자리가 0입니다." % (words, words, words + 2, max_len, words + 2, zeros))
    else:
        stem = head + "번호 줄에 남는 낱말은 ____ 개입니다."
        answer = kept
        explain = ("시작 토큰과 낱말을 합친 길이가 %d − 1 = %d에 이르면 멈추므로 낱말은 %d개까지 붙습니다. "
                   "끝 토큰까지 붙인 번호 줄 길이는 max_len과 같은 %d입니다. 붙이지 못한 낱말 %d개는 버려집니다." % (max_len, max_len - 1, kept, max_len, words - kept))
    return blank(stem=stem, blanks=[{"answer": [str(answer)], "mode": "number"}], explain=explain,
                 params={"form": form, "words": words, "max_len": max_len})


pad_count.gen_spec.meta.update(template_revision="pad-count-1", author_difficulty=2, display_params=["form", "words", "max_len"])


_TAKEN_PARAMS = {("lstm", 128, 256), ("embedding", 128, 5000)}


@gen("a08-g02", unit="a8d", level=2, tags=["app.a8d"], ref=["응용 8차시 노트북 01 [20]", "PyTorch 문서 LSTM"],
     facts=["FA08-d2"], basis="lecture-formula", step="a8d/2", family="a08-decoder-params")
def decoder_params(r):
    """어휘 수 V, 임베딩 길이 E, 은닉 상태 길이 H 를 주고 디코더 한 층이나 세 층 합의 파라미터 수를 물음."""
    v = r.int(20, 120) * 100
    e = r.pick([64, 128, 200, 256, 300])
    h = r.pick([128, 256, 384, 512])
    form = r.pick(["embedding", "lstm", "linear", "total"])
    if (form, e, h) in _TAKEN_PARAMS or (form == "embedding" and (e, v) == (128, 5000)):
        raise Retry("본문·고정 문항과 같은 조건")
    emb = v * e
    lstm = 4 * (h * e + h * h + 2 * h)
    lin = h * v + v
    head = ("캡션 디코더를 `nn.Embedding(%d, %d)`, `nn.LSTM(%d, %d, 1, batch_first=True)`, `nn.Linear(%d, %d)`로 만듭니다. "
            % (v, e, e, h, h, v))
    lstm_text = ("LSTM은 네 묶음마다 입력 쪽 %d × %d, 은닉 상태 쪽 %d × %d, 편향 %d개 두 벌이 듭니다. "
                 "식은 4 × (%d × %d + %d × %d + 2 × %d)이고 %s입니다." % (h, e, h, h, h, h, e, h, h, h, num(lstm)))
    if form == "embedding":
        answer = emb
        stem = head + "Embedding 층의 파라미터는 ____ 개입니다."
        explain = "Embedding에는 낱말 %s개마다 길이 %d인 행이 하나씩 있어 %s × %d = %s입니다." % (num(v), e, num(v), e, num(emb))
    elif form == "lstm":
        answer = lstm
        stem = head + "LSTM 층의 파라미터는 ____ 개입니다."
        explain = lstm_text
    elif form == "linear":
        answer = lin
        stem = head + "Linear 층의 파라미터는 ____ 개입니다."
        explain = "Linear는 가중치 %d × %s개에 편향 %s개를 더해 %s입니다." % (h, num(v), num(v), num(lin))
    else:
        answer = emb + lstm + lin
        stem = head + "세 층의 파라미터를 모두 더하면 ____ 개입니다."
        explain = ("Embedding은 %s × %d = %s개, Linear는 %d × %s + %s = %s개입니다. %s "
                   "셋을 더하면 %s개입니다." % (num(v), e, num(emb), h, num(v), num(v), num(lin), lstm_text, num(answer)))
    return blank(stem=stem, blanks=[{"answer": [str(answer)], "mode": "number"}], explain=explain,
                 params={"V": v, "E": e, "H": h, "form": form})


decoder_params.gen_spec.meta.update(template_revision="decoder-params-1", author_difficulty=2,
                                    display_params=["V", "E", "H", "form"])


_NOTE_METEOR = {(7, 7, 8, 2), (6, 6, 8, 3), (6, 6, 8, 1), (8, 8, 8, 8), (8, 8, 8, 2)}
_WHAT = {"fmean": "Fmean은", "penalty": "덩어리 벌점은", "score": "점수는"}


@gen("a08-g03", unit="a8f", level=2, tags=["app.a8f"], ref=["응용 8차시 슬 p16", "NLTK 문서 meteor_score"],
     facts=["FA08-f2"], basis="lecture-formula", step="a8f/3", family="a08-meteor")
def meteor_parts(r):
    """정답·후보 길이, 짝이 된 낱말 수, 덩어리 수를 주고 METEOR 의 Fmean, 벌점, 점수 가운데 하나를 물음."""
    ref_len = r.int(6, 14)
    cand_len = r.int(4, ref_len + 3)
    m = r.int(2, min(cand_len, ref_len))
    k = r.int(1, m)
    form = r.pick(["fmean", "penalty", "score"])
    if (m, cand_len, ref_len, k) in _NOTE_METEOR:
        raise Retry("본문·고정 문항과 같은 조건")
    p, rr = m / cand_len, m / ref_len
    fmean = 10 * p * rr / (rr + 9 * p)
    pen = 0.5 * (k / m) ** 3
    score = fmean * (1 - pen)
    if form == "fmean" and m == cand_len == ref_len:
        raise Retry("Fmean 이 1")
    value = {"fmean": fmean, "penalty": pen, "score": score}[form]
    answer = fixed(value, 4)
    stem = ("정답 캡션에는 낱말이 %d개, 후보 캡션에는 낱말이 %d개 있습니다. 후보 낱말 가운데 %d개가 정답 낱말과 짝이 되고, 짝이 된 낱말은 덩어리 %d개로 나뉩니다. "
            "METEOR의 %s 소수 넷째 자리까지 ____ 입니다." % (ref_len, cand_len, m, k, _WHAT[form]))
    pr = "P = %d/%d, R = %d/%d입니다." % (m, cand_len, m, ref_len)
    f_text = "Fmean = 10PR/(R + 9P)를 계산하면 %s입니다." % fixed(fmean, 4) if form != "fmean" else ""
    if form == "fmean":
        explain = "%s Fmean = 10PR/(R + 9P)에 넣어 계산하면 %s입니다." % (pr, answer)
    elif form == "penalty":
        explain = "벌점은 0.5 × (덩어리 수 ÷ 짝이 된 낱말 수)³입니다. 0.5 × (%d/%d)³을 계산하면 %s입니다." % (k, m, answer)
    else:
        explain = ("%s %s 벌점은 0.5 × (%d/%d)³ = %s입니다. 점수는 Fmean × (1 − 벌점)이고 %s입니다."
                   % (pr, f_text, k, m, fixed(pen, 4), answer))
    return blank(stem=stem, blanks=[{"answer": [answer], "mode": "number", "places": 4}], explain=explain,
                 params={"ref_len": ref_len, "cand_len": cand_len, "m": m, "k": k, "form": form})


meteor_parts.gen_spec.meta.update(template_revision="meteor-parts-1", author_difficulty=2,
                                  display_params=["ref_len", "cand_len", "m", "k", "form"])
