# -*- coding: utf-8 -*-
"""AI 비전 개론 그림 도구(설계 7.2, 7.4). 학습 노트 그림은 출제자 컴퓨터에서 tools/ai_art/lNN.py 가 matplotlib(Agg)·Pillow 로
그리고 `python -m tools.ai_art lNN` 이 ai/learn/lNN/assets/ 에 씀.

이 파일의 위쪽(이름 규칙, 한도, manifest, 그림 파일 검사)은 표준 라이브러리만 써서 CI 의 verify_ai 가 import 함. 아래쪽 그리기
도우미(setup, canvas, to_image, quantize, save)는 부를 때 matplotlib·Pillow 를 import 함. 스크립트는 이렇게 씀:

    from tools.ai_art import figure, setup, canvas, to_image, COLORS

    @figure("l05-3", 560, 300)
    def descent():
        plt = setup()
        frames = []
        for k in range(6):
            fig, ax = canvas(560, 300)
            ...                                   # 그림에 찍는 숫자는 assert 로 확인함
            frames.append(to_image(fig))
        return frames, [2000] * 6                 # GIF. PNG 는 그림 한 장(Image 나 Figure)만 돌려줌

그림 이름은 웹 규칙과 같음(페이지 l05-3, 단원 5c-1, 상황별 코드 18a-1). 파일 폭은 논리 폭의 2배(1120 이하), 높이 600 이하.
만든 파일의 sha256 을 tools/ai_art/manifest.json 에 은행 기준 경로(learn/l05/assets/l05-3.gif)로 적어 verify_ai 가 "스크립트로
그린 그림"인지 봄. 바이트가 판·글꼴마다 달라서 다시 그린 그림이 같은 바이트인지는 보지 않음. 자기 명령줄로 그리는 스크립트
(python tools/ai_art/l02.py)는 그린 뒤 `python -m tools.ai_art l02 --record` 로 manifest 만 고침.
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

KB = 1024
SCALE = 2
LIMITS = {
    "gif_bytes": 250 * KB, "png_bytes": 150 * KB,
    "frames": 10, "frames_min": 2, "ms_min": 1600, "ms_max": 2500,
    "width": 1120, "height": 600, "colors": 64,
    "note_bytes": int(2.5 * 1024 * KB), "total_bytes": 32 * 1024 * KB, "warn_bytes": 28 * 1024 * KB,
}
NAMES = {
    "page": re.compile(r"^a?l\d{2}-\d{1,2}\Z"),
    "section": re.compile(r"^a?\d{1,2}[a-i]-\d{1,2}\Z"),
}
MANIFEST = os.path.join(ROOT, "tools", "ai_art", "manifest.json")
FONTS = os.path.join(ROOT, "gui", "fonts")
COLORS = {"ink": "#1f2937", "muted": "#6b7280", "faint": "#d1d5db", "grid": "#eef0f3", "blue": "#2563eb", "red": "#dc2626",
          "orange": "#ea580c", "green": "#059669", "purple": "#7c3aed", "highlight": "#fef3c7"}
# 그림 스크립트가 쓰는 색 이름표와 글자로 적은 색. quantize() 는 그림에 있는 이 색을 팔레트에 그대로 넣음.
# 스크립트에 새 색을 쓰면 여기에도 넣어야 tests/test_ai_tools.py 가 통과함
FIXED = ("#ffffff",) + tuple(COLORS.values()) + (
    "#9ca3af", "#e5e7eb", "#f3f4f6", "#f8fafc", "#fafafa", "#eff6ff", "#dbeafe", "#bfdbfe", "#93c5fd", "#3b82f6",
    "#1d4ed8", "#fee2e2", "#b91c1c", "#ffedd5", "#c2410c", "#d1fae5", "#047857", "#ede9fe", "#6d28d9", "#fde68a",
    "#253747", "#3d6187", "#9fb2c4", "#e0e8f0")
MINUS = "−"

_FIGURES = []


def page_of(name):
    """그림 이름의 학습 노트 id. l05-3 → l05, 5c-1 → l05, 18a-1 → l18. 규칙에 맞지 않으면 None."""
    if NAMES["page"].match(name or ""):
        return name.split("-")[0]
    if NAMES["section"].match(name or ""):
        return ("al%02d" if name.startswith("a") else "l%02d") % int(re.search(r"\d+", name).group(0))
    return None


def figure(name, width=560, height=300):
    """그림 함수 선언. width·height 는 화면 크기(논리 px)이고 파일은 SCALE 배."""
    def wrap(fn):
        if page_of(name) is None:
            raise ValueError("그림 이름은 l05-3 이나 5c-1 꼴이어야 합니다: %r" % name)
        if width * SCALE > LIMITS["width"] or height * SCALE > LIMITS["height"]:
            raise ValueError("그림 %s 가 %d×%d 입니다(화면 한도 %d×%d)." % (name, width, height, LIMITS["width"] // SCALE,
                                                                 LIMITS["height"] // SCALE))
        fn.ai_figure = (name, width, height)
        _FIGURES.append((name, width, height, fn))
        return fn
    return wrap


def figures(module):
    """모듈 안의 @figure 함수 [(이름, 폭, 높이, 함수)] (선언 순서)."""
    found = [getattr(fn, "ai_figure") + (fn,) for fn in vars(module).values() if callable(fn) and hasattr(fn, "ai_figure")]
    order = {fn: n for n, (_, _, _, fn) in enumerate(_FIGURES)}
    return sorted(found, key=lambda row: order.get(row[3], 0))


# manifest

def file_sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_manifest(path=None):
    """{"format": 1, "files": {은행 기준 경로: {"sha256", "script", "fn"}}}. 없으면 빈 것."""
    path = path or MANIFEST
    if not os.path.isfile(path):
        return {"format": 1, "files": {}}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("files", {})
    return data


def write_manifest(data, path=None):
    path = path or MANIFEST
    data = {"format": 1, "files": dict(sorted(data.get("files", {}).items()))}
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


# 그림 파일 검사(표준 라이브러리)

def image_info(path):
    """{"kind", "bytes", "width", "height", "frames", "durations"}. 읽지 못하면 ValueError."""
    from tools.verify_journey import gif_info, png_info
    kind = os.path.splitext(path)[1].lower()[1:]
    with open(path, "rb") as f:
        data = f.read()
    info = gif_info(data) if kind == "gif" else png_info(data)
    return dict(info, kind=kind, bytes=len(data))


def image_problems(path):
    """그림 한 장이 7.4 한도를 넘은 곳의 문구 목록."""
    try:
        info = image_info(path)
    except ValueError as error:
        return ["읽을 수 없습니다(%s)" % error]
    found = []
    limit = LIMITS["%s_bytes" % info["kind"]] if info["kind"] in ("gif", "png") else LIMITS["png_bytes"]
    if info["bytes"] > limit:
        found.append("크기가 %.1fKB 입니다(한도 %dKB)" % (info["bytes"] / float(KB), limit // KB))
    if info["width"] > LIMITS["width"] or info["height"] > LIMITS["height"]:
        found.append("파일 크기가 %d×%d 입니다(한도 %d×%d)" % (info["width"], info["height"], LIMITS["width"], LIMITS["height"]))
    if info["kind"] == "gif":
        if info["frames"] > LIMITS["frames"]:
            found.append("장이 %d개입니다(한도 %d개)" % (info["frames"], LIMITS["frames"]))
        bad = [ms for ms in info["durations"] if not LIMITS["ms_min"] <= ms <= LIMITS["ms_max"]]
        if bad:
            found.append("장 시간 %s 가 %d~%dms 를 벗어납니다" % (", ".join("%dms" % ms for ms in bad), LIMITS["ms_min"],
                                                           LIMITS["ms_max"]))
    return found


# 그리기 도우미(출제자 컴퓨터에서만)

def math_symbols(fig):
    """수식 기호와 음수 눈금에 맞는 글꼴을 쓰며 한글 설명 글꼴은 유지함."""
    from matplotlib.text import Text
    from matplotlib.ticker import FuncFormatter, ScalarFormatter
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            formatter = axis.get_major_formatter()
            if isinstance(formatter, ScalarFormatter) and min(axis.get_view_interval()) < 0:
                axis.set_major_formatter(FuncFormatter(lambda value, _: format(value, "g").replace("-", MINUS)))
                for label in axis.get_ticklabels():
                    label.set_fontfamily("DejaVu Sans")
    for text in fig.findobj(match=Text):
        value = text.get_text()
        if "$" in value:
            text.set_math_fontfamily("dejavusans")
        elif any(char in value for char in ("μ", "γ", "α", "δ", "√", "−")):
            text.set_fontfamily(["DejaVu Sans", "NanumGothic"])


def setup():
    """matplotlib 을 Agg 로 켜고 gui/fonts 의 나눔고딕·D2Coding 을 등록한 pyplot. 창을 띄우지 않음."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for name in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf", "D2Coding-Regular.ttf", "D2Coding-Bold.ttf"):
        path = os.path.join(FONTS, name)
        if os.path.isfile(path):
            font_manager.fontManager.addfont(path)
    plt.rcParams.update({"font.family": ["NanumGothic", "DejaVu Sans"], "axes.unicode_minus": False, "font.size": 17,
                         "axes.titlesize": 19, "axes.labelsize": 17, "xtick.labelsize": 15, "ytick.labelsize": 15,
                         "axes.edgecolor": "#9ca3af", "figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white"})
    return plt


