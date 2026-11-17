"""apc 생성 문항의 정답을 생성기 코드를 보지 않고 공개 지문의 조건만으로 따로 계산함."""


def _shape_text(dims):
    return "(" + ", ".join(str(d) for d in dims) + ")"


def _half(value):
    """0.5 단위 값을 정수면 정수로, 아니면 소수 한 자리로 적음."""
    return str(int(value)) if float(value).is_integer() else "%.1f" % value


def apc_g101(p):
    # 슬라이스는 끝이 축 길이를 넘으면 축 끝에서 멈춤
    rows = max(0, min(p["top"] + p["h"], p["rows"]) - p["top"])
    cols = max(0, min(p["left"] + p["w"], p["cols"]) - p["left"])
    return [_shape_text((rows, cols, 3))]


def apc_g102(p):
    image = p["rgb"]
    plane = [[pixel[p["channel"]] for pixel in line] for line in image]
    return [str(plane), str(list(image[p["row"]][p["col"]]))]


def apc_g201(p):
    height, width = p["size"]
    mask = [[0] * width for _ in range(height)]
    for y, x in p["spots"]:
        mask[y][x] = 255
    order = [(y, x) for y in range(height) for x in range(width) if mask[y][x]]
    xs = [x for _, x in order]
    ys = [y for y, _ in order]
    return [str(xs[0]), str(min(xs)), str(max(ys))]


def apc_g301(p):
    y0, y1, x0, x1 = p["y0"], p["y1"], p["x0"], p["x1"]
    top, bottom, left, right = p["box"]
    height, width = 6, 8
    cells = [(y, x) for y in range(height) for x in range(width)
             if top <= y < bottom and left <= x < right and y0 <= y < y1 and x0 <= x < x1]
    cx = sum(x - x0 for _, x in cells) / len(cells) + x0
    cy = sum(y - y0 for y, _ in cells) / len(cells) + y0
    return [_shape_text((y1 - y0, x1 - x0)), "(%s, %s)" % (_half(cx), _half(cy))]


def apc_g401(p):
    rows = []
    for (px, py), (nx, ny), ok in zip(p["prev"], p["next"], p["status"]):
        if ok == 1:
            rows.append("[%d, %d]" % (nx - px, ny - py))
    return ["[" + ", ".join(rows) + "]"]


def apc_g402(p):
    kept = sum(1 for s in p["status"] if s == 1)
    return ["(%d, 2)" % kept] if p["form"] == 0 else ["(%d, 1, 2)" % kept]
