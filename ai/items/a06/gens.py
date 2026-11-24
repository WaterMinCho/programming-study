"""두 채널의 위치 값과 이어 붙인 횟수, 잘라 낸 VGG19 의 특징 모양, 에폭 기록 수의 조건을 바꿔 물음."""
from aiprep.gen import Retry, blank, gen, num

_TAKEN = {
    ((1, 0, 2), (3, 1, 0)),
    ((2, 0, 1), (1, 3, 2)),
    ((2, 1, 0), (0, 3, 1)),
}
_NAME = {"11": "채널 1과 채널 1", "12": "채널 1과 채널 2", "22": "채널 2와 채널 2"}
_CELL = {"11": "1행 1열", "12": "1행 2열", "22": "2행 2열"}


@gen("a06-g01", unit="a6b", level=2, tags=["app.a6b"], ref=["응용 6차시 슬 p7", "응용 6차시 노트북 01 [4]"],
     facts=["FA06-b1", "FA06-b2"], basis="lecture-example", step="a6b/2", family="a06-gram-entry")
def gram_entry(r):
    """두 채널의 위치 값(3~5개)을 주고 나누지 않은 Gram 행렬의 원소 하나를 물음. 같은 특징 맵 두 개를 가로로 이어 붙인 경우도 냄."""
    k = r.int(3, 5)
    c1 = [r.int(0, 5) for _ in range(k)]
    c2 = [r.int(0, 5) for _ in range(k)]
    if (tuple(c1), tuple(c2)) in _TAKEN:
        raise Retry("본문·고정 문항과 같은 값")
    pair = r.pick(["12", "12", "11", "22"])
    reps = r.pick([1, 1, 2])
    a = c1 if pair[0] == "1" else c2
    b = c1 if pair[1] == "1" else c2
    once = sum(x * y for x, y in zip(a, b))
    if once == 0:
        raise Retry("원소가 0")
    if sum(c1) == 0 or sum(c2) == 0:
        raise Retry("값이 모두 0인 채널")
    answer = once * reps
    shown1 = ", ".join(str(v) for v in c1)
    shown2 = ", ".join(str(v) for v in c2)
    terms = " + ".join("%d×%d" % (x, y) for x, y in zip(a, b))
    if reps == 1:
        stem = ("채널이 2개, 위치가 %d개인 특징 맵에서 채널 1의 값은 [%s], 채널 2의 값은 [%s]입니다. "
                "Gram 행렬의 %s 원소는 ____ 입니다." % (k, shown1, shown2, _CELL[pair]))
        explain = "%s의 값을 같은 위치끼리 곱해 더합니다. %s = %s입니다." % (_NAME[pair], terms, num(answer))
    else:
        stem = ("채널이 2개, 위치가 %d개인 특징 맵에서 채널 1의 값은 [%s], 채널 2의 값은 [%s]입니다. "
                "이 특징 맵 두 개를 가로로 이어 붙여 위치를 %d개로 만들었습니다. "
                "이어 붙인 특징 맵에서 위치 수로 나누지 않은 Gram 행렬의 %s 원소는 ____ 입니다." % (k, shown1, shown2, 2 * k, _CELL[pair]))
        explain = ("이어 붙이기 전 %s의 곱의 합은 %s = %s입니다. 같은 값이 두 번 나오므로 합도 두 배인 %s입니다."
                   % (_NAME[pair], terms, num(once), num(answer)))
    return blank(stem=stem, blanks=[{"answer": [str(answer)], "mode": "number"}], explain=explain,
                 params={"c1": c1, "c2": c2, "pair": pair, "reps": reps})


gram_entry.gen_spec.meta.update(template_revision="gram-entry-1", author_difficulty=2,
                                display_params=["c1", "c2", "pair", "reps"])


_CONVS = [2, 2, 4, 4, 4]
_CHANNELS = [64, 128, 256, 512, 512]
_NOTE_SIZES = {(128, 170), (128, 161), (100, 150), (96, 150)}
_NOTE_LOGS = {(300, 50), (450, 50), (500, 100), (200, 40)}


def _conv_name(key):
    left = key
    for block, count in enumerate(_CONVS, 1):
        if left <= count:
            return block, "conv%d_%d" % (block, left)
        left -= count
    raise ValueError(key)


@gen("a06-g02", unit="a6d", level=2, tags=["app.a6d"], family="a06-feature-shape",
     ref=["응용 6차시 노트북 02 [17]", "응용 6차시 노트북 02 [13]", "PyTorch 문서 AvgPool2d"],
     facts=["FA06-d8", "FA06-d12"], basis="lecture-formula", step="a6d/6")
