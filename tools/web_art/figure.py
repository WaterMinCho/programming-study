# -*- coding: utf-8 -*-
"""페이지·미션 그림 스크립트가 같이 쓰는 도우미. Pillow 가 필요하므로 출제자 컴퓨터에서만 import 함.

스크립트는 이렇게 씀:

    from tools.web_art.figure import figure, main

    @figure("3a-1", 560, 240)
    def race(fig):
        c = fig.frame(1400)
        ...

    if __name__ == "__main__":
        sys.exit(main(sys.modules[__name__], "web/learn/l03/assets", owner="l03"))

WebFigure 는 draw.Figure 와 같되 이름 검사만 웹 규칙(l01-1, 3a-1, w03-1)으로 함. main() 은 journey_art/render.py 와 같은
명령줄(그림 이름 고르기, --check, --out DIR)을 주고, owner 를 적으면 그 페이지·미션의 그림만 그리게 이름 앞부분을 확인함.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.journey_art import draw, render  # noqa: E402
from tools.journey_art.draw import figure  # noqa: E402,F401
from tools.web_art import LIMITS, NAMES, name_kind, owner_of  # noqa: E402

USAGE = "쓰는 법: python3 %s [그림 이름...] [--check] [--out DIR]"


class WebFigure(draw.Figure):
    """웹 트랙 그림. 이름이 l01-1, 3a-1, w03-1 가운데 하나의 꼴이어야 하고 나머지는 draw.Figure 와 같음."""

    def __init__(self, name, width, height):
        if name_kind(name) is None:
            raise ValueError("그림 이름은 %s 꼴이어야 합니다: %r" % (", ".join("l01-1 3a-1 w03-1".split()), name))
        if width > LIMITS["width"]:
            raise ValueError("논리 폭은 %dpx 이하여야 합니다: %s 가 %dpx" % (LIMITS["width"], name, width))
        self.name, self.width, self.height = name, width, height
        self.frames, self.durations = [], []


def belongs(name, owner, sections=()):
    """그림 이름이 owner(페이지 id, 미션 id)의 것인지. 페이지는 l03-1 꼴이거나 그 페이지 절(sections, 예 "3a")의 3a-1 꼴."""
    found = owner_of(name)
    if found is None:
        return False
    kind, head = found
    if kind == "section":
        return head in sections
    return head == owner


def render_module(module, out_dir, names=None, check=False, owner=None, sections=()):
    """모듈의 @figure 함수를 그려 out_dir 에 쓰고 render.inspect 결과 줄 목록을 돌려줌. owner 가 있으면 이름이 그 페이지·미션의
    것인지도 봄."""
    found = draw.figures(module)
    known = [item[0] for item in found]
    for name in names or []:
        if name not in known:
            raise ValueError("그림 %s 가 없습니다. 있는 것: %s" % (name, ", ".join(known) or "없음"))
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for name, width, height, fn in found:
        if names and name not in names:
            continue
        fig = WebFigure(name, width, height)
        fn(fig)
        path = fig.save(out_dir)
        row = render.inspect(path, check)
        if owner and not belongs(name, owner, sections):
            row["problems"].insert(0, "이름이 %s 의 그림 규칙에 맞지 않습니다" % owner)
        row.update(name=name, path=path)
        rows.append(row)
    return rows


def main(module, default_out, argv=None, owner=None, sections=()):
    """스크립트의 명령줄. 그림 이름을 적으면 그것만, --check 면 밝은 면과 팔레트까지, --out DIR 이면 다른 폴더에 씀."""
    args = list(sys.argv[1:] if argv is None else argv)
    script = os.path.basename(getattr(module, "__file__", "figure.py"))
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out_dir = os.path.join(ROOT, default_out) if not os.path.isabs(default_out) else default_out
    if "--out" in args:
        at = args.index("--out")
        if at + 1 >= len(args):
            print(USAGE % script)
            return 2
        out_dir = os.path.abspath(args[at + 1])
        del args[at:at + 2]
    if any(a.startswith("-") for a in args):
        print(USAGE % script)
        return 2
    try:
        rows = render_module(module, out_dir, args, check, owner, sections)
    except ValueError as error:
        print(error)
        return 1
    print("쓴 폴더: %s" % out_dir)
    return 1 if render.report(rows, out_dir) else 0


__all__ = ["WebFigure", "figure", "belongs", "render_module", "main", "NAMES", "LIMITS"]
