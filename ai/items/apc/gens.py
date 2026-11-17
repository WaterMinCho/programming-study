"""응용 코딩 실습(apc)의 결과 예측 문항. 작은 입력의 숫자를 바꿔 모양·값·좌표를 물음."""
from aiprep.gen import Retry, blank, gen


# a18a 단원의 생성 문항
@gen("apc-g101", unit="a18a", level=2, tags=["입력 준비", "슬라이스"],
     ref=["응용 1차시 노트북 06 [17]", "NumPy 문서 Indexing on ndarrays"],
     facts=["FA18-103"], basis="lecture-example", step="a18a/5",
     family="apc-crop-shape", core=False, prio=2)
def crop_shape(r):
    """사진 크기, 왼쪽 위 점, 영역 크기를 바꿔 검사 없이 자른 배열의 shape 를 물음.

    영역이 사진 밖으로 나가는 경우를 주로 내어 슬라이스가 축 끝까지만 고르는 것을 보임.
    점 (x, y) 와 [행, 열] 순서는 차시 문항이 이미 물었으므로 인덱스 순서는 바꾸지 않음.
    """
    rows, cols = r.int(6, 10), r.int(9, 14)
    left, top = r.int(1, cols - 3), r.int(1, rows - 2)
    w, h = r.int(2, cols - left + 4), r.int(2, rows - top + 4)
    got_rows = min(top + h, rows) - top
    got_cols = min(left + w, cols) - left
    row_cut, col_cut = top + h > rows, left + w > cols
    if not (row_cut or col_cut) and r.chance(0.7):
        raise Retry()  # 영역이 사진 안에 있는 경우는 답이 (h, w, 3) 이라 드물게만 냄
    if (rows, cols, left, top, w, h) in ((8, 12, 3, 2, 4, 8), (8, 12, 2, 3, 8, 4)):
        raise Retry()  # a18a 의 짐작 문항 image[2:10, 3:7] 과 본문 예 image[3:7, 2:10] 은 내지 않음
    shape = (got_rows, got_cols, 3)
    stem = (f"`image.shape`는 ({rows}, {cols}, 3)입니다. 왼쪽 위 점은 (left, top) = ({left}, {top}), "
            f"너비 w는 {w}, 높이 h는 {h}입니다. 크기 검사 없이 아래 줄로 잘랐습니다.\n\n"
            "```python\nx = image[top:top + h, left:left + w]\n```\n\n"
            "`x.shape`는 ____ 입니다.")
    explain = f"행 범위는 {top}:{top + h}, 열 범위는 {left}:{left + w}입니다. "
    cut = []
    if row_cut:
        cut.append(f"행은 {rows - 1}번까지만 있어 {top}~{rows - 1}행의 {got_rows}개만 남습니다")
    if col_cut:
        cut.append(f"열은 {cols - 1}번까지만 있어 {left}~{cols - 1}열의 {got_cols}개만 남습니다")
    if cut:
        explain += "슬라이스는 끝 위치가 축 길이보다 커도 오류를 내지 않습니다. " + ". ".join(cut) + ". "
    else:
        explain += f"영역이 사진 안에 있어 {h}행, {w}열을 그대로 고릅니다. "
    explain += f"그래서 `x.shape`는 {shape}입니다."
    return blank(stem, [{"answer": [str(shape)], "mode": "shape"}], explain,
                 params={"rows": rows, "cols": cols, "left": left, "top": top, "w": w, "h": h})


crop_shape.gen_spec.meta.update(template_revision="crop-shape-3", author_difficulty=2,
                                display_params=["rows", "cols", "left", "top", "w", "h"])


@gen("apc-g102", unit="a18a", level=2, tags=["입력 준비", "축 순서"],
     ref=["응용 1차시 노트북 01 [20]", "NumPy 문서 numpy.transpose"],
     facts=["FA18-110"], basis="lecture-example", step="a18a/4",
     family="apc-chw-values", core=False, prio=2)
