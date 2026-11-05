# -*- coding: utf-8 -*-
"""「세 수준으로 다시 보기」 블록 그림의 도우미. 크기(화면 520×280, 파일 1040×560), 글자 크기(22 이상), 여백을 고정한 함수 셋이
matplotlib Figure 를 돌려줌. 작가의 lNN.py 가 블록마다 수준을 인자로 받는 함수 하나에서 이 도우미를 부르고, 그림 이름마다 얇은 함수로
등록함(그 스크립트 방식대로 FIGS 나 @figure("4b-31", *SIZE)).

  chain   7살. 상자와 화살표 한 줄. 칸마다 숫자, 이름표는 넷 이하, 식 글자와 코드 글꼴을 쓰지 않음
  grid    15살·20살. 괄호 없는 숫자 칸 표, 강조 칸 한 색, 위에 식 한 줄(15살)이나 코드 줄 이름(20살, code=True)
  graph   15살. 좌표 그래프, 축 이름, 위에 식 한 줄. 다 그린 뒤 글이 그림 밖으로 나가면 ValueError

색은 ai_art.COLORS 의 이름(blue, orange …)으로 받고 옅은 칠은 PALE 을 씀. 둘 다 ai_art.FIXED 에 있어 팔레트로 줄여도 값이 그대로임.
그림에 찍는 숫자는 부르는 쪽이 계산하고 assert 함(ai_art.fmt 로 빼기표를 U+2212 로 씀). matplotlib 는 함수 안에서 import 해서
CI 가 이 파일을 import 해도 matplotlib 를 찾지 않음.
"""
from tools.ai_art import COLORS, SCALE

SIZE = (520, 280)  # 화면 논리 크기. 파일은 SCALE 배
FONT = 22  # matplotlib 글자 크기 하한. dpi 100·SCALE 2 에서 화면 약 15px
BIG = 28  # 상자 안 숫자
PAD = 24  # 그림 가장자리 여백(논리 px)
PALE = {"blue": "#dbeafe", "orange": "#ffedd5", "green": "#d1fae5", "purple": "#ede9fe", "red": "#fee2e2", "gray": "#f3f4f6",
        "highlight": COLORS["highlight"]}
CODE_FONT = ["D2Coding", "DejaVu Sans Mono"]
MATH_FONT = ["DejaVu Sans", "NanumGothic"]  # 나눔고딕의 ²·√ 글리프가 작아 식 줄은 DejaVu 로 쓰고 한글만 나눔고딕으로 씀


