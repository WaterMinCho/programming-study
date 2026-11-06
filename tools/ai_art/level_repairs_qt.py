"""전수검수에서 확인한 그림의 연산 관계와 출력 축을 Qt로 보완함."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFontDatabase, QPen
from PyQt6.QtWidgets import QApplication

from tools.ai_art import l01_training_qt as art
from tools.ai_art.lesson_bridges_qt import cube, rectangle


ROOT = Path(__file__).resolve().parents[2]
CASES = {
    '13b-32': '같은 네 값의 공간 평균을 계산합니다',
    '13c-33': 'weight의 행과 열을 구분합니다',
    '14c-31': '처음 열 칸에서 두 칸을 지웁니다',
    '14c-33': '그룹의 학습률로 파라미터를 갱신합니다',
    '14d-31': '열 개씩 담은 묶음 두 개를 놓습니다',
    '14d-33': '초기 학습률에 같은 배수를 적용합니다',
    '14e-33': '해제한 블록을 목록에 남깁니다',
    '15b-33': '자른 뒤 채널·높이·너비를 읽습니다',
    '15c-33': '정규화 전후의 모양을 비교합니다',
    '15d-33': '마지막 배치의 실제 길이를 확인합니다',
    '16a-1': '선택한 입력 창과 필터를 곱합니다',
    '16b-31': '양 끝에 한 칸씩 붙입니다',
    '16b-33': '너비 축의 출력 길이를 계산합니다',
    '16c-33': '입력 창의 최댓값을 한 칸에 남깁니다',
    '16d-31': '여덟 칸을 같은 크기로 나눕니다',
    '16d-33': '펼친 뒤 배치와 특징을 구분합니다',
    '17a-33': '남긴 토큰과 잘라낸 토큰을 구분합니다',
    '17c-33': '층과 방향을 묶어 첫 축을 만듭니다',
}


def label(painter, x, y, width, value, color=art.INK, size=28, bold=False):
    art.text(painter, x, y, width, 42, value, color, size, bold)


def cell_grid(painter, x, y, values, cell=64, highlight=()):
    for row, line in enumerate(values):
        for col, value in enumerate(line):
            active = (row, col) in highlight
            rectangle(painter, (x + col * cell, y + row * cell, cell, cell),
                      art.HIGHLIGHT if active else '#ffffff', art.ORANGE if active else art.GRAY, 2)
            label(painter, x + col * cell + 13, y + row * cell + (cell - 42) / 2,
                  cell - 14, str(value), size=29, bold=active)


def strip(painter, x, y, count, width=42, active=(), caption=''):
    for index in range(count):
        rectangle(painter, (x + index * width, y, width - 5, 54),
                  art.PURPLE_PALE if index in active else '#ffffff', art.PURPLE if index in active else art.GRAY, 3)
    if caption: label(painter, x, y + 68, 1000 - x, caption, art.MUTED, 25)


def picture(name):
    image, painter = art.canvas()
    label(painter, 32, 20, 1056, CASES[name], size=34, bold=True)
    if name == '13b-32':
        cell_grid(painter, 95, 180, [[1, 3], [5, 7]], 84)
        art.arrow(painter, (322, 265), (438, 265), art.PURPLE)
        label(painter, 468, 181, 600, '(1 + 3 + 5 + 7) ÷ 4', art.PURPLE, 34, True)
        label(painter, 468, 257, 600, '같은 공간의 네 값을 평균 냅니다.', size=28)
        rectangle(painter, (682, 339, 104, 80), art.PURPLE_PALE, art.PURPLE)
        label(painter, 711, 355, 70, '4', art.PURPLE, 36, True)
    elif name == '13c-33':
        cell_grid(painter, 315, 177, [['w'] * 4 for _ in range(3)], 66)
        label(painter, 325, 113, 420, '입력 4열', art.BLUE, 29, True)
        label(painter, 72, 245, 227, '출력 3행', art.PURPLE, 29, True)
        label(painter, 680, 177, 360, 'bias는 별도입니다.', art.MUTED, 27)
        cell_grid(painter, 715, 250, [['b'], ['b'], ['b']], 56)
        label(painter, 295, 442, 700, 'weight.shape = (3, 4)', art.PURPLE, 32, True)
    elif name == '14c-31':
        label(painter, 60, 123, 990, '처음에는 열 칸이 있습니다.', size=30)
        strip(painter, 65, 233, 10, 86)
        for index in (8, 9):
            x = 65 + index * 86
            art.line(painter, (x + 4, 236), (x + 74, 282), art.RED, 4)
            art.line(painter, (x + 4, 282), (x + 74, 236), art.RED, 4)
        label(painter, 65, 352, 990, '오른쪽 두 칸에 지울 표시를 했습니다.', art.RED, 29)
    elif name == '14c-33':
        for x, heading, value in ((80, '갱신 전 p', '10'), (795, '갱신 후 p', '9.8')):
            label(painter, x, 157, 270, heading, art.GREEN, 28, True)
            rectangle(painter, (x, 224, 228, 96), '#d1fae5', art.GREEN)
            label(painter, x + 55, 249, 150, value, art.GREEN, 38, True)
        art.arrow(painter, (355, 272), (748, 272), art.GREEN)
        label(painter, 380, 192, 400, '그룹 lr 0.1 · grad 2', art.PURPLE, 28)
        label(painter, 318, 378, 750, '10 − 0.1 × 2 = 9.8', art.GREEN, 34, True)
        label(painter, 225, 464, 800, '생성자 lr 0.5 대신 그룹의 lr를 사용합니다.', art.MUTED, 25)
    elif name == '14d-31':
        for x in (95, 620):
            rectangle(painter, (x - 20, 171, 405, 216), '#ffffff', art.BLUE)
            for row in range(2):
                for col in range(5): art.dot(painter, (x + 30 + col * 73, 230 + row * 92), art.BLUE, 12)
            label(painter, x + 50, 402, 335, '열 개를 담은 묶음', art.BLUE, 28)
    elif name == '14d-33':
        label(painter, 95, 117, 970, '초기 기준 10 × 함수의 배수 0.1', art.PURPLE, 32, True)
        for n, title in enumerate(('설정 직후', '첫 step 뒤', '둘째 step 뒤')):
            x = 92 + n * 350
            label(painter, x, 215, 325, title, size=28)
            rectangle(painter, (x, 285, 260, 98), art.PURPLE_PALE, art.PURPLE)
            label(painter, x + 91, 309, 140, '1', art.PURPLE, 38, True)
        label(painter, 92, 458, 980, '이전 결과에 다시 곱하지 않습니다.', art.MUTED, 28)
    elif name == '14e-33':
        label(painter, 72, 122, 1000, 'e = 11 · 구간 길이 3', art.PURPLE, 31, True)
        for n, value in enumerate(('layer4', 'layer3', 'layer2', 'layer1')):
            active = n < 3
            x = 72 + n * 262
            rectangle(painter, (x, 238, 232, 88), '#d1fae5' if active else art.PALE, art.GREEN if active else art.GRAY)
            label(painter, x + 28, 260, 200, value, art.GREEN if active else art.MUTED, 29, active)
        label(painter, 72, 383, 990, 'active = [layer4, layer3, layer2]', art.GREEN, 30, True)
        label(painter, 72, 455, 990, '앞서 해제한 블록은 목록에 남습니다.', art.MUTED, 27)
    elif name == '15b-33':
        cube(painter, 375, 207, 211, 211, 3, art.BLUE)
        label(painter, 108, 210, 240, '채널 C = 3', art.BLUE, 28, True)
        label(painter, 675, 222, 360, '높이 H = 4', art.PURPLE, 28, True)
        label(painter, 675, 320, 360, '너비 W = 4', art.PURPLE, 28, True)
        label(painter, 315, 469, 760, 'ToTensor 뒤 모양 (3, 4, 4)', art.BLUE, 32, True)
    elif name == '15c-33':
        for x, title in ((75, '정규화 전'), (770, '정규화 뒤')):
            label(painter, x, 150, 300, title, art.BLUE, 29, True)
            cube(painter, x + 15, 238, 113, 113, 3, art.BLUE, grid=1)
            label(painter, x, 412, 315, '(C,H,W) = (3,1,1)', art.BLUE, 27, True)
        art.arrow(painter, (365, 298), (718, 298), art.PURPLE)
        label(painter, 424, 223, 310, 'Normalize', art.PURPLE, 30, True)
        label(painter, 384, 352, 390, '값의 범위를 바꿉니다.', art.MUTED, 26)
    elif name == '15d-33':
        for n, (count, title) in enumerate(((5, '앞 배치'), (5, '다음 배치'), (4, '마지막 배치'))):
            x = 72 + n * 350
            label(painter, x, 157, 315, title, art.BLUE, 29, True)
            for col in range(count): rectangle(painter, (x + col * 51, 253, 44, 64), '#ffffff', art.BLUE, 4)
            label(painter, x, 365, 315, 'labels.shape (%d,)' % count, art.BLUE, 27, True)
        label(painter, 120, 464, 980, 'drop_last=False이므로 마지막의 작은 배치도 보냅니다.', art.MUTED, 26)
    elif name == '16a-1':
        cell_grid(painter, 60, 173, [[1, 2, 4], [0, 3, 5], [2, 1, 6]], 69,
                  highlight=((0, 0), (0, 1), (1, 0), (1, 1)))
        label(painter, 62, 111, 280, '입력의 선택 창', art.BLUE, 28, True)
        cell_grid(painter, 424, 200, [[1, 0], [0, -1]], 69)
        label(painter, 424, 133, 280, '같은 필터', art.PURPLE, 28, True)
        art.arrow(painter, (636, 270), (785, 270), art.ORANGE)
        cell_grid(painter, 830, 236, [[-2]], 84, highlight=((0, 0),))
        label(painter, 805, 155, 270, '첫 출력 위치', art.ORANGE, 28, True)
        label(painter, 130, 453, 980, '1×1 + 2×0 + 0×0 + 3×(−1) = −2', art.PURPLE, 31, True)
    elif name == '16b-31':
        for n in range(19):
            edge = n in (0, 18)
            rectangle(painter, (41 + n * 55, 249, 47, 69), '#ffedd5' if edge else '#ffffff', art.ORANGE if edge else art.BLUE, 3)
        label(painter, 365, 160, 700, '가운데 원래 열일곱 칸', art.BLUE, 29)
        label(painter, 55, 366, 1000, '양 끝의 색칠한 칸을 붙였습니다.', art.ORANGE, 28)
    elif name == '16b-33':
        for x, title, value in ((80, '입력 너비', '19'), (780, '출력 너비', '10')):
            label(painter, x, 155, 270, title, art.BLUE, 29, True)
            rectangle(painter, (x, 231, 250, 86), '#ffffff', art.BLUE)
            label(painter, x + 88, 252, 140, value, art.BLUE, 36, True)
        art.arrow(painter, (376, 274), (724, 274), art.PURPLE)
        label(painter, 370, 184, 390, '창 3 · 간격 2 · 양끝 1', art.PURPLE, 26)
        label(painter, 220, 420, 870, 'floor((19 + 2 − 3) ÷ 2) + 1 = 10', art.PURPLE, 31, True)
        label(painter, 220, 481, 870, '이 그림에서는 너비 축을 계산합니다.', art.MUTED, 25)
    elif name == '16c-33':
        cell_grid(painter, 155, 192, [[1, 2], [5, 8]], 92, highlight=((1, 1),))
        art.arrow(painter, (419, 287), (718, 287), art.ORANGE)
        label(painter, 467, 205, 370, 'MaxPool2d(2,2)', art.PURPLE, 29)
        cell_grid(painter, 795, 241, [[8]], 92, highlight=((0, 0),))
        label(painter, 145, 453, 900, '공간 2×2의 최댓값을 출력 한 칸에 남깁니다.', art.MUTED, 28)
    elif name == '16d-31':
        label(painter, 87, 134, 990, '처음에는 여덟 칸이 있습니다.', size=30)
        strip(painter, 88, 252, 4, 86, active=range(4))
        strip(painter, 638, 252, 4, 86)
        label(painter, 84, 410, 990, '같은 크기의 두 묶음으로 나누었습니다.', art.MUTED, 29)
    elif name == '16d-33':
        label(painter, 80, 124, 990, '두 번 풀링한 뒤 배치마다 따로 펼칩니다.', size=29)
        for row in range(3):
            for col in range(6): rectangle(painter, (250 + col * 75, 214 + row * 64, 63, 48), '#ffffff', art.PURPLE, 3)
            label(painter, 743, 217 + row * 64, 330, '… 특징 48개', art.PURPLE, 26)
        label(painter, 45, 263, 200, '배치 3개', art.BLUE, 27, True)
        label(painter, 272, 462, 790, 'y.shape = (3, 48)', art.PURPLE, 34, True)
    elif name == '17a-33':
        for row, vals in enumerate(([2, 4, 7, 8, 9], [2, 4, 7, 8])):
            label(painter, 65, 194 + row * 150, 270, '원래 번호' if row == 0 else '남긴 번호', art.BLUE, 29, True)
            cell_grid(painter, 328, 183 + row * 150, [vals], 88)
        art.line(painter, (692, 192), (753, 258), art.RED, 4)
        art.line(painter, (692, 258), (753, 192), art.RED, 4)
        label(painter, 65, 489, 990, '맨 뒤의 9는 최대 길이 밖에 있어 제외합니다.', art.MUTED, 28)
    elif name == '17c-33':
        label(painter, 60, 122, 1000, '층 2 × 방향 2를 첫 축 4로 묶습니다.', art.PURPLE, 31, True)
        for n, (title, value) in enumerate((('층×방향', '4'), ('배치', '3'), ('은닉 길이', '6'))):
            x = 92 + n * 350
            label(painter, x, 228, 315, title, art.BLUE, 28, True)
            rectangle(painter, (x, 297, 260, 86), '#ffffff', art.PURPLE)
            label(painter, x + 95, 319, 140, value, art.PURPLE, 36, True)
        label(painter, 245, 459, 840, 'h_n.shape = (4, 3, 6)', art.PURPLE, 32, True)
    painter.end()
    return image


def main():
    parser = argparse.ArgumentParser(description='검토에서 지정한 그림만 보완합니다.')
    parser.add_argument('--only', nargs='+', choices=list(CASES), required=True)
    parser.add_argument('--pillow-site')
    args = parser.parse_args()
    if args.pillow_site: sys.path.append(args.pillow_site)
    from PIL import Image
    app = QApplication.instance() or QApplication([])
    for name in ('NanumGothic-Regular.ttf', 'NanumGothic-Bold.ttf', 'D2Coding-Regular.ttf'):
        fid = QFontDatabase.addApplicationFont(str(ROOT / 'gui/fonts' / name))
        assert fid >= 0
        art.FONTS['code' if name.startswith('D2') else 'body'] = QFontDatabase.applicationFontFamilies(fid)[0]
    assert (1 + 3 + 5 + 7) / 4 == 4 and 10 - .1 * 2 == 9.8
    assert min(4, (11 - 1) // 3) == 3 and (19 + 2 - 3) // 2 + 1 == 10
    assert 12 * (8 // 2 // 2) ** 2 == 48 and (2 * 2, 3, 6) == (4, 3, 6)
    manifest_path = ROOT / 'tools/ai_art/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name in args.only:
        number = int(name.split('a')[0]) if 'a' in name.split('-')[0] else int(''.join(c for c in name.split('-')[0] if c.isdigit()))
        path = ROOT / ('ai/learn/l%02d/assets/%s.png' % (number, name))
        image = picture(name).convertToFormat(art.QImage.Format.Format_RGBA8888)
        if name != '16a-1':
            scaled = image.scaled(1040, 560, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image = art.QImage(1040, 560, art.QImage.Format.Format_RGBA8888)
            image.fill(QColor('#ffffff'))
            painter = art.QPainter(image)
            painter.drawImage((1040 - scaled.width()) // 2, (560 - scaled.height()) // 2, scaled)
            painter.end()
        raw = Image.frombytes('RGBA', (image.width(), image.height()), image.constBits().asstring(image.sizeInBytes())).convert('RGB')
        raw.quantize(colors=64).save(path)
        assert path.stat().st_size <= 150 * 1024
        manifest['files'][path.relative_to(ROOT / 'ai').as_posix()] = {
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'script': 'tools/ai_art/level_repairs_qt.py', 'fn': name}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n')
    assert not any(name in sys.modules for name in ('torch', 'numpy', 'matplotlib'))
    return app


if __name__ == '__main__':
    main()