def chw_values(r):
    """작은 RGB 배열의 값을 바꿔 transpose(2, 0, 1) 뒤 한 채널의 값과 한 픽셀의 세 값을 물음."""
    height, width = 2, r.pick([2, 3])
    levels = [0, 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 255]
    picked = [r.pick(levels) for _ in range(height * width * 3)]
    rgb = [[picked[(i * width + j) * 3:(i * width + j) * 3 + 3] for j in range(width)] for i in range(height)]
    channel = r.int(0, 2)
    row, col = r.int(0, height - 1), r.int(0, width - 1)
    plane = [[rgb[i][j][channel] for j in range(width)] for i in range(height)]
    pixel = rgb[row][col]
    names = ["R", "G", "B"]
    stem = (f"`x`는 RGB 순서의 uint8 배열이고 `x.shape`는 ({height}, {width}, 3)입니다.\n\n"
            f"```python\nx = np.array({rgb}, dtype=np.uint8)\nx = x.transpose(2, 0, 1)\n```\n\n"
            f"`x[{channel}]`의 값은 ____ 이고 `x[:, {row}, {col}]`의 값은 ____ 입니다. 각 칸에 배열 값만 쓰세요. 예: [1, 2, 3].")
    explain = (f"`transpose(2, 0, 1)`이 채널 축을 맨 앞으로 옮깁니다. 모양은 (3, {height}, {width})입니다. "
               f"인덱스도 [채널, 행, 열] 순서가 됩니다. `x[{channel}]`의 값은 픽셀마다 {names[channel]} 값만 모은 배열 "
               f"{plane}입니다. `x[:, {row}, {col}]`의 값은 {row}행 {col}열 픽셀의 세 값 {pixel}입니다. "
               f"축을 옮기기 전에는 같은 세 값을 `x[{row}, {col}]`에서 읽었습니다.")
    return blank(stem, [{"answer": [str(plane)], "mode": "values"},
                        {"answer": [str(pixel)], "mode": "values"}],
                 explain, params={"rgb": rgb, "channel": channel, "row": row, "col": col})


chw_values.gen_spec.meta.update(template_revision="chw-values-1", author_difficulty=2,
                                display_params=["rgb", "channel", "row", "col"])



# a18b 단원의 생성 문항
TEMPLATE_REVISION = "a18b-nonzero-3"


def _grid_text(rows):
    """2차원 리스트를 코드 블록 안의 배열 글로 바꿈."""
    body = ",\n".join("    [" + ", ".join("%3d" % v for v in row) + "]" for row in rows)
    return "[\n" + body + "]"


@gen("apc-g201", unit="a18b", level=2, tags=["색 범위 남기기", "행과 열"],
     ref=["응용 1차시 노트북 03 [5]", "NumPy 문서 numpy.nonzero"],
     facts=["FA18-207"], basis="lecture-example", step="a18b/4",
     family="apc-nonzero-predict", core=False, prio=2)