def feature_shape(r):
    """평균 풀링으로 바꾼 VGG19 features 에 넣은 이미지 크기와 합성곱 번호를 주고 특징 모양을 물음."""
    h, w = r.int(64, 256), r.int(64, 256)
    key = r.int(3, 16)
    if (h, w) in _NOTE_SIZES:
        raise Retry("본문·고정 문항과 같은 크기")
    block, name = _conv_name(key)
    pools = block - 1
    if all((h >> i) % 2 == 0 and (w >> i) % 2 == 0 for i in range(pools)):
        raise Retry("소수를 버리는 자리가 없음")
    hs, ws = [h], [w]
    for _ in range(pools):
        hs.append(hs[-1] // 2)
        ws.append(ws[-1] // 2)
    c = _CHANNELS[block - 1]
    answer = "[1, %d, %d, %d]" % (c, hs[-1], ws[-1])
    stem = ("VGG19 features의 MaxPool2d를 AvgPool2d(kernel_size=2, stride=2)로 바꾸고 마지막 합성곱까지 잘랐습니다. "
            "합성곱은 블록마다 2, 2, 4, 4, 4개입니다. 출력 채널은 블록 차례로 64, 128, 256, 512, 512입니다. "
            "합성곱은 모두 3×3, stride=1, padding=1입니다. "
            "평균 풀링은 블록 끝마다 하나씩 있습니다. 모양이 (1, 3, %d, %d)인 이미지 텐서를 넣고 앞에서부터 %d번째 합성곱까지 지난 특징 맵의 모양은 ____ 입니다."
            % (h, w, key))
    explain = ("%d번째 합성곱 %s의 출력 채널은 %d이고, 그 앞에서 평균 풀링을 %d번 지납니다. "
               "지날 때마다 한 변을 2로 나누고 소수를 버리면 높이 %s, 너비 %s입니다."
               % (key, name, c, pools, " → ".join(map(str, hs)), " → ".join(map(str, ws))))
    return blank(stem=stem, blanks=[{"answer": [answer], "mode": "shape"}], explain=explain,
                 params={"h": h, "w": w, "key": key})


feature_shape.gen_spec.meta.update(template_revision="vgg19-feature-shape-1", author_difficulty=2, display_params=["h", "w", "key"])


@gen("a06-g03", unit="a6f", level=1, tags=["app.a6f"], family="a06-log-count",
     ref=["응용 6차시 노트북 02 [17]", "응용 6차시 노트북 02 [18]"],
     facts=["FA06-f3"], basis="lecture-example", step="a6f/4")
def log_count(r):
    """에폭 수와 기록 간격을 주고 기록 수나 range 끝 값을 물음."""
    every = r.pick([10, 20, 25, 40, 50, 60, 100])
    epochs = r.int(12, 60) * 10
    count = epochs // every
    if (epochs, every) in _NOTE_LOGS or count < 3 or count > 30:
        raise Retry("본문·고정 문항과 같은 조건이거나 기록 수가 너무 적거나 많음")
    form = r.pick(["count", "end"])
    loop = "for epoch in range(%d): 안에서 (epoch + 1) %% %d == 0일 때만 손실을 log에 하나씩 넣습니다." % (epochs, every)
    if form == "count":
        stem = loop + " 학습이 끝난 뒤 len(log)는 ____ 입니다."
        answer = count
        if count == 3:
            marks = "%d, %d, %d" % (every, 2 * every, 3 * every)
        else:
            marks = "%d, %d, …, %d" % (every, 2 * every, count * every)
        explain = ("epoch + 1은 1부터 %d까지라 %d의 배수인 %s에서 기록합니다. "
                   "그래서 기록 수는 에폭 수 %d를 간격 %d로 나눈 몫인 %d개입니다."
                   % (epochs, every, marks, epochs, every, count))
    else:
        stem = loop + (" 그래프의 x 값을 range(%d, 끝 값, %d)로 만들려고 합니다. "
                       "x 값의 개수가 len(log)와 같아지는 끝 값 가운데 가장 작은 정수는 ____ 입니다." % (every, every))
        answer = count * every + 1
        explain = ("기록은 %d개이고 마지막 기록 에폭은 %d입니다. range는 끝 값을 넣지 않으므로 %d를 넣으려면 끝 값이 %d보다 커야 합니다. "
                   "가장 작은 정수는 %d입니다." % (count, count * every, count * every, count * every, answer))
    return blank(stem=stem, blanks=[{"answer": [str(answer)], "mode": "number"}], explain=explain,
                 params={"form": form, "epochs": epochs, "every": every})


log_count.gen_spec.meta.update(template_revision="log-count-1", author_difficulty=1, display_params=["form", "epochs", "every"])