def canvas(width=560, height=300):
    """논리 폭·높이의 SCALE 배 픽셀인 (Figure, Axes)."""
    plt = setup()
    fig = plt.figure(figsize=(width * SCALE / 100.0, height * SCALE / 100.0), dpi=100)
    ax = fig.add_axes([0.1, 0.14, 0.86, 0.76])
    return fig, ax


def to_image(fig):
    """matplotlib Figure 를 Pillow RGB 그림으로 바꾸고 Figure 를 닫음."""
    import numpy as np
    from PIL import Image
    fig.canvas.draw()
    data = np.asarray(fig.canvas.buffer_rgba())
    image = Image.fromarray(data[..., :3].copy())
    import matplotlib.pyplot as plt
    plt.close(fig)
    return image


def fmt(value, digits=4):
    """그림에 찍는 숫자 글. 빼기표는 U+2212."""
    text = ("%.*f" % (digits, value)).rstrip("0").rstrip(".") if digits else "%.0f" % value
    return ("0" if text == "-0" else text).replace("-", MINUS)


def _image(item):
    if hasattr(item, "canvas") and hasattr(item, "savefig"):
        return to_image(item)
    return item.convert("RGB")


def quantize(images, colors=None):
    """RGB 그림 목록을 팔레트 하나를 같이 쓰는 P 그림 목록으로 줄임(디더링 없음). FIXED 가운데 그림에 있는 색을 먼저
    팔레트에 넣고, 남은 자리는 나머지 픽셀을 FASTOCTREE 로 줄인 색으로 채움. 픽셀마다 팔레트에서 가장 가까운 색을 고르므로
    FIXED 색 픽셀은 값이 바뀌지 않음. 팔레트는 colors(기본 LIMITS["colors"]) 색 이하."""
    import numpy as np
    from PIL import Image
    colors = colors or LIMITS["colors"]
    arrays = [np.asarray(image.convert("RGB"), dtype=np.int32) for image in images]
    pixels = np.concatenate([(a[..., 0] << 16 | a[..., 1] << 8 | a[..., 2]).ravel() for a in arrays])
    seen = np.zeros(1 << 24, dtype=bool)
    seen[pixels] = True
    fixed = np.array([int(value[1:], 16) for value in FIXED])
    palette = [int(value) for value in fixed[seen[fixed]]]
    kept = np.zeros(1 << 24, dtype=bool)
    kept[palette] = True
    rest = pixels[~kept[pixels]]
    if rest.size and len(palette) < colors:
        strip = np.stack([rest >> 16, rest >> 8 & 255, rest & 255], axis=-1).astype(np.uint8)[None]
        small = Image.fromarray(strip).quantize(colors - len(palette), method=Image.Quantize.FASTOCTREE,
                                                dither=Image.Dither.NONE)
        palette += [r << 16 | g << 8 | b for _, (r, g, b) in small.convert("RGB").getcolors()]
    rgb = np.array([[value >> 16, value >> 8 & 255, value & 255] for value in palette])
    unique = np.flatnonzero(seen)
    wanted = np.stack([unique >> 16, unique >> 8 & 255, unique & 255], axis=-1)
    lookup = np.zeros(1 << 24, dtype=np.uint8)
    for s in range(0, len(unique), 4096):
        lookup[unique[s:s + 4096]] = ((wanted[s:s + 4096, None] - rgb) ** 2).sum(-1).argmin(-1)
    index = lookup[pixels]
    flat = [int(part) for part in rgb.ravel()]
    out, start = [], 0
    for image in images:
        width, height = image.size
        frame = Image.frombytes("P", (width, height), index[start:start + width * height].tobytes())
        frame.putpalette(flat)
        out.append(frame)
        start += width * height
    return out