def nonzero_spots(r):
    """흩어진 255 칸 세 개의 xs[0], left, bottom 을 계산함. xs[0] 은 행 순서로 처음 나오는 칸의 열 번호임."""
    height, width = r.pick([5, 6, 7]), r.pick([7, 8, 9, 10])
    left = r.int(0, width - 3)
    # 맨 아래 행을 bottom 으로 찍어 맞히는 일이 잦지 않게 대개 한 행 위에서 끝냄
    last = height - 1 if r.chance(0.3) else height - 2
    first_y = r.int(0, last - 2)
    bottom = r.int(first_y + 2, last)
    # 넷 가운데 셋은 처음 나오는 칸이 가장 왼쪽 칸이 아니게 둬서 xs[0] 과 left 를 구분하게 함
    if r.chance(0.75):
        first_x = r.int(left + 1, width - 1)
        spots = {(first_y, first_x), (r.int(first_y + 1, bottom), left)}
    else:
        first_x = left
        spots = {(first_y, first_x)}
    spots.add((bottom, r.int(left, width - 1)))
    while len(spots) < 3:
        y, x = r.int(first_y, bottom), r.int(left, width - 1)
        if y > first_y or x > first_x:
            spots.add((y, x))
    rows = [[0] * width for _ in range(height)]
    for y, x in spots:
        rows[y][x] = 255
    ordered = sorted(spots)
    stem = ("`mask`는 높이 %d·너비 %d인 0·255 uint8 배열입니다. 그 값은 아래 코드의 `np.array` 문장에 적었습니다.\n\n"
            "```python\nmask = np.array(%s, dtype=np.uint8)\n"
            "ys, xs = np.nonzero(mask)\n"
            "left, right = int(xs.min()), int(xs.max())\n"
            "top, bottom = int(ys.min()), int(ys.max())\n```\n\n"
            "`xs[0]`은 ____ 이고 `left`는 ____ 입니다. `bottom`은 ____ 입니다.") % (height, width, _grid_text(rows))
    explain = ("`np.nonzero`는 행 번호 `ys`를 먼저, 열 번호 `xs`를 다음에 돌려줍니다. 번호는 0행부터 행 순서로 나오므로 "
               "`xs[0]`은 255가 처음 나오는 %d행에서 가장 왼쪽 칸의 열 번호 %d입니다. "
               "`left`는 가장 작은 열 번호 %d이고 `bottom`은 가장 큰 행 번호 %d입니다.") % (first_y, first_x, left, bottom)
    return blank(stem, [{"answer": [str(first_x)], "mode": "number"},
                        {"answer": [str(left)], "mode": "number"},
                        {"answer": [str(bottom)], "mode": "number"}],
                 explain, params={"size": [height, width], "spots": [[y, x] for y, x in ordered]})


nonzero_spots.gen_spec.meta.update(template_revision=TEMPLATE_REVISION, author_difficulty=2,
                                   display_params=["size", "spots"])



# a18c 단원의 생성 문항
GRID_H, GRID_W = 6, 8
DARK, BRIGHT = 40, 230


def _num(value):
    """정수로 떨어지면 소수점을 떼고 아니면 소수 한 자리로 적음."""
    return str(int(value)) if value == int(value) else "%.1f" % value


@gen("apc-g301", unit="a18c", level=2, tags=["프레임 중심 기록"],
     ref=["응용 3차시 노트북 02 [7]", "NumPy 문서 indexing"],
     facts=["FA18-302", "FA18-303", "FA18-306"], basis="lecture-formula", step="a18c/4",
     family="apc-g-grid", core=False, prio=2)
