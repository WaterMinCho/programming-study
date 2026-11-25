"""동점이 있는 검증 정확도와 Inception 모듈의 채널·block3 곱셈 수의 조건을 바꿈."""
from aiprep.gen import Retry, blank, gen, num

@gen("a05-g01", unit="a5c", level=2, tags=["app.a5c"], ref=["응용 5차시 노트북 02 [15]", "응용 5차시 노트북 02 [21]"], facts=["FA05-c1"], basis="lecture-example", step="a5c/3", family="a05-tie-select")
def tie_select(r):
    """최고값이 여러 번 나오는 검증 정확도 목록과 비교 기호 하나를 주고 끝에 남는 가중치의 에폭을 물음."""
    n = r.int(6, 9)
    top = r.int(72, 95)
    count = r.int(2, 3)
    spots = sorted(r.sample(range(1, n), count))
    accs = [r.int(50, top - 1) for _ in range(n)]
    for i in spots:
        accs[i] = top
    op = r.pick([">", ">="])
    first, last = accs.index(top), n - 1 - accs[::-1].index(top)
    answer = first if op == ">" else last
    shown = ", ".join("%.2f" % (a / 100) for a in accs)
    where = "처음" if op == ">" else "마지막으로"
    rule = "최고와 같은 값에서는 조건이 거짓이라 복사하지 않습니다." if op == ">" else "최고와 같은 값에서도 조건이 참이라 다시 복사합니다."
    return blank(
        stem="에폭 번호를 0부터 셉니다. 검증 정확도가 차례로 [%s]이고 accuracy_epoch %s accuracy일 때 가중치를 복사합니다. accuracy는 0.0에서 시작합니다. 학습이 끝난 뒤 남는 가중치는 ____ 번 에폭의 것입니다." % (shown, op),
        blanks=[{"answer": [str(answer)], "mode": "number"}],
        explain="가장 큰 정확도는 %.2f이고 %s에 나옵니다. %s 그래서 최고값이 %s 나온 %d번 에폭의 가중치가 남습니다." % (
            top / 100, ", ".join("%d번" % i for i, a in enumerate(accs) if a == top), rule, where, answer),
        params={"accs": accs, "op": op})

tie_select.gen_spec.meta.update(template_revision="accuracy-tie-1", author_difficulty=2, display_params=["accs", "op"])

_CIN = [192, 256, 384, 480, 512, 528, 640, 832]
_OUT = [32, 48, 64, 96, 112, 128, 160, 192, 208, 224, 256, 288, 320, 384]
_RED = [16, 24, 32, 48, 64, 96, 112, 128, 144, 160, 192]
_FIXED_MODULES = {
    (192, 64, 96, 128, 16, 32, 32),
    (256, 128, 128, 192, 32, 96, 64),
    (480, 192, 96, 208, 16, 48, 64),
    (512, 160, 112, 224, 24, 64, 64),
    (512, 128, 128, 256, 24, 64, 64),
    (512, 112, 144, 288, 32, 64, 64),
    (528, 256, 160, 320, 32, 128, 128),
    (832, 256, 160, 320, 32, 128, 128),
    (832, 384, 192, 384, 48, 128, 128),
    (384, 128, 96, 192, 24, 64, 48),
}
_FIXED_BRANCH3 = {(m[0], m[4], m[5]) for m in _FIXED_MODULES}
_ARGS = "인자는 차례로 입력 채널, block1 출력, block2 첫 층 출력, block2 출력, block3 첫 층 출력, block3 출력, block4 출력입니다."


@gen("a05-g02", unit="a5e", level=2, tags=["app.a5e"], family="a05-out-channels",
     ref=["응용 5차시 노트북 04 [3]", "PyTorch 문서 torch.cat"],
     facts=["FA05-e1"], basis="lecture-formula", step="a5e/2")