def save(name, result, out_dir):
    """그림 함수가 돌려준 것을 파일로. 그림 한 장이면 PNG, (장 목록, 장 시간) 이나 장 목록이면 GIF(장 시간 2000ms).
    quantize() 로 줄이고 GIF 는 모든 장이 팔레트 하나를 같이 씀. 쓴 경로."""
    os.makedirs(out_dir, exist_ok=True)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], (list, tuple)):
        frames, durations = [_image(f) for f in result[0]], list(result[1])
    elif isinstance(result, (list, tuple)):
        frames, durations = [_image(f) for f in result], [2000] * len(result)
    else:
        path = os.path.join(out_dir, name + ".png")
        quantize([_image(result)])[0].save(path, optimize=True)
        return path
    width, height = frames[0].size
    for k, frame in enumerate(frames):
        if frame.size != (width, height):
            raise ValueError("%s 의 %d번째 장 크기가 다릅니다" % (name, k + 1))
    quantized = quantize(frames)
    path = os.path.join(out_dir, name + ".gif")
    quantized[0].save(path, save_all=True, append_images=quantized[1:], duration=durations, loop=0, optimize=True, disposal=1)
    return path


def record(page_id, bank_dir=None, manifest=None, script=None):
    """스크립트가 이미 그린 assets/ 의 그림을 manifest 에 적음(표준 라이브러리만). 스크립트 파일이 있어야 함. 적은 경로 목록."""
    bank_dir = bank_dir or os.path.join(ROOT, "ai")
    script = script or "tools/ai_art/%s.py" % page_id
    if not os.path.isfile(os.path.join(ROOT, *script.split("/"))):
        raise ValueError("그림 스크립트가 없습니다: %s" % script)
    assets = os.path.join(bank_dir, "learn", page_id, "assets")
    data = read_manifest(manifest)
    prefix = "learn/%s/assets/" % page_id
    data["files"] = {k: v for k, v in data["files"].items() if not k.startswith(prefix)}
    done = []
    for name in sorted(os.listdir(assets)) if os.path.isdir(assets) else []:
        stem, ext = os.path.splitext(name)
        if ext.lower() not in (".gif", ".png") or page_of(stem) != page_id:
            continue
        rel = prefix + name
        data["files"][rel] = {"sha256": file_sha(os.path.join(assets, name)), "script": script, "fn": stem}
        done.append(rel)
    write_manifest(data, manifest)
    return done