def grid_center(r):
    """밝은 직사각형 일부가 영역 밖으로 나간 격자에서 roi 모양과 255 칸 중심의 원본 좌표를 구함."""
    y0 = r.int(1, 2)
    y1 = r.int(y0 + 3, GRID_H)
    x0 = r.int(1, 3)
    x1 = r.int(x0 + 3, GRID_W)
    top = r.int(0, GRID_H - 2)
    left = r.int(0, GRID_W - 2)
    bottom = top + r.int(2, 3)
    right = left + r.int(2, 3)
    rows = [y for y in range(top, min(bottom, GRID_H)) if y0 <= y < y1]
    cols = [x for x in range(left, min(right, GRID_W)) if x0 <= x < x1]
    if not rows or not cols:
        raise Retry()
    full_rows = [y for y in range(top, min(bottom, GRID_H))]
    full_cols = [x for x in range(left, min(right, GRID_W))]
    if rows == full_rows and cols == full_cols:
        raise Retry()
    # x 와 y, 행과 열을 바꿔 써도 같은 답이 나오는 문항은 내지 않음
    if y1 - y0 == x1 - x0:
        raise Retry()
    grid = [[BRIGHT if (top <= y < bottom and left <= x < right) else DARK for x in range(GRID_W)]
            for y in range(GRID_H)]
    shape = (y1 - y0, x1 - x0)
    inner_x = sum(x - x0 for x in cols) / float(len(cols))
    inner_y = sum(y - y0 for y in rows) / float(len(rows))
    cx, cy = inner_x + x0, inner_y + y0
    if cx == cy:
        raise Retry()
    literal = ",\n                  ".join(str(row) for row in grid)
    code = ("frame = np.array([%s], dtype=np.uint8)\n" % literal
            + "roi = frame[%d:%d, %d:%d]\n" % (y0, y1, x0, x1)
            + "level, binary = cv2.threshold(roi, 200, 255, cv2.THRESH_BINARY)")
    stem = ("frame은 높이 %d·너비 %d인 회색조 영상입니다. 밝기 %d인 어두운 배경에 밝기 %d인 직사각형이 있습니다. "
            "binary에서 값이 255인 칸의 열 번호 평균을 x, 행 번호 평균을 y로 두어 roi 안의 중심을 구하고, "
            "이 중심을 원본 좌표 (x, y)로 옮깁니다.\n\n"
            "```python\n%s\n```\n\n"
            "roi.shape는 ____ 이고, 중심의 원본 좌표 (x, y)는 ____ 입니다." % (GRID_H, GRID_W, DARK, BRIGHT, code))
    explain = ("`roi = frame[%d:%d, %d:%d]` 줄은 %d행부터 %d행까지, %d열부터 %d열까지를 고르므로 roi.shape는 (%d, %d)입니다. "
               "밝기 %d은 기준 200보다 커서 255가 되고 %d은 0이 됩니다. "
               "roi 안에 남은 직사각형 칸은 원본의 %s행, %s열입니다. "
               "roi 안의 중심은 (%s, %s)입니다. x에는 시작 열 x0, y에는 시작 행 y0을 더합니다. x0 = %d, y0 = %d이므로 원본 좌표는 (%s, %s)입니다."
               % (y0, y1, x0, x1, y0, y1 - 1, x0, x1 - 1, shape[0], shape[1], BRIGHT, DARK,
                  "·".join(map(str, rows)), "·".join(map(str, cols)),
                  _num(inner_x), _num(inner_y), x0, y0, _num(cx), _num(cy)))
    answer_center = "(%s, %s)" % (_num(cx), _num(cy))
    return blank(stem,
                 [{"answer": ["(%d, %d)" % shape], "mode": "shape"},
                  {"answer": [answer_center], "mode": "values"}],
                 explain,
                 params={"y0": y0, "y1": y1, "x0": x0, "x1": x1,
                         "box": [top, bottom, left, right]})


grid_center.gen_spec.meta.update(template_revision="roi-grid-center-1", author_difficulty=2,
                                 display_params=["y0", "y1", "x0", "x1", "box"])



# a18d 단원의 생성 문항
REF = ["응용 4차시 노트북 06 [6]", "문서 numpy indexing"]


def _points(r):
    """성공한 점이 3개 이상이 되도록 점 좌표와 status 를 만듦."""
    count = r.int(4, 5)
    fail = r.sample(range(count), r.int(1, count - 3))
    prev, nxt, status = [], [], []
    for i in range(count):
        x, y = r.int(20, 300), r.int(20, 220)
        prev.append((x, y))
        if i in fail:
            nxt.append((r.int(0, 319), r.int(0, 239)))
            status.append(0)
        else:
            dx, dy = r.pick([-4, -3, -2, -1, 1, 2, 3, 4]), r.pick([-4, -3, -2, -1, 0, 1, 2, 3, 4])
            nxt.append((x + dx, y + dy))
            status.append(1)
    return prev, nxt, status


def _rows(points):
    return "[" + ", ".join("[%d, %d]" % p for p in points) + "]"


def _coords(points):
    return ", ".join("(%d, %d)" % p for p in points)


def _status(status):
    return "[" + ", ".join("[%d]" % s for s in status) + "]"


