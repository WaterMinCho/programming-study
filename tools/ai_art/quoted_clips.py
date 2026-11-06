"""보존한 공식 MP4에서 대표 장면을 발췌해 출처와 한글 설명을 붙임.

사용: python tools/ai_art/quoted_clips.py --source-dir DIR --intake FILE
      --permission FILE --evidence-dir DIR [--output-dir DIR]
다운로드하지 않으며 입력 해시와 영상 길이 및 프레임 수를 먼저 대조함.
직접 그린 그림의 manifest와 학습 노트 메타는 수정하지 않음.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import ai_art

AUTHOR = "3Blue1Brown · Grant Sanderson"
LESSON = "https://www.3blue1brown.com/lessons/neural-networks/"
PERMISSION = "https://www.3blue1brown.com/about/"
ASSET_BASE = "https://storage.googleapis.com/3blue1brown-website-bucket/lessons/2017/neural-networks/"
SIZE = (800, 600)
VIDEO_BOX = (0, 96, 800, 546)
FRAME_MS = 1800
FRAME_SELECTIONS = {"network-propagation": (0, 52, 105, 158, 211), "number-line-squish": (0, 37, 43, 51, 74)}
CLIPS = (
    ("network-propagation", "4d-6.gif", 212, 7.073733, "순전파", (
        "입력 그림의 값을 입력층에 대응시킵니다.",
        "그림의 픽셀 값을 입력층에 늘어놓습니다.",
        "층을 지나며 다음 층의 값을 계산합니다.",
        "출력층 쪽으로 계산을 이어 갑니다.",
        "이 장면은 입력에서 출력으로 가는 순전파입니다.",
    )),
    ("number-line-squish", "4e-5.gif", 75, 2.5025, "시그모이드", (
        "실수 입력과 출력 쪽 수직선을 나란히 봅니다.",
        "입력 쪽 눈금이 출력 쪽으로 옮겨 갑니다.",
        "입력 0에 대응하는 위치를 노란 화살표로 봅니다.",
        "눈금 간격이 좁아지는 모습을 따라갑니다.",
        "입력 0은 출력 0.5이며 출력은 0과 1 사이입니다.",
    )),
)


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text_line(image, text, xy, size, bold=False):
    """그림 밖이나 다른 영역으로 글자가 넘어가면 중단함."""
    font = ImageFont.truetype(str(ROOT / "gui/fonts" / ("NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf")), size)
    draw = ImageDraw.Draw(image)
    box = draw.textbbox(xy, text, font=font)
    assert 0 <= box[0] < box[2] <= SIZE[0] - 8, (text, box)
    assert 0 <= box[1] < box[3] <= SIZE[1], (text, box)
    assert box[3] <= VIDEO_BOX[1] or box[1] >= VIDEO_BOX[3], (text, box)
    draw.text(xy, text, font=font, fill="#1f2937")
    return {"text": text, "box": list(box), "font_size": size}


def sheet(frames, path, width):
    """모든 장을 같은 크기로 놓은 검토 시트를 저장함."""
    height = round(width * SIZE[1] / SIZE[0])
    cols = 2
    rows = (len(frames) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * width, rows * height), "#eef0f3")
    for index, frame in enumerate(frames):
        canvas.paste(frame.resize((width, height), Image.Resampling.LANCZOS), ((index % cols) * width, (index // cols) * height))
    canvas.save(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="보존 MP4의 발췌 GIF와 검토 프레임을 만듭니다.")
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--intake", required=True, type=Path)
    parser.add_argument("--permission", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ai/learn/l04/assets")
    parser.add_argument("--ffmpeg", default="/opt/homebrew/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/opt/homebrew/bin/ffprobe")
    args = parser.parse_args(argv)
    evidence = args.evidence_dir.resolve()
    assert not evidence.is_relative_to(ROOT), "검토 증거는 저장소 밖에 보존합니다."
    evidence.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    intake = json.loads(args.intake.read_text(encoding="utf-8"))
    permission = json.loads(args.permission.read_text(encoding="utf-8"))
    assert permission["url"] == PERMISSION
    assert permission.get("condition_summary")
    source_rows = {row["name"]: row for row in intake["sources"]}
    results = []
    assert 1 / (1 + math.exp(0)) == 0.5
    for name, target, count, seconds, topic, descriptions in CLIPS:
        source = (args.source_dir / (name + ".mp4")).resolve()
        assert source.is_file() and source.parent == args.source_dir.resolve()
        record = source_rows[source.name]
        assert record["url"] == ASSET_BASE + source.name
        assert file_sha(source) == record["sha256"]
        assert record["source_range_seconds"] == [0, seconds]
        assert record["duration_seconds"] == seconds and 0 < seconds < 60
        probe = json.loads(subprocess.check_output([
            args.ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height,nb_frames,duration,r_frame_rate",
            "-show_entries", "format=duration", "-of", "json", str(source),
        ], text=True))
        assert len(probe["streams"]) == 1 and probe["streams"][0]["codec_type"] == "video"
        stream = probe["streams"][0]
        assert (stream["width"], stream["height"]) == (1920, 1080)
        assert int(stream["nb_frames"]) == count
        assert abs(float(probe["format"]["duration"]) - seconds) < 0.000001
        selected = list(FRAME_SELECTIONS[name])
        assert len(selected) == 5 and sorted(set(selected)) == selected and selected[-1] < count
        rate = Fraction(stream["r_frame_rate"])
        folder = evidence / name
        folder.mkdir(exist_ok=True)
        expr = "+".join("eq(n\\,%d)" % index for index in selected)
        subprocess.run([args.ffmpeg, "-nostdin", "-v", "error", "-y", "-i", str(source), "-vf", "select=" + expr,
                        "-fps_mode", "vfr", "-frames:v", "5", "-start_number", "0", str(folder / "source-%02d.png")], check=True)
        composed, text_boxes = [], []
        for index, description in enumerate(descriptions):
            with Image.open(folder / ("source-%02d.png" % index)) as raw:
                original = raw.convert("RGB").resize((800, 450), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", SIZE, "#ffffff")
            frame.paste(original, VIDEO_BOX[:2])
            boxes = [text_line(frame, AUTHOR, (14, 4), 32, True),
                     text_line(frame, LESSON, (14, 43), 26),
                     text_line(frame, "원본 장면 발췌 · 대표 5장 · 장마다 1.8초로 표시합니다.", (14, 76), 16),
                     text_line(frame, "추가 한글 해설 · " + topic, (14, 548), 18, True),
                     text_line(frame, description, (14, 573), 20)]
            assert all(left["box"][3] <= right["box"][1] for left, right in zip(boxes, boxes[1:]))
            composed.append(frame)
            text_boxes.append(boxes)
        palette_frames = ai_art.quantize(composed, colors=32)
        path = args.output_dir / target
        palette_frames[0].save(path, save_all=True, append_images=palette_frames[1:], duration=[FRAME_MS] * 5,
                               loop=0, optimize=True, disposal=1)
        assert not ai_art.image_problems(str(path)), ai_art.image_problems(str(path))
        decoded = []
        with Image.open(path) as gif:
            assert gif.n_frames == 5 and gif.size == SIZE
            for index in range(5):
                gif.seek(index)
                assert gif.info["duration"] == FRAME_MS
                frame = gif.convert("RGB")
                assert ImageChops.difference(frame, palette_frames[index].convert("RGB")).getbbox() is None
                assert len(frame.getcolors(SIZE[0] * SIZE[1])) <= 64
                frame.save(folder / ("final-%02d.png" % index))
                decoded.append(frame.copy())
        for width in (800, 520, 320):
            sheet(decoded, folder / ("sheet-%d.png" % width), width)
        results.append({"name": name, "source_url": record["url"], "source_sha256": record["sha256"],
                        "source_seconds": seconds, "source_frame_count": count, "selected_frame_indices": selected,
                        "selected_source_times": [float(Fraction(index, 1) / rate) for index in selected],
                        "gif": str(path), "gif_sha256": file_sha(path), "bytes": path.stat().st_size,
                        "size": list(SIZE), "frames": 5, "colors_max": 64, "frame_ms": FRAME_MS,
                        "display_seconds": 5 * FRAME_MS / 1000, "video_box": list(VIDEO_BOX),
                        "author": AUTHOR, "lesson_url": LESSON, "permission_url": PERMISSION,
                        "text_boxes": text_boxes, "probe": probe})
    assert sum(row["source_seconds"] for row in results) < 60
    note_bytes = sum(p.stat().st_size for p in args.output_dir.iterdir() if p.is_file())
    assert note_bytes <= ai_art.LIMITS["note_bytes"], note_bytes
    write_json(evidence / "renders.json", {"clips": results, "source_seconds_total": sum(row["source_seconds"] for row in results),
               "note_asset_bytes": note_bytes, "permission_record_sha256": file_sha(args.permission),
               "intake_sha256": file_sha(args.intake)})
    print(json.dumps({"gifs": [r["gif"] for r in results], "gif_bytes": [r["bytes"] for r in results],
                      "frames": 10, "note_asset_bytes": note_bytes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
