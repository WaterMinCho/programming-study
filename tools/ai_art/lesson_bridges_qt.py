"""차시 사이의 입력·모델·출력을 같은 연결 예로 그림. 모델 코드는 실행하지 않음."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFontDatabase, QPen
from PyQt6.QtWidgets import QApplication

from tools.ai_art import l01_training_qt as art


ROOT = Path(__file__).resolve().parents[2]
STORIES = {
    10: {
        "title": "같은 분류 문제에서 입력 표현을 준비합니다",
        "previous": "9차시 · 클래스 점수와 정답",
        "current": "10차시 · 입력과 배치",
        "next": "11차시 · 공간을 남긴 특징",
        "input": "사진 4장 · RGB 24×24",
        "input_shape": "(4, 3, 24, 24)", "feature_shape": "(4, 1728)",
        "model": "flat", "feature": "사진마다 1728개 값",
        "changed": "픽셀을 펼쳐 모델 입력에 맞춥니다.",
        "kept": "정답 4개와 클래스 점수 4개씩의 대응은 유지합니다.",
        "handoff": "다음에는 가까운 픽셀의 관계를 남기는 CNN을 배웁니다.",
    },
    11: {
        "title": "펼치기 전에 공간에서 특징을 계산합니다",
        "previous": "10차시 · 펼친 픽셀",
        "current": "11차시 · CNN의 특징",
        "next": "12차시 · 학습 조건 조정",
        "input": "같은 사진 4장 · RGB 24×24",
        "input_shape": "(4, 3, 24, 24)", "feature_shape": "(4, 12, 6, 6)",
        "model": "cnn", "feature": "12채널 · 공간 6×6",
        "changed": "연결 예에서는 공간을 두 번 절반으로 줄입니다.",
        "kept": "배치 4장은 남고, 마지막에는 사진마다 점수 4개를 냅니다.",
        "handoff": "다음에는 이 모델의 학습·검증 조건을 조정합니다.",
    },
    12: {
        "title": "같은 입출력에서 학습 조건을 바꿉니다",
        "previous": "11차시 · CNN과 출력",
        "current": "12차시 · 과적합 대응",
        "next": "13차시 · 학습한 특징 재사용",
        "input": "같은 사진 4장 · RGB 24×24",
        "input_shape": "(4, 3, 24, 24)", "feature_shape": "(4, 12, 6, 6)",
        "model": "dropout", "feature": "가려도 특징 모양은 유지",
        "changed": "Dropout은 일부 값을 가립니다. 축을 없애는 연산이 아닙니다.",
        "kept": "검증에서는 가림을 끄고 같은 클래스 점수 모양을 확인합니다.",
        "handoff": "다음에는 특징 추출부의 가중치를 가져와 사용합니다.",
    },
    13: {
        "title": "특징 추출부를 가져오고 분류기를 맞춥니다",
        "previous": "12차시 · 처음부터 학습",
        "current": "13차시 · 사전학습 특징",
        "next": "14차시 · 갱신할 범위",
        "input": "사진 4장 · 입력은 RGB 224×224",
        "input_shape": "(4, 3, 224, 224)", "feature_shape": "(4, 512)",
        "model": "pretrained", "feature": "이 예의 특징 길이는 512",
        "changed": "입력 크기와 특징 추출부를 바꾸고 분류기를 새로 둡니다.",
        "kept": "분류 대상은 4종이므로 마지막 클래스 점수는 4개입니다.",
        "handoff": "다음에는 가져온 층 중 어디를 갱신할지 정합니다.",
    },
    14: {
        "title": "모양과 파라미터의 갱신 범위를 구분합니다",
        "previous": "13차시 · 특징과 새 분류기",
        "current": "14차시 · 고정과 해제",
        "next": "15차시 · 실제 파일 연결",
        "input": "같은 사진 4장 · RGB 224×224",
        "input_shape": "(4, 3, 224, 224)", "feature_shape": "(4, 512)",
        "model": "freeze", "feature": "고정할 층과 갱신할 층",
        "changed": "초록은 갱신 대상으로 정한 층입니다. 범위를 바꿀 수 있습니다.",
        "kept": "갱신 범위를 바꾸어도 이 예의 출력 모양은 (4, 4)입니다.",
        "handoff": "기울기 설정·optimizer 등록·모드를 맞춘 뒤 파일을 연결합니다.",
    },
    15: {
        "title": "파일의 클래스와 모델 출력의 번호를 잇습니다",
        "previous": "13~14차시 · 모델 준비",
        "current": "15차시 · 파일과 배치",
        "next": "16차시 · 직접 만든 CNN",
        "input": "부품 사진 폴더 4개 · 정답 0~3",
        "input_shape": "파일 → (4, 3, 224, 224)", "feature_shape": "(4, 512)",
        "model": "loader", "feature": "사진 4장과 정답 4개",
        "changed": "폴더의 클래스 번호와 분류기의 점수 칸을 연결합니다.",
        "kept": "사진과 정답의 순서를 맞추고 클래스 점수는 4개씩 냅니다.",
        "handoff": "직접 만든 CNN을 쓰면 입력 크기도 그 모델에 맞춥니다.",
    },
    16: {
        "title": "특징을 직접 만들고 펼친 길이를 검산합니다",
        "previous": "15차시 · 파일에서 배치로",
        "current": "16차시 · 작은 CNN 설계",
        "next": "17차시 · 문장 입력으로",
        "input": "입력을 다시 RGB 24×24로 맞춤",
        "input_shape": "(4, 3, 24, 24)", "feature_shape": "(4, 432)",
        "model": "custom", "feature": "12×6×6을 펼쳐 432",
        "changed": "특징 (4,12,6,6)을 펼치고 432→20→4로 계산합니다.",
        "kept": "펼치기는 특징의 개수를 줄이지 않고 배치 4장도 남깁니다.",
        "handoff": "다음에는 입력을 바꾸되 점수·손실·갱신의 관계를 이어 씁니다.",
    },
    17: {
        "title": "입력이 바뀌어도 분류와 학습의 관계는 남습니다",
        "previous": "16차시 · 사진의 특징",
        "current": "17차시 · 문장의 특징",
        "next": "공통 · 점수와 손실·갱신",
        "input": "이번에는 문장 4개 · 길이는 5로 맞춤",
        "input_shape": "토큰 번호 (4, 5)", "feature_shape": "(4, 5, 8) → (4, 8)",
        "model": "tokens", "feature": "단어 벡터와 문장 특징",
        "changed": "사진 대신 토큰 번호를 받고, 문장 특징으로 점수를 만듭니다.",
        "kept": "클래스 점수 (4,4)와 정답 (4,)을 손실에 전달합니다.",
        "handoff": "벡터·마지막 상태를 구하는 조건은 이 차시에서 확인합니다.",
    },
}


def rectangle(painter, rect, fill, border=art.GRAY, radius=10):
    painter.setPen(QPen(QColor(border), 2))
    painter.setBrush(QColor(fill))
    painter.drawRoundedRect(QRectF(*rect), radius, radius)


def cube(painter, x, y, width, height, planes, color, grid=4):
    """채널과 공간을 겹친 판으로 구분해 그림. 배치 축은 글로 따로 표시함."""
    for index in reversed(range(planes)):
        offset = index * 11
        rectangle(painter, (x + offset, y - offset, width, height), '#ffffff', color, 2)
        painter.setPen(QPen(QColor(color), 1))
        for part in range(1, grid):
            painter.drawLine(QPointF(x + offset + width * part / grid, y - offset),
                             QPointF(x + offset + width * part / grid, y - offset + height))
            painter.drawLine(QPointF(x + offset, y - offset + height * part / grid),
                             QPointF(x + offset + width, y - offset + height * part / grid))


def values(painter, x, y, rows=4, columns=4, color=art.ORANGE, masked=False):
    for row in range(rows):
        for column in range(columns):
            blank = masked and (row, column) in ((0, 1), (1, 3), (2, 0), (3, 2))
            rectangle(painter, (x + column * 36, y + row * 31, 30, 25),
                      art.PALE if blank else '#ffffff', art.GRAY if blank else color, 3)
            if blank:
                art.text(painter, x + column * 36 + 7, y + row * 31, 20, 25, '0', art.MUTED, 20)


def model_drawing(painter, story, frame):
    kind = story['model']
    if kind in ('cnn', 'dropout', 'custom'):
        cube(painter, 443, 276, 94, 94, 3, art.PURPLE, grid=6)
        if kind == 'dropout':
            for row in range(6):
                for column in range(6):
                    hidden = (row, column) in ((0, 1), (1, 3), (2, 0), (3, 2), (5, 4))
                    rectangle(painter, (588 + column * 18, 263 + row * 18, 15, 15),
                              art.PALE if hidden else '#ffffff', art.GRAY if hidden else art.PURPLE, 1)
            art.text(painter, 588, 371, 140, 28, '가림 예', art.MUTED, 21)
        elif kind == 'custom':
            art.arrow(painter, (578, 324), (607, 324), art.PURPLE)
            for n in range(4):
                rectangle(painter, (615 + n * 18, 301, 15, 42), '#ffffff', art.PURPLE, 2)
            art.text(painter, 690, 306, 38, 32, '…', art.PURPLE, 25)
            art.text(painter, 608, 254, 130, 32, '펼침', art.PURPLE, 24)
        else:
            art.arrow(painter, (581, 324), (618, 324), art.PURPLE)
            cube(painter, 633, 302, 45, 45, 2, art.PURPLE, grid=6)
        art.text(painter, 401, 392, 338, 35, story['feature_shape'], art.PURPLE, 27, True)
    elif kind in ('pretrained', 'freeze'):
        for n in range(3):
            learned = n == 2 or (kind == 'freeze' and frame >= 1 and n == 1)
            color = art.GREEN if learned else art.PURPLE
            rectangle(painter, (405 + n * 112, 264, 100, 96),
                      '#d1fae5' if learned else art.PURPLE_PALE, color)
            label = ('특징 앞', '특징 뒤', '분류기')[n]
            art.text(painter, 413 + n * 112, 291, 84, 40, label, color, 22, True)
        art.text(painter, 413, 388, 324, 35, story['feature_shape'], art.PURPLE, 27, True)
    elif kind == 'tokens':
        cube(painter, 424, 281, 69, 86, 3, art.PURPLE, grid=1)
        art.arrow(painter, (548, 313), (592, 313), art.PURPLE)
        for n in range(4): rectangle(painter, (610 + n * 22, 288, 18, 52), '#ffffff', art.PURPLE, 2)
        art.text(painter, 610, 346, 115, 30, '… 특징 8', art.PURPLE, 20)
        art.text(painter, 393, 392, 356, 35, story['feature_shape'], art.PURPLE, 24, True)
    elif kind == 'loader':
        rectangle(painter, (414, 257, 316, 60), art.PURPLE_PALE, art.PURPLE)
        art.text(painter, 432, 269, 286, 38, '모델 · 사진 → 점수', art.PURPLE, 26, True)
        art.text(painter, 414, 337, 324, 35, '정답 (4,) · 0, 1, 2, 3', art.BLUE, 25, True)
        art.text(painter, 403, 387, 337, 32, '정답은 손실 계산에 따로 전달', art.BLUE, 21)
    else:
        values(painter, 415, 270, rows=4, columns=7, color=art.BLUE)
        art.text(painter, 401, 392, 338, 35, story['feature_shape'], art.PURPLE, 27, True)


def frames(number):
    story = STORIES[number]
    output = []
    for frame in range(3):
        image, painter = art.canvas()
        art.text(painter, 24, 12, 1072, 44, '%d차시 · %s' % (number, story['title']), size=31, bold=True)
        art.text(painter, 24, 65, 1072, 32, '차시 연결용 예입니다. 입력은 기호로 나타내며 실제 모델을 실행한 결과가 아닙니다.', art.MUTED, 21)
        for index, label in enumerate((story['previous'], story['current'], story['next'])):
            x = 24 + index * 362
            active = index == frame
            rectangle(painter, (x, 114, 348, 46), art.PURPLE_PALE if active else '#ffffff', art.PURPLE if active else art.GRAY)
            art.text(painter, x + 12, 121, 324, 32, label, art.PURPLE if active else art.MUTED, 23, active)
        rectangle(painter, (24, 184, 1072, 283), '#ffffff')
        labels = [('입력', art.BLUE), ('이번에 다루는 표현', art.PURPLE), ('분류기 출력', art.ORANGE)]
        for index, (label, color) in enumerate(labels):
            x = (48, 399, 804)[index]
            art.text(painter, x, 200, (320, 346, 264)[index], 37, label, color, 27, True)
        if number == 17:
            token_rows = ((2, 4, 3, 0, 0), (5, 3, 6, 2, 4), (2, 5, 6, 3, 0), (4, 3, 6, 2, 5))
            for row, tokens in enumerate(token_rows):
                for col, token in enumerate(tokens):
                    rectangle(painter, (63 + col * 46, 261 + row * 30, 39, 26), art.PALE if token == 0 else '#ffffff', art.BLUE, 2)
                    art.text(painter, 73 + col * 46, 261 + row * 30, 28, 26, str(token), art.MUTED if token == 0 else art.BLUE, 22)
            art.text(painter, 63, 396, 310, 35, '토큰 번호 · 0은 PAD', art.BLUE, 23)
        else:
            cube(painter, 83, 278, 114, 92, 3, art.BLUE, grid=24 if number in (10, 11, 12, 16) else 1)
            art.text(painter, 66, 396, 310, 35, '배치 4장 · 정답 4개', art.BLUE, 24, True)
        model_drawing(painter, story, frame)
        values(painter, 843, 269)
        art.text(painter, 819, 393, 270, 35, '(4, 4)', art.ORANGE, 29, True)
        arrow_y = 284 if number == 15 else 326
        art.arrow(painter, (327, arrow_y), (379, arrow_y), art.PURPLE)
        art.arrow(painter, (745, arrow_y), (793, arrow_y), art.ORANGE)
        art.text(painter, 43, 438, 1050, 28, story['input'] + '  →  ' + story['feature'], art.MUTED, 22)
        messages = ((story['kept'], '입력 모양: ' + story['input_shape']),
                    (story['changed'], '연결 예: ' + story['feature']),
                    (story['handoff'], '같은 학습 관계: 점수 → 손실 → 기울기 → 파라미터 갱신'))
        for line, text in enumerate(messages[frame]):
            art.text(painter, 24, 494 + line * 48, 1072, 40, text,
                     art.PURPLE if line == 0 else art.MUTED, 27 if line == 0 else 24, line == 0)
        painter.end()
        output.append(image)
    return output


def save_gif(images, path, pillow):
    pictures = []
    for image in images:
        rgba = image.convertToFormat(art.QImage.Format.Format_RGBA8888)
        pictures.append(pillow.frombytes('RGBA', (art.WIDTH, art.HEIGHT),
                                        rgba.constBits().asstring(rgba.sizeInBytes())).convert('RGB'))
    sheet = pillow.new('RGB', (art.WIDTH, art.HEIGHT * len(pictures)), 'white')
    for n, picture in enumerate(pictures): sheet.paste(picture, (0, n * art.HEIGHT))
    palette = sheet.quantize(colors=64)
    fixed = ['#ffffff', art.INK, art.MUTED, art.GRAY, art.BLUE, art.PURPLE, art.ORANGE, art.GREEN,
             art.PALE, art.PURPLE_PALE, '#d1fae5']
    channels = [value for color in fixed for value in (QColor(color).red(), QColor(color).green(), QColor(color).blue())]
    colors = channels + palette.getpalette()[:(64 - len(fixed)) * 3]
    palette.putpalette(colors + [0] * (768 - len(colors)))
    pictures = [picture.quantize(palette=palette, dither=pillow.Dither.NONE) for picture in pictures]
    pictures[0].save(path, save_all=True, append_images=pictures[1:], duration=2400, loop=0, disposal=1, optimize=True)
    with pillow.open(path) as saved:
        assert saved.n_frames == 3 and saved.size == (1120, 600)
    assert path.stat().st_size < 250 * 1024


def main():
    parser = argparse.ArgumentParser(description='차시 연결 그림을 필요한 차시만 만듭니다.')
    parser.add_argument('--only', type=int, nargs='+', choices=list(STORIES), required=True)
    parser.add_argument('--pillow-site')
    args = parser.parse_args()
    if args.pillow_site: sys.path.append(args.pillow_site)
    from PIL import Image
    app = QApplication.instance() or QApplication([])
    for name in ('NanumGothic-Regular.ttf', 'NanumGothic-Bold.ttf', 'D2Coding-Regular.ttf'):
        font_id = QFontDatabase.addApplicationFont(str(ROOT / 'gui/fonts' / name))
        assert font_id >= 0
        art.FONTS['code' if name.startswith('D2') else 'body'] = QFontDatabase.applicationFontFamilies(font_id)[0]
    assert 3 * 24 * 24 == 1728 and 12 * 6 * 6 == 432 and 24 // 2 // 2 == 6
    manifest_path = ROOT / 'tools/ai_art/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for number in args.only:
        path = ROOT / ('ai/learn/l%02d/assets/%da-8.gif' % (number, number))
        save_gif(frames(number), path, Image)
        key = path.relative_to(ROOT / 'ai').as_posix()
        manifest['files'][key] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                  'script': 'tools/ai_art/lesson_bridges_qt.py', 'fn': 'bridge_%d' % number}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n')
    assert not any(name in sys.modules for name in ('torch', 'numpy', 'matplotlib'))
    return app


if __name__ == '__main__':
    main()
