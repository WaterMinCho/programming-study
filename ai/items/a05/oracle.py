"""공개한 조건에서 남는 에폭, 출력 채널, block3 곱셈 수를 생성기와 따로 계산함."""


def a05_g01(params):
    best, kept = 0.0, None
    for epoch, value in enumerate(params["accs"]):
        acc = value / 100
        if (acc > best) if params["op"] == ">" else (acc >= best):
            best, kept = acc, epoch
    return [str(kept)]


def a05_g02(params):
    outputs = [params["n1"], params["n3"], params["n5"], params["pp"]]
    if params["form"] == "out":
        return [str(sum(outputs))]
    known = sum(value for value in outputs if value is not None)
    return [str(params["next_in"] - known)]


def a05_g03(params):
    layers = [(1, params["cin"], params["red"]), (3, params["red"], params["out"]), (3, params["out"], params["out"])]
    return [str(sum(k * k * cin * cout for k, cin, cout in layers))]
