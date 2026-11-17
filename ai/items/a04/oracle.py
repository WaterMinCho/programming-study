"""입력 조건에서 놓을 위치 수와 화살표 끝점의 가로 값을 계산함."""

def a04_g01(params):
    rows = params["h"] - params["th"] + 1
    cols = params["w"] - params["tw"] + 1
    return [str((rows, cols))]

def a04_g02(params):
    return [str(params["x"] + params["dx"] * params["scale"])]