def _canvas():
    """(Figure, Axes). Axes 는 그림 전체를 덮고 좌표는 논리 px(왼쪽 아래 0, 0)."""
    from tools.ai_art import setup
    plt = setup()
    width, height = SIZE
    fig = plt.figure(figsize=(width * SCALE / 100.0, height * SCALE / 100.0), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def _color(name, default="ink"):
    return COLORS.get(name or default, name)


def _width(fig, text, size=FONT, code=False, bold=False):
    """글 한 줄이 그림에서 차지하는 폭(논리 px)."""
    piece = fig.text(0, 0, str(text), fontsize=size, family=CODE_FONT if code is True else (code or None), weight="bold" if bold else "normal")
    width = piece.get_window_extent(fig.canvas.get_renderer()).width / float(SCALE)
    piece.remove()
    return width


def _top(ax, text, code=False):
    if text:
        ax.text(SIZE[0] / 2.0, SIZE[1] - PAD - 4, text, ha="center", va="top", fontsize=FONT, color=COLORS["ink"],
                family=CODE_FONT if code else MATH_FONT)


def chain(values, labels=(), arrows=(), mark=None, color="blue", note=""):
    """7살 그림. values 는 왼쪽부터 상자에 넣는 글(숫자, 넷 이하), labels 는 상자 위 이름표(없으면 빈 글), arrows 는 화살표 위
    글(상자 수보다 하나 적음), mark 는 강조할 상자 번호(0부터), color 는 강조 색 이름, note 는 아래 한 줄."""
    if not 1 <= len(values) <= 4:
        raise ValueError("chain 의 상자는 1~4개여야 합니다: %d" % len(values))
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig, ax = _canvas()
    count = len(values)
    gap = max([56.0] + [_width(fig, text) + 16 for text in arrows if text])
    width = (SIZE[0] - 2 * PAD - gap * (count - 1)) / float(count)
    for text in list(values):
        if _width(fig, text, BIG, bold=True) > width - 16:
            raise ValueError("chain 상자 글 %r 가 상자 폭 %.0f 를 넘습니다." % (text, width))
    for text in list(labels) + [note]:
        if text and _width(fig, text) > (width + gap - 8 if text != note else SIZE[0] - 2 * PAD):
            raise ValueError("chain 이름표 %r 가 자리를 넘습니다." % text)
    height, middle = 84, SIZE[1] / 2.0 + (10 if note else 0)
    for n, value in enumerate(values):
        left = PAD + n * (width + gap)
        marked = n == mark
        ax.add_patch(FancyBboxPatch((left, middle - height / 2), width, height, boxstyle="round,pad=0,rounding_size=12",
                                    fc=PALE.get(color, PALE["highlight"]) if marked else "white",
                                    ec=_color(color) if marked else COLORS["muted"], lw=3 if marked else 2))
        ax.text(left + width / 2, middle, str(value), ha="center", va="center", fontsize=BIG, color=COLORS["ink"],
                weight="bold" if marked else "normal")
        label = labels[n] if n < len(labels) else ""
        if label:
            ax.text(left + width / 2, middle + height / 2 + 12, label, ha="center", va="bottom", fontsize=FONT, color=COLORS["muted"])
        if n < count - 1:
            start, end = left + width + 6, left + width + gap - 6
            ax.add_patch(FancyArrowPatch((start, middle), (end, middle), arrowstyle="-|>", mutation_scale=22, lw=2.5,
                                         color=COLORS["ink"]))
            text = arrows[n] if n < len(arrows) else ""
            if text:
                ax.text((start + end) / 2, middle + 10, text, ha="center", va="bottom", fontsize=FONT, color=COLORS["muted"])
    if note:
        ax.text(SIZE[0] / 2.0, PAD, note, ha="center", va="bottom", fontsize=FONT, color=COLORS["ink"])
    return fig


def grid(rows, col_names=(), row_names=(), marks=(), color="orange", top="", code=False):
    """15살·20살 그림. rows 는 행마다 칸 글을 담은 목록(괄호 없는 숫자 칸), col_names 는 열 머리, row_names 는 행 머리, marks 는 강조할
    (행, 열) 목록(0부터, 머리 빼고), color 는 강조 색 이름, top 은 표 위 한 줄(15살 식, 20살 코드 줄 이름이면 code=True)."""
    if not rows or len({len(r) for r in rows}) != 1:
        raise ValueError("grid 의 행은 비지 않고 칸 수가 같아야 합니다.")
    from matplotlib.patches import Rectangle
    fig, ax = _canvas()
    _top(ax, top, code)
    head_rows = 1 if col_names else 0
    head_cols = 1 if row_names else 0
    total_rows = len(rows) + head_rows
    if total_rows > 7:
        raise ValueError("grid 는 머리를 넣어 7행 이하여야 글자가 22 크기로 들어갑니다: %d행" % total_rows)
    if top and _width(fig, top, code=True if code else MATH_FONT) > SIZE[0] - 2 * PAD:
        raise ValueError("grid 위 글 %r 가 그림 폭을 넘습니다." % top)
    top_space = 56 if top else 0
    room_h = SIZE[1] - 2 * PAD - top_space
    cell_h = min(56.0, room_h / total_rows)
    head_w = max([_width(fig, name) + 28 for name in row_names] + [72.0]) if head_cols else 0
    widths = []
    for c in range(len(rows[0])):
        texts = [(row[c], code) for row in rows] + ([(col_names[c], False)] if c < len(col_names) else [])
        widths.append(max([_width(fig, text, code=mono, bold=True) + 28 for text, mono in texts] + [72.0]))
    table_w = head_w + sum(widths)
    if table_w > SIZE[0] - 2 * PAD:
        raise ValueError("grid 표 폭 %.0f 가 그림 폭 %d 를 넘습니다. 칸 글을 줄이세요." % (table_w, SIZE[0] - 2 * PAD))
    left = (SIZE[0] - table_w) / 2.0
    upper = PAD + (room_h + cell_h * total_rows) / 2.0
    marked = {tuple(m) for m in marks}

    def cell(r, c, text, fill, bold=False, tone="ink"):
        x = left + (head_w + sum(widths[:c]) if c >= 0 else 0)
        y = upper - (r + 1) * cell_h
        w = head_w if c < 0 else widths[c]
        ax.add_patch(Rectangle((x, y), w, cell_h, fc=fill, ec=COLORS["faint"], lw=1.5))
        ax.text(x + w / 2, y + cell_h / 2, str(text), ha="center", va="center", fontsize=FONT, color=COLORS[tone],
                weight="bold" if bold else "normal", family=CODE_FONT if code and c >= 0 and r >= head_rows else None)

    for c, name in enumerate(col_names):
        cell(0, c, name, PALE["gray"], tone="muted")
    for r, row in enumerate(rows):
        if head_cols:
            cell(r + head_rows, -1, row_names[r] if r < len(row_names) else "", PALE["gray"], tone="muted")
        for c, text in enumerate(row):
            hit = (r, c) in marked
            cell(r + head_rows, c, text, PALE.get(color, PALE["highlight"]) if hit else "white", bold=hit)
    return fig


def graph(xs, series, xlabel, ylabel, top="", marks=(), xlim=None, ylim=None):
    """15살 그림. series 는 [(ys, 색 이름, 이름표)] 이고 이름표가 있으면 선 끝에 적음. marks 는 [(x, y, 글, 색 이름)] 점,
    top 은 그래프 위 식 한 줄. 축 이름은 꼭 줌."""
    from tools.ai_art import setup
    plt = setup()
    width, height = SIZE
    fig = plt.figure(figsize=(width * SCALE / 100.0, height * SCALE / 100.0), dpi=100)
    top_space = 0.16 if top else 0.05
    ax = fig.add_axes([0.17, 0.22, 0.76, 0.73 - top_space])
    for ys, name, label in series:
        ax.plot(xs, ys, color=_color(name), lw=3)
        if label:
            ax.text(xs[-1], ys[-1], " " + label, ha="left", va="center", fontsize=FONT, color=_color(name))
    for x, y, text, name in marks:
        ax.plot([x], [y], "o", ms=12, color=_color(name))
        if text:
            ax.annotate(text, (x, y), xytext=(0, 14), textcoords="offset points", ha="center", va="bottom", fontsize=FONT,
                        color=_color(name))
    if xlim:
        ax.set_xlim(*xlim)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel, fontsize=FONT, color=COLORS["ink"])
    ax.set_ylabel(ylabel, fontsize=FONT, color=COLORS["ink"], labelpad=12)
    ax.tick_params(labelsize=FONT, colors=COLORS["muted"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, color=COLORS["grid"], lw=1.2)
    ax.set_axisbelow(True)
    if top:
        fig.text(0.5, 0.96, top, ha="center", va="top", fontsize=FONT, color=COLORS["ink"], family=MATH_FONT)
    _inside(fig)
    return fig


def _inside(fig):
    """그림 밖으로 나간 글이 있으면 ValueError. 축 이름, 선 이름표, 점 글, 위 식 줄은 글마다, 눈금 글은 축 전체 테두리로 봄."""
    fig.draw_without_rendering()  # 축 이름과 눈금 글 자리는 그릴 때 정해짐
    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height

    def out(box):
        return box.x0 < 0 or box.y0 < 0 or box.x1 > width or box.y1 > height

    for ax in fig.axes:
        for text in [ax.xaxis.label, ax.yaxis.label] + list(ax.texts):
            if text.get_text().strip() and out(text.get_window_extent(renderer)):
                raise ValueError("graph 글 %r 가 그림 밖으로 나갑니다. 글을 줄이세요." % text.get_text())
        if out(ax.get_tightbbox(renderer)):
            raise ValueError("graph 눈금 글이 그림 밖으로 나갑니다. xlim·ylim 이나 값을 줄이세요.")
    for text in fig.texts:
        if out(text.get_window_extent(renderer)):
            raise ValueError("graph 위 글 %r 가 그림 밖으로 나갑니다. 글을 줄이세요." % text.get_text())
