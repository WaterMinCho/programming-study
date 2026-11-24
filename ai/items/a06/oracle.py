"""공개한 조건으로 Gram 행렬 원소, 특징 모양, 기록 수를 생성기와 따로 계산함."""


def a06_g01(params):
    rows = {"1": list(params["c1"]) * params["reps"], "2": list(params["c2"]) * params["reps"]}
    left, right = rows[params["pair"][0]], rows[params["pair"][1]]
    total = 0
    for i in range(len(left)):
        total += left[i] * right[i]
    return [str(total)]


BLOCK_OF_KEY = [1, 1, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5]
OUT_CHANNELS = {1: 64, 2: 128, 3: 256, 4: 512, 5: 512}


def a06_g02(params):
    block = BLOCK_OF_KEY[params["key"] - 1]
    h, w = params["h"], params["w"]
    for _ in range(block - 1):
        h, w = int(h / 2), int(w / 2)
    return ["[1, %d, %d, %d]" % (OUT_CHANNELS[block], h, w)]


def a06_g03(params):
    logged = [e for e in range(params["epochs"]) if (e + 1) % params["every"] == 0]
    if params["form"] == "count":
        return [str(len(logged))]
    end = params["every"]
    while len(range(params["every"], end, params["every"])) != len(logged):
        end += 1
    return [str(end)]