def render(page_id, names=None, bank_dir=None, manifest=None, script=None):
    """tools/ai_art/<page_id>.py 의 그림을 그려 <은행>/learn/<page_id>/assets/ 에 쓰고 manifest 를 고침. 그림마다
    {"name", "path", "problems"} 목록."""
    import importlib.util
    bank_dir = bank_dir or os.path.join(ROOT, "ai")
    script = script or os.path.join(ROOT, "tools", "ai_art", page_id + ".py")
    spec = importlib.util.spec_from_file_location("ai_art_" + page_id, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    found = figures(module)
    known = [row[0] for row in found]
    for name in names or []:
        if name not in known:
            raise ValueError("그림 %s 가 없습니다. 있는 것: %s" % (name, ", ".join(known) or "없음"))
    data = read_manifest(manifest)
    out_dir = os.path.join(bank_dir, "learn", page_id, "assets")
    rows = []
    for name, width, height, fn in found:
        if names and name not in names:
            continue
        problems = [] if page_of(name) == page_id else ["이름이 %s 의 그림이 아닙니다" % page_id]
        path = save(name, fn(), out_dir)
        problems += image_problems(path)
        rel = os.path.relpath(path, bank_dir).replace(os.sep, "/")
        data["files"][rel] = {"sha256": file_sha(path), "script": "tools/ai_art/%s.py" % page_id, "fn": fn.__name__}
        rows.append({"name": name, "path": path, "problems": problems})
    write_manifest(data, manifest)
    return rows