def inception_out_channels(r):
    """출력 채널을 묻거나, 다음 모듈 입력과 세 갈래를 주고 남은 갈래의 채널을 물음."""
    cin = r.pick(_CIN)
    n1, n3, n5, pp = r.pick(_OUT), r.pick(_OUT), r.pick(_OUT[:8]), r.pick(_OUT[:7])
    r3, r5 = r.pick(_RED), r.pick(_RED[:6])
    if r3 >= n3 or r5 >= n5:
        raise Retry("축소 채널이 출력보다 크거나 같음")
    if (cin, n1, r3, n3, r5, n5, pp) in _FIXED_MODULES:
        raise Retry("본문 코드·고정 문항과 같은 설정")
    total = n1 + n3 + n5 + pp
    if n1 + r3 + r5 + pp == total:
        raise Retry("축소 채널을 고른 오답과 정답이 같음")
    form = r.pick(["out", "missing"])
    if form == "out":
        args = "(%d, %d, %d, %d, %d, %d, %d)" % (cin, n1, r3, n3, r5, n5, pp)
        stem = ("InceptionModule%s의 %s 네 갈래 모두 높이·너비를 지킵니다. 이 모듈을 지난 출력의 채널 수는 ____ 입니다."
                % (args, _ARGS))
        explain = ("갈래마다 마지막 층의 출력 채널만 채널 축으로 이어 붙입니다. %d + %d + %d + %d = %s입니다. "
                   "block2와 block3의 첫 층 출력은 같은 갈래의 다음 층으로 들어가므로 더하지 않습니다." % (n1, n3, n5, pp, num(total)))
        params = {"form": form, "cin": cin, "n1": n1, "r3": r3, "n3": n3, "r5": r5, "n5": n5, "pp": pp, "next_in": None}
        return blank(stem=stem, blanks=[{"answer": [str(total)], "mode": "number"}], explain=explain, params=params)
    miss = r.pick(["n1", "n3", "n5", "pp"])
    values = {"n1": n1, "n3": n3, "n5": n5, "pp": pp}
    answer = values[miss]
    shown = dict(values)
    shown[miss] = None
    text = {k: ("x" if v is None else str(v)) for k, v in shown.items()}
    args = "(%d, %s, %d, %s, %d, %s, %s)" % (cin, text["n1"], r3, text["n3"], r5, text["n5"], text["pp"])
    stem = ("InceptionModule%s의 바로 뒤 모듈은 입력 채널이 %d입니다. %s 네 갈래 모두 높이·너비를 지킵니다. "
            "x는 ____ 입니다." % (args, total, _ARGS))
    known = [v for k, v in values.items() if k != miss]
    explain = ("출력 채널은 네 갈래 출력의 합이고 바로 뒤 모듈의 입력 채널과 같아야 합니다. %d − (%d + %d + %d) = %s입니다."
               % (total, known[0], known[1], known[2], num(answer)))
    params = {"form": form, "cin": cin, "n1": shown["n1"], "r3": r3, "n3": shown["n3"], "r5": r5,
              "n5": shown["n5"], "pp": shown["pp"], "next_in": total}
    return blank(stem=stem, blanks=[{"answer": [str(answer)], "mode": "number"}], explain=explain, params=params)


@gen("a05-g03", unit="a5e", level=2, tags=["app.a5e"], family="a05-branch-mults",
     ref=["응용 5차시 노트북 04 [3]", "PyTorch 문서 Conv2d"],
     facts=["FA05-e2"], basis="lecture-formula", step="a5e/3")
def branch3_mults(r):
    """모듈 인자 일곱 개만 주고 block3 의 1×1, 3×3, 3×3 층을 코드에 적힌 대로 세게 함. bias·BN·ReLU 는 넣지 않음."""
    cin = r.pick(_CIN)
    red = r.pick([8, 12, 16, 24, 32, 48])
    out = r.pick([16, 24, 32, 48, 64, 96, 128])
    n1, n3, pp = r.pick(_OUT), r.pick(_OUT), r.pick(_OUT[:7])
    r3 = r.pick(_RED)
    if out <= red or r3 >= n3:
        raise Retry("축소 채널이 출력보다 크거나 같음")
    if (cin, red, out) in _FIXED_BRANCH3:
        raise Retry("본문 코드·고정 문항과 같은 block3")
    first, second, third = cin * red, 9 * red * out, 9 * out * out
    code = first + second + third
    five = first + 25 * red * out
    wrong = {five, second + third, first + second, 25 * cin * out, 9 * cin * out}
    if code in wrong:
        raise Retry("다른 구성으로 센 값과 겹침")
    args = "(%d, %d, %d, %d, %d, %d, %d)" % (cin, n1, r3, n3, red, out, pp)
    stem = ("InceptionModule%s를 만들었습니다. %s "
            "block3은 1×1, 3×3, 3×3 합성곱을 차례로 적용합니다. 첫 층의 출력 채널은 block3 첫 층 출력 인수이고, "
            "이후 두 층의 출력 채널은 block3 출력 인수입니다. "
            "출력 위치 하나에서 block3의 합성곱 층이 하는 곱셈 수는 모두 ____ 번입니다. "
            "bias, BatchNorm2d, ReLU는 세지 않습니다." % (args, _ARGS))
    explain = ("block3은 1×1 합성곱(%d→%d), 3×3 합성곱(%d→%d), 3×3 합성곱(%d→%d) 세 층입니다. "
               "층마다 커널 높이 × 너비 × 입력 채널 × 출력 채널을 세면 %s + %s + %s = %s번입니다."
               % (cin, red, red, out, out, out, num(first), num(second), num(third), num(code)))
    return blank(stem=stem, blanks=[{"answer": [str(code)], "mode": "number", "unit": "번"}], explain=explain,
                 params={"cin": cin, "n1": n1, "r3": r3, "n3": n3, "red": red, "out": out, "pp": pp})


inception_out_channels.gen_spec.meta.update(
    template_revision="inception-out-3", author_difficulty=2,
    display_params=["form", "cin", "n1", "r3", "n3", "r5", "n5", "pp", "next_in"])
branch3_mults.gen_spec.meta.update(
    template_revision="inception-branch3-3", author_difficulty=2,
    display_params=["cin", "n1", "r3", "n3", "red", "out", "pp"])