@gen("apc-g401", unit="a18d", level=2, tags=["특징점 변위"], ref=REF,
     facts=["FA18-404", "FA18-405", "FA18-407"], basis="lecture-formula", step="a18d/4", family="apc-moves-values")
def kept_moves(r):
    """status 가 1인 점만 같은 조건으로 골라 현재 좌표에서 이전 좌표를 뺀 moves 를 계산함."""
    prev, nxt, status = _points(r)
    kept = [i for i, s in enumerate(status) if s == 1]
    moves = [(nxt[i][0] - prev[i][0], nxt[i][1] - prev[i][1]) for i in kept]
    lost = [i for i, s in enumerate(status) if s == 0]
    return blank(
        stem=("점 %d개의 좌표를 (x, y)로 0번 점부터 차례로 적었습니다. 이전 좌표는 %s, 현재 좌표는 %s이고 status는 %s입니다. "
              "`keep = status.ravel() == 1`로 고른 `old_ok`와 `new_ok`를 `reshape(-1, 2)`로 (K, 2) 배열로 만들고 "
              "`moves = new_ok - old_ok`를 구하면 `moves`는 ____ 입니다." % (len(prev), _coords(prev), _coords(nxt), _status(status))),
        blanks=[{"answer": [_rows(moves)], "mode": "values"}],
        explain=("status가 1인 %s번 점만 남습니다. 남은 점마다 현재 좌표에서 이전 좌표를 빼면 %s입니다. "
                 "status가 0인 %s번 점은 두 배열에서 함께 빠집니다."
                 % (", ".join(map(str, kept)), _rows(moves), ", ".join(map(str, lost)))),
        params={"prev": prev, "next": nxt, "status": status})


@gen("apc-g402", unit="a18d", level=2, tags=["특징점 변위"], ref=["응용 4차시 노트북 06 [6]", "문서 numpy indexing"],
     facts=["FA18-404"], basis="lecture-formula", step="a18d/6", family="apc-mask-shape")
def mask_shape(r):
    """(N, 1, 2) 배열을 (N, 1) 마스크나 펴서 만든 길이 N 마스크로 고른 결과의 shape 를 계산함."""
    count = r.int(4, 7)
    kept = r.int(1, count - 1)
    ok = set(r.sample(range(count), kept))
    status = [1 if i in ok else 0 for i in range(count)]
    form = r.pick([0, 1])
    if (count, status, form) == (4, [1, 1, 0, 1], 0):
        raise Retry()  # a18d 의 짐작 문항 prev_pts[status == 1] 과 같은 문항은 내지 않음
    if form == 0:
        expr, shape = "prev_pts[status == 1]", "(%d, 2)" % kept
        why = ("status == 1은 (%d, 1) True·False 배열이라 prev_pts의 0번 축과 1번 축을 함께 고릅니다. "
               "True인 %d개가 남고 마지막 축 2가 붙어 %s입니다." % (count, kept, shape))
    else:
        expr, shape = "prev_pts[status.ravel() == 1]", "(%d, 1, 2)" % kept
        why = ("status.ravel() == 1은 길이 %d인 True·False 배열이라 prev_pts의 0번 축만 고릅니다. "
               "True인 %d개가 남고 뒤의 두 축 (1, 2)가 붙어 %s입니다." % (count, kept, shape))
    return blank(
        stem=("prev_pts는 점 %d개의 좌표를 담은 float32 (%d, 1, 2) 배열이고 status는 %s인 (%d, 1) 배열입니다. "
              "%s의 shape는 ____ 입니다." % (count, count, _status(status), count, expr)),
        blanks=[{"answer": [shape], "mode": "shape"}],
        explain=why,
        params={"count": count, "status": status, "form": form})


kept_moves.gen_spec.meta.update(template_revision="kept-moves-3", author_difficulty=2, display_params=["prev", "next", "status"])
mask_shape.gen_spec.meta.update(template_revision="mask-shape-2", author_difficulty=2, display_params=["count", "status", "form"])
