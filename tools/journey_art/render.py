#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""던전 그림 스크립트를 돌려 dungeons/<던전>/assets/ 에 GIF·PNG 를 씀. 출제자 컴퓨터에서만 돌고 Pillow 가 필요함.

  python3 tools/journey_art/render.py d01                tools/journey_art/d01.py 의 @figure 함수를 모두 그림
  python3 tools/journey_art/render.py d01 1-1a 1-2b      이름을 적은 그림만
  python3 tools/journey_art/render.py d01 --check        쓴 파일을 다시 읽어 밝은 면과 팔레트까지 확인
  python3 tools/journey_art/render.py sample --out DIR   저장소 밖 폴더에 씀(sample.py 의 기준 그림)

파일마다 종류·프레임 수·크기를 표로 찍고 LIMITS 의 한도(GIF 300KB, PNG 200KB, 프레임 12개, 프레임 800~2500ms,
논리 폭 560px, 던전 assets 합계 2.5MB)를 넘으면 1 로 끝남. tools/verify_journey.py 가 같은 한도를 봄.
"""
import importlib
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.journey_art import KB, LIMITS, SCALE  # noqa: E402
from tools.journey_art import draw  # noqa: E402
from PIL import Image  # noqa: E402

DUNGEON = re.compile(r"^d(\d\d)$")
USAGE = "쓰는 법: python3 tools/journey_art/render.py <d01 | sample> [그림 이름...] [--check] [--out DIR]"


def assets_dir(dungeon):
    return os.path.join(ROOT, "dungeons", dungeon, "assets")


def name_prefix(module_name):
    """d01 → "1-". 던전 스크립트가 아니면 None(이름의 앞부분을 확인하지 않음)."""
    m = DUNGEON.match(module_name.rsplit(".", 1)[-1])
    return "%d-" % int(m.group(1)) if m else None


def inspect(path, check=False):
    """쓴 파일을 다시 읽어 프레임 수·시간·크기를 재고 한도를 넘은 곳을 문구로 모음. check 면 밝은 면과 팔레트도 봄."""
    kind = os.path.splitext(path)[1][1:]
    size = os.path.getsize(path)
    problems, durations, frames = [], [], 0
    with Image.open(path) as im:
        width, height = im.size
        frames = getattr(im, "n_frames", 1)
        for i in range(frames):
            im.seek(i)
            if kind == "gif":
                durations.append(im.info.get("duration", 0))
            if check:
                if draw.bright_runs(im) > 0:
                    problems.append("%d번 프레임에 밝은 면이 있습니다(어두운 테마 화면 검사에 걸립니다)" % (i + 1))
                outside = draw.outside_palette(im)
                if outside:
                    problems.append("%d번 프레임에 팔레트 밖의 색이 %d개 있습니다" % (i + 1, len(outside)))
    limit = LIMITS["%s_bytes" % kind]
    if size > limit:
        problems.append("크기가 %.1fKB 입니다(한도 %dKB)" % (size / KB, limit // KB))
    if frames > LIMITS["frames"]:
        problems.append("프레임이 %d개입니다(한도 %d개)" % (frames, LIMITS["frames"]))
    bad_ms = [ms for ms in durations if not LIMITS["ms_min"] <= ms <= LIMITS["ms_max"]]
    if bad_ms:
        problems.append("프레임 시간 %s 가 %d~%dms 를 벗어납니다" % (", ".join("%dms" % ms for ms in bad_ms), LIMITS["ms_min"], LIMITS["ms_max"]))
    if width > LIMITS["width"] * SCALE:
        problems.append("파일 폭이 %dpx 입니다(한도 %dpx)" % (width, LIMITS["width"] * SCALE))
    return {"kind": kind, "frames": frames, "durations": durations, "bytes": size, "width": width, "height": height, "problems": problems}


def render(module, out_dir, names=None, check=False):
    """모듈의 @figure 함수를 모두(또는 names 의 것만) 그려 out_dir 에 쓰고 파일마다 inspect 결과에 name·path 를 더해 돌려줌."""
    prefix = name_prefix(module.__name__)
    found = draw.figures(module)
    known = [item[0] for item in found]
    for name in names or []:
        if name not in known:
            raise ValueError("%s 에 그림 %s 가 없습니다. 있는 것: %s" % (module.__name__, name, ", ".join(known) or "없음"))
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for name, width, height, fn in found:
        if names and name not in names:
            continue
        fig = draw.Figure(name, width, height)
        fn(fig)
        path = fig.save(out_dir)
        row = inspect(path, check)
        if prefix and not name.startswith(prefix):
            row["problems"].insert(0, "이름이 %s 로 시작해야 합니다" % prefix)
        row.update(name=name, path=path)
        rows.append(row)
    return rows


def folder_bytes(folder):
    return sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)))


def pad(s, width, right=False):
    """한글을 두 칸으로 세어 width 칸이 되게 빈칸을 붙임. right 면 오른쪽 맞춤."""
    cols = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)
    blank = " " * max(0, width - cols)
    return blank + s if right else s + blank


def report(rows, out_dir):
    """표를 찍고 실패한 줄 수를 돌려줌. 폴더 합계도 한도를 봄."""
    print("%s %s %s %s  %s" % (pad("그림", 8), pad("종류", 4), pad("프레임", 6, True), pad("크기", 10, True), "판정"))
    bad = 0
    for row in rows:
        verdict = "통과" if not row["problems"] else "실패"
        bad += bool(row["problems"])
        print("%-8s %-4s %6d %8.1fKB  %s" % (row["name"], row["kind"], row["frames"], row["bytes"] / KB, verdict))
        for problem in row["problems"]:
            print("  %s: %s" % (row["name"], problem))
    total = folder_bytes(out_dir)
    print("폴더 합계 %.1fKB (한도 %dKB)" % (total / KB, LIMITS["total_bytes"] // KB))
    if total > LIMITS["total_bytes"]:
        print("  %s 의 그림 합계가 한도를 넘습니다" % out_dir)
        bad += 1
    return bad


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    out_dir = None
    if "--out" in args:
        at = args.index("--out")
        if at + 1 >= len(args):
            print(USAGE)
            return 2
        out_dir = os.path.abspath(args[at + 1])
        del args[at:at + 2]
    if not args or args[0].startswith("-"):
        print(USAGE)
        return 2
    module_name, names = args[0], args[1:]
    if out_dir is None:
        if not DUNGEON.match(module_name):
            print("%s 는 던전 스크립트가 아니라서 --out DIR 로 쓸 폴더를 정해 주세요." % module_name)
            return 2
        out_dir = assets_dir(module_name)
    try:
        module = importlib.import_module("tools.journey_art.%s" % module_name)
    except ImportError as e:
        print("tools/journey_art/%s.py 를 불러오지 못했습니다: %s" % (module_name, e))
        return 2
    try:
        rows = render(module, out_dir, names, check)
    except ValueError as e:
        print(e)
        return 1
    if not rows:
        print("%s 에 그릴 그림이 없습니다." % module_name)
        return 1
    print("쓴 폴더: %s" % out_dir)
    return 1 if report(rows, out_dir) else 0


if __name__ == "__main__":
    sys.exit(main())
