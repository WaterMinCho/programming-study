"""추적과 광학 흐름의 입력·좌표·출력 모양을 직접 그린 계산 도식임."""
from functools import lru_cache
from math import cos, sin, radians, hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tools.ai_art import FONTS, ROOT, figure, figures, image_problems, save
from tools.ai_art.al01 import font
from tools.ai_art.application_vision import W, H, INK, BLUE, PALE, LINE, PURPLE

MUTED, FAINT, GREEN = '#6b7280', '#f3f4f6', '#059669'

CAPTIONS = {
    'a4a-1': '6×8 영상에서 2×3 템플릿을 비교하면 점수맵은 5×6입니다. 최고점 (4, 1)은 템플릿의 좌상단입니다.',
    'a4a-2': 'matchTemplate의 입력 크기와 점수맵 모양, 최고점에서 얻는 사각형 좌표를 연결합니다.',
    'a4a-3': '최고점에 템플릿의 너비 3과 높이 2를 더하면 우하단 경계는 (7, 3)입니다.',
    'a4b-1': '그림자 검출을 켠 MOG2의 기본 마스크 값은 배경 0, 그림자 127, 전경 255입니다.',
    'a4b-2': '마스크 [0, 127, 255]에서 mask == 255를 쓰면 전경에 해당하는 마지막 값만 선택합니다.',
    'a4b-3': 'mask > 0은 그림자 127도 선택합니다. 전경만 필요하면 mask == 255로 고릅니다.',
    'a4c-1': 'HSV 관심 영역의 색상 빈도 [1, 3, 0, 2]를 역투영한 뒤 MeanShift가 고정 크기의 창 위치를 갱신합니다.',
    'a4c-2': 'x=[0, 1, 2]의 가중치가 [1, 2, 1]이면 가중 중심은 1입니다. 창의 너비와 높이는 유지합니다.',
    'a4c-3': '화면 경계에서 잘린 ROI는 요청한 너비·높이와 다를 수 있습니다. 실제 ROI 크기로 초기 창을 맞춥니다.',
    'a4d-1': 'CamShift의 회전 사각형은 중심·크기·각도이며 다음 추적 창은 x·y·너비·높이입니다.',
    'a4d-2': 'CamShift 반환값의 회전 사각형과 다음 track_window를 나눠 받습니다.',
    'a4d-3': 'uint8 점수 [100, 200]에 255를 곱하면 [156, 56]으로 바뀝니다. 비트 마스크는 [100, 200]을 보존합니다.',
    'a4e-1': 'LK에서 점 (10, 20)이 (13, 24)로 옮겨가면 변위는 오른쪽 3, 아래 4입니다.',
    'a4e-2': 'status=[1, 0, 1]로 점을 고르면 두 점이 남습니다. 다음 입력은 (2, 1, 2) 모양으로 만듭니다.',
    'a4e-3': '성공한 점만 다음 프레임으로 전달합니다. 전부 잃으면 현재 프레임에서 특징점을 다시 찾습니다.',
    'a4f-1': 'Farneback은 높이 3, 너비 4인 영상의 각 위치에 (dx, dy)를 저장해 (3, 4, 2) 흐름을 만듭니다.',
    'a4f-2': 'flow[y, x]에서 (dx, dy)를 읽고 끝점을 (x+dx, y+dy)로 계산합니다.',
    'a4f-3': '전체 위치의 흐름 중 일부 화살표만 그려도 Farneback의 밀집 흐름 계산은 유지됩니다.',
    'a4g-1': 'RAFT는 RGB 영상 쌍 N×3×H×W에서 N×2×H×W 흐름을 반복 갱신하며 추론 중 가중치는 바꾸지 않습니다.',
    'a4g-2': 'RAFT 전처리는 입력 값 0, 0.5, 1을 -1, 0, 1로 바꿉니다. 입력 두 장에 같은 전처리를 적용합니다.',
    'a4g-3': 'torchvision flow_to_image에서 변위가 (0, 0)이면 흰색입니다. 방향색만으로 변위 크기를 읽지 않습니다.',
    'a4a-41': '6×8 영상 위에서 같은 크기의 2×3 템플릿을 옮기며 위치를 비교합니다.',
    'a4a-42': '템플릿이 들어갈 좌상단 위치는 세로 5개·가로 6개여서 점수맵은 5×6입니다.',
    'a4a-43': 'SQDIFF 계열은 최솟값, CCOEFF 계열은 최댓값에 해당하는 위치를 선택합니다.',
    'a4e-41': '이전 점 (10, 20)과 다음 점 (13, 24)을 같은 점으로 연결합니다.',
    'a4e-42': '변위 (3, 4)의 직선 길이는 5입니다. 가로와 세로 이동량의 합 7과 구분합니다.',
    'a4e-43': 'status=[1, 0, 1]로 이전 점과 다음 점에서 같은 두 대응점을 고릅니다.',
    'a4g-41': '두 사진에서 같은 장면 위치를 짝짓고 첫 사진에서 다음 사진으로 옮겨 간 위치를 읽습니다.',
    'a4g-42': '입력 0, 0.5, 1을 같은 선형식 2x-1에 넣으면 -1, 0, 1입니다.',
    'a4g-43': '영상 쌍은 각각 1×3×136×160이며 마지막 흐름은 1×2×136×160입니다. 추론 가중치는 고정합니다.',
}

FRAME_DESCRIPTIONS = {
    'a4a-1': (
        '높이 6·너비 8인 영상과 높이 2·너비 3인 템플릿을 확인합니다.',
        '템플릿 좌상단이 놓일 위치는 세로 5개·가로 6개입니다.',
        '점수맵 최고점 (4, 1)을 좌상단으로 두고 우하단 경계 (7, 3)을 구합니다.'),
    'a4b-1': (
        'MOG2 마스크는 기본값에서 배경 0·그림자 127·전경 255를 표시합니다.',
        'mask > 0으로 고르면 그림자와 전경이 모두 남습니다.',
        'mask == 255로 고르면 그림자를 제외한 전경만 남습니다.'),
    'a4c-1': (
        '잘라 낸 ROI를 HSV로 바꾸고 색상 구간의 빈도 [1, 3, 0, 2]를 셉니다.',
        '새 프레임의 각 색상 구간에 해당 빈도를 돌려주어 역투영 점수맵을 만듭니다.',
        'MeanShift는 점수의 가중 중심을 따라 창을 옮기며 너비와 높이를 유지합니다.'),
    'a4d-1': (
        '역투영 점수맵과 현재 x·y·너비·높이 창을 입력합니다.',
        'CamShift가 물체의 중심·크기·각도를 담은 회전 사각형을 반환합니다.',
        '회전 사각형은 표시하고 함께 반환한 x·y·너비·높이 창은 다음 추적에 씁니다.'),
    'a4e-1': (
        '이전 프레임에서 추적할 점 (10, 20)을 고릅니다.',
        '다음 프레임의 대응점 (13, 24)을 연결합니다.',
        '새 좌표에서 이전 좌표를 빼면 변위는 (3, 4)입니다.'),
    'a4f-1': (
        '높이 3·너비 4의 모든 위치에 흐름을 담을 칸을 둡니다.',
        '각 위치는 가로 변위 dx와 세로 변위 dy를 함께 저장합니다.',
        'flow[y, x]=(dx, dy)를 읽어 (x+dx, y+dy)에 화살표 끝을 놓습니다.'),
    'a4g-1': (
        '같은 크기의 RGB 영상 쌍을 각각 N×3×H×W 모양으로 준비합니다.',
        '추론에서 흐름을 반복 갱신하며 모델의 가중치는 유지합니다.',
        '반복 결과 중 마지막 N×2×H×W 흐름을 선택합니다. 역전파 학습은 수행하지 않습니다.'),
}


@lru_cache(maxsize=None)
def mono(size=28):
    return ImageFont.truetype(str(Path(FONTS) / 'D2Coding-Regular.ttf'), size)


def text(d, xy, value, size=32, color=INK, bold=False, code=False):
    value = str(value)
    face = mono(size) if code else font(size, bold)
    x, y = xy
    bounds = d.textbbox((x, y), value, font=face, anchor='lt')
    assert bounds[0] >= 40 and bounds[1] >= 28, (value, bounds)
    assert bounds[2] <= W-40 and bounds[3] <= H-28, (value, bounds)
    d.text((x, y), value, font=face, fill=color, anchor='lt')


def centered(d, bounds, value, size=32, color=INK, bold=True, code=False):
    x, y, w, h = bounds
    face = mono(size) if code else font(size, bold)
    value = str(value)
    bb = d.textbbox((0, 0), value, font=face, anchor='lt')
    assert bb[2] <= w-20 and bb[3] <= h-12, (value, bb, bounds)
    text(d, (x+(w-bb[2])/2, y+(h-bb[3])/2), value, size, color, bold, code)


def box(d, bounds, value, fill=PALE, size=32, color=INK, code=False):
    x, y, w, h = bounds
    d.rounded_rectangle((x, y, x+w, y+h), 14, fill=fill, outline=LINE, width=2)
    centered(d, bounds, value, size, color, code=code)


def lines(d, xy, values, size=30, gap=18, color=INK, code=False):
    x, y = xy
    for i, value in enumerate(values):
        text(d, (x, y+i*(size+gap)), value, size, color, code=code)


def base(title, note, stage=None, labels=('입력', '처리', '결과')):
    image = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((24, 24, W-24, H-24), 24, outline=LINE, width=2)
    text(d, (52, 43), 'AI 응용 · 움직임과 추적', 26, BLUE, True)
    text(d, (52, 88), title, 38, bold=True)
    if stage is not None:
        for i, label in enumerate(labels):
            x = 52+i*344
            box(d, (x, 146, 328, 42), f'{i+1}  {label}',
                PALE if i == stage else FAINT, 25, BLUE if i == stage else MUTED)
            if i == stage:
                d.line((x+14, 186, x+314, 186), fill=BLUE, width=3)
    text(d, (52, 542), note, 26, MUTED)
    return image, d


def arrow(d, start, end, color=BLUE, width=5):
    x, y = start
    u, v = end
    d.line((x, y, u, v), fill=color, width=width)
    length = hypot(u-x, v-y)
    if not length:
        return
    dx, dy = (u-x)/length, (v-y)/length
    d.polygon([(u, v), (u-15*dx+7*dy, v-15*dy-7*dx),
               (u-15*dx-7*dy, v-15*dy+7*dx)], fill=color)


def grid(d, x, y, rows, cols, cell=42, values=None, marked=None):
    for r in range(rows):
        for c in range(cols):
            bounds = (x+c*cell, y+r*cell, cell, cell)
            selected = (r, c) == marked
            d.rectangle((bounds[0], bounds[1], bounds[0]+cell, bounds[1]+cell),
                        fill=PALE if selected else 'white', outline=LINE, width=2)
            if values is not None:
                centered(d, bounds, values[r][c], 27, BLUE if selected else INK)
            elif selected:
                d.ellipse((bounds[0]+cell/2-6, bounds[1]+cell/2-6,
                           bounds[0]+cell/2+6, bounds[1]+cell/2+6), fill=BLUE)
    if marked is not None:
        r, c = marked
        d.rectangle((x+c*cell+2, y+r*cell+2, x+(c+1)*cell-2, y+(r+1)*cell-2),
                    outline=BLUE, width=4)


def code_panel(d, x, y, w, h, title, source):
    d.rounded_rectangle((x, y, x+w, y+h), 14, fill=FAINT, outline=LINE, width=2)
    text(d, (x+20, y+20), title, 30, BLUE, True)
    for i, line in enumerate(source):
        assert d.textlength(line, font=mono(27)) <= w-40, (line, w)
        text(d, (x+20, y+72+i*41), line, 27, code=True)


def animation(draw):
    return [draw(stage) for stage in range(3)], [1800]*3


def video_grid(d, x=72, y=234, cell=39, mark=True):
    grid(d, x, y, 6, 8, cell)
    # 위치 설명용 템플릿의 모양을 영상 안에도 같은 크기로 그림.
    for r, row in enumerate(((1, 0, 1), (0, 1, 0))):
        for c, value in enumerate(row):
            if value:
                xx, yy = x+(c+4)*cell, y+(r+1)*cell
                d.rectangle((xx+6, yy+6, xx+cell-6, yy+cell-6), fill=BLUE)
    if mark:
        d.rectangle((x+4*cell, y+cell, x+7*cell, y+3*cell), outline=PURPLE, width=4)


def template_scene(stage):
    image, d = base('템플릿 좌상단마다 점수 하나를 놓습니다',
                    '높이×너비 순서 · 좌상단 원점의 위치 도식입니다.', stage,
                    ('영상과 템플릿', '점수맵 5×6', '최고점 좌표'))
    text(d, (72, 204), '영상 6×8', 30, BLUE, True)
    video_grid(d, mark=stage == 2)
    if stage == 0:
        text(d, (568, 215), '템플릿 2×3', 32, BLUE, True)
        grid(d, 568, 270, 2, 3, 65)
        for r, row in enumerate(((1, 0, 1), (0, 1, 0))):
            for c, value in enumerate(row):
                if value:
                    d.rectangle((578+c*65, 280+r*65, 623+c*65, 325+r*65), fill=BLUE)
        text(d, (568, 438), '같은 크기로 겹쳐 봅니다.', 30)
    else:
        text(d, (568, 204), '점수맵 5×6', 30, BLUE, True)
        grid(d, 568, 250, 5, 6, 40, marked=(1, 4) if stage == 2 else None)
        if stage == 1:
            lines(d, (850, 264), ['6-2+1 = 5', '8-3+1 = 6'], 28, code=True)
        else:
            lines(d, (850, 258), ['최고점', '(x=4, y=1)', '우하단 경계', '(7, 3)'], 28, gap=18)
    text(d, (72, 492), ['비교할 무늬의 높이는 2, 너비는 3입니다.',
                        '각 칸은 원본 영상의 템플릿 좌상단에 대응합니다.',
                        '(4+3, 1+2) = (7, 3)'][stage], 30, BLUE, True)
    assert (6-2+1, 8-3+1) == (5, 6) and (4+3, 1+2) == (7, 3)
    return image


@figure('a4a-1')
def template_matching():
    return animation(template_scene)


@figure('a4a-2')
def template_io():
    image, d = base('입력 크기로 점수맵 크기를 구합니다',
                    'TM_CCOEFF_NORMED 예 · 최고점 좌표는 (x, y)입니다.')
    code_panel(d, 52, 176, 488, 334, '입력과 호출', [
        'image.shape     # (6, 8)', 'template.shape  # (2, 3)',
        'score = cv.matchTemplate(', '    image, template,', '    cv.TM_CCOEFF_NORMED)'])
    code_panel(d, 580, 176, 488, 334, '출력과 좌표', [
        'score.shape  # (5, 6)', 'top_left = (4, 1)',
        'w, h = 3, 2', 'bottom_right = (4+w, 1+h)', '# (7, 3)'])
    return image


@figure('a4a-3')
def template_bounds():
    image, d = base('사각형에는 템플릿의 너비와 높이를 더합니다',
                    '우하단 경계 (7, 3) · 마지막 포함 픽셀 (6, 2)')
    video_grid(d, 92, 202, 43)
    text(d, (92, 480), '좌상단 (4, 1)', 32, BLUE, True)
    box(d, (560, 190, 490, 80), '(4+3, 1+2) = (7, 3)', size=34)
    box(d, (560, 304, 490, 80), '(4+2, 1+3) = (6, 4)', '#fee2e2', 34)
    lines(d, (580, 410), ['위: 너비 3을 x에 더합니다.', '아래: 높이·너비를 바꾼 오류입니다.'], 28)
    return image


def mask_row(d, y, selected=None):
    for i, (value, name) in enumerate(zip((0, 127, 255), ('배경', '그림자', '전경'))):
        x = 92+i*328
        box(d, (x, y, 280, 96), f'{name}  {value}', size=35)
        if selected is not None:
            yes = selected[i]
            box(d, (x, y+123, 280, 66), '선택 1' if yes else '제외 0',
                '#d1fae5' if yes else FAINT, 32)


def mog_scene(stage):
    image, d = base('그림자와 전경을 마스크 값으로 나눕니다',
                    'detectShadows=True · 그림자 값 127은 기본 설정입니다.', stage,
                    ('마스크 값', '> 0 비교', '== 255 비교'))
    mask_row(d, 225, None if stage == 0 else ((False, True, True) if stage == 1 else (False, False, True)))
    text(d, (92, 461), ['mask = [0, 127, 255]', 'mask > 0  →  [0, 1, 1]',
                        'mask == 255  →  [0, 0, 1]'][stage], 35, BLUE, True)
    assert [int(v == 255) for v in (0, 127, 255)] == [0, 0, 1]
    return image


@figure('a4b-1')
def mog2_mask():
    return animation(mog_scene)


@figure('a4b-2')
def mog2_io():
    image, d = base('전경 255에 해당하는 위치만 고릅니다',
                    '비교 결과를 uint8로 바꿔 255를 곱합니다.')
    code_panel(d, 52, 176, 1016, 172, '프레임에서 전경 선택까지', [
        'mask = mog.apply(frame)', 'fg = (mask == 255).astype("uint8") * 255'])
    for i, value in enumerate(('입력 [0, 127, 255]', '선택 [0, 0, 1]', '출력 [0, 0, 255]')):
        box(d, (52+i*344, 395, 328, 90), value, size=27)
    return image


@figure('a4b-3')
def mog2_shadow_comparison():
    image, d = base('0보다 큰 값에는 그림자 127도 들어갑니다',
                    '입력 마스크 [0, 127, 255] · 같은 순서의 위치를 비교합니다.')
    for y, label, values, note, fill in (
            (184, 'mask > 0', [0, 1, 1], '그림자 포함', '#fee2e2'),
            (353, 'mask == 255', [0, 0, 1], '전경만 선택', '#d1fae5')):
        box(d, (52, y, 330, 100), label, fill, 32, code=True)
        grid(d, 442, y, 1, 3, 92, values=[values])
        text(d, (778, y+31), note, 32, bold=True)
    assert [int(v > 0) for v in (0, 127, 255)] == [0, 1, 1]
    return image


def histogram(d, x, y, counts=(1, 3, 0, 2), scale=45):
    for i, value in enumerate(counts):
        xx = x+i*102
        d.rectangle((xx, y+150-value*scale, xx+64, y+150), fill=PALE, outline=BLUE, width=2)
        text(d, (xx+15, y+106-value*scale), value, 31, BLUE, True)
        text(d, (xx+5, y+171), f'구간{i}', 25)


def meanshift_scene(stage):
    image, d = base('색상 빈도로 점수를 만들고 창을 옮깁니다',
                    '계산 도식 · MeanShift는 창의 너비와 높이를 유지합니다.', stage,
                    ('ROI → HSV', '빈도 → 역투영', '고정 크기 창'))
    if stage == 0:
        box(d, (60, 240, 380, 100), 'ROI → HSV 색상', size=33)
        histogram(d, 580, 249)
        text(d, (70, 414), '각 색상 구간을 셉니다.', 32)
        text(d, (580, 475), '빈도 [1, 3, 0, 2]', 31, BLUE, True)
    elif stage == 1:
        histogram(d, 70, 249)
        arrow(d, (490, 333), (555, 333))
        grid(d, 610, 267, 1, 4, 100, values=[[1, 3, 0, 2]])
        text(d, (610, 407), '구간 0 · 1 · 2 · 3', 30)
        text(d, (610, 472), '해당 빈도로 역투영합니다.', 29)
    else:
        box(d, (60, 240, 410, 100), '역투영 점수맵', size=34)
        arrow(d, (492, 290), (552, 290))
        for x, label in ((610, '이전 창'), (830, '옮긴 창')):
            d.rectangle((x, 255, x+170, 395), outline=BLUE, width=4)
            centered(d, (x, 295, 170, 60), label, 29)
        arrow(d, (797, 327), (821, 327))
        text(d, (610, 445), '같은 너비 · 같은 높이', 32, BLUE, True)
        text(d, (70, 415), '가중 중심을 따라 이동합니다.', 30)
    assert sum((1, 3, 0, 2)) == 6
    return image


@figure('a4c-1')
def meanshift_pipeline():
    return animation(meanshift_scene)


@figure('a4c-2')
def meanshift_centroid():
    image, d = base('위치에 점수의 비중을 곱해 중심을 구합니다',
                    '이 점수는 중심 계산용 예입니다. 앞의 색상 빈도와 별개입니다.')
    for i, (x, weight) in enumerate(zip((0, 1, 2), (1, 2, 1))):
        xx = 84+i*151
        box(d, (xx, 189, 126, 82), f'x={x}', size=32)
        box(d, (xx, 306, 126, 82), weight, size=37)
    text(d, (84, 420), '점수 비중: 1 · 2 · 1', 31, BLUE, True)
    code_panel(d, 580, 176, 488, 269, '입력 → 중심', [
        'x = [0, 1, 2]', 'weights = [1, 2, 1]',
        '(0*1 + 1*2 + 2*1) / 4', '# 중심 x = 1'])
    text(d, (580, 480), '창의 너비·높이를 유지합니다.', 29)
    assert sum(x*w for x, w in zip((0, 1, 2), (1, 2, 1)))/4 == 1
    return image


@figure('a4c-3')
def roi_actual_size():
    image, d = base('잘라 낸 ROI의 실제 크기를 확인합니다',
                    'ROI가 비었으면 영역을 다시 고릅니다.')
    d.rectangle((82, 194, 447, 444), fill=FAINT, outline=INK, width=3)
    d.rectangle((340, 322, 492, 474), outline=PURPLE, width=4)
    d.rectangle((340, 322, 447, 444), fill=PALE, outline=BLUE, width=4)
    text(d, (82, 470), '영상 밖은 잘려 나갑니다.', 29)
    code_panel(d, 540, 176, 528, 334, '실제 ROI → 초기 창', [
        'roi = frame[y:y+h, x:x+w]', 'rh, rw = roi.shape[:2]',
        'if rh > 0 and rw > 0:', '    track_window = (', '        x, y, rw, rh)'])
    return image


def rotated_box(d, center=(350, 340), size=(300, 150), angle=-25):
    cx, cy = center
    w, h = size
    a = radians(angle)
    corners = [(cx+u*cos(a)-v*sin(a), cy+u*sin(a)+v*cos(a))
               for u, v in ((-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2))]
    d.polygon(corners, fill=PALE, outline=BLUE, width=4)
    d.ellipse((cx-6, cy-6, cx+6, cy+6), fill=INK)
    return corners


def camshift_scene(stage):
    image, d = base('회전 사각형과 다음 창을 구분합니다',
                    '설명용 도형 · 추적 결과의 각도 수치가 아닙니다.', stage,
                    ('점수맵과 창', '회전 사각형', '다음 추적 창'))
    corners = rotated_box(d)
    if stage != 1:
        xs, ys = zip(*corners)
        d.rectangle((min(xs)-10, min(ys)-10, max(xs)+10, max(ys)+10), outline=PURPLE, width=4)
    lines(d, (70, 490), ['창: x · y · w · h' if stage == 0 else '중심 · 크기 · 각도'], 30, color=BLUE)
    if stage == 0:
        box(d, (625, 245, 400, 85), '역투영 점수맵', size=33)
        box(d, (625, 385, 400, 85), '현재 track_window', size=31)
    elif stage == 1:
        lines(d, (625, 247), ['rotated_rect', '중심 (cx, cy)', '크기 (rw, rh)', '회전 각도 angle'], 32, gap=22)
    else:
        box(d, (625, 236, 400, 85), '표시: 회전 사각형', size=31)
        box(d, (625, 377, 400, 85), '다음 창: (x, y, w, h)', '#ede9fe', 30)
    return image


@figure('a4d-1')
def camshift_returns():
    return animation(camshift_scene)


@figure('a4d-2')
def camshift_io():
    image, d = base('CamShift 반환값은 모양과 쓰임이 다릅니다',
                    '회전 사각형 중심과 창의 좌상단을 구분합니다.')
    code_panel(d, 52, 176, 1016, 176, '입력 → 반환값 분리', [
        'rotated_rect, track_window = cv.CamShift(',
        '    backproject, track_window, criteria)'])
    box(d, (52, 395, 488, 105), '(cx, cy), (rw, rh), angle', size=29, code=True)
    box(d, (580, 395, 488, 105), '(x, y, w, h)', '#ede9fe', 32, code=True)
    text(d, (72, 362), '물체 표시용 회전 사각형', 27, BLUE, True)
    text(d, (600, 362), '다음 호출의 추적 창', 27, PURPLE, True)
    return image


@figure('a4d-3')
def uint8_mask_comparison():
    image, d = base('uint8 점수에 255를 곱하면 값이 바뀝니다',
                    'uint8 곱셈은 256으로 나눈 나머지를 저장합니다.')
    code_panel(d, 52, 176, 488, 240, '점수 × 마스크 255', [
        'scores # uint8: [100, 200]', 'scores * 255  # uint8', '# [156, 56]'])
    code_panel(d, 580, 176, 488, 240, '비트 마스크 255', [
        'cv.bitwise_and(', '    scores, scores,', '    mask=mask) # [100, 200]'])
    box(d, (52, 445, 488, 65), '곱셈: 점수 변경', '#fee2e2', 31)
    box(d, (580, 445, 488, 65), '선택: 원래 점수 보존', '#d1fae5', 31)
    assert [(v*255) % 256 for v in (100, 200)] == [156, 56]
    assert [v & 255 for v in (100, 200)] == [100, 200]
    return image


def lk_scene(stage):
    image, d = base('좌표의 차이가 점의 변위입니다',
                    'x는 오른쪽, y는 아래로 증가합니다. 단위는 픽셀입니다.', stage,
                    ('이전 점', '대응점', '변위 (3, 4)'))
    x, y, step = 115, 252, 45
    for r in range(5):
        for c in range(4):
            d.ellipse((x+c*step-3, y+r*step-3, x+c*step+3, y+r*step+3), fill=LINE)
    d.ellipse((x-9, y-9, x+9, y+9), fill=BLUE)
    text(d, (72, 210), '이전 (10, 20)', 31, BLUE, True)
    if stage > 0:
        arrow(d, (x, y), (x+3*step, y+4*step))
        d.ellipse((x+3*step-9, y+4*step-9, x+3*step+9, y+4*step+9), fill=PURPLE)
        text(d, (72, 474), '다음 (13, 24)', 31, PURPLE, True)
    if stage == 2:
        arrow(d, (x, y), (x+3*step, y), MUTED, 3)
        arrow(d, (x+3*step, y), (x+3*step, y+4*step), MUTED, 3)
    lines(d, (540, 246), [
        ['이전 프레임의 점', 'x=10 · y=20'],
        ['다음 프레임의 대응점', 'x=13 · y=24'],
        ['dx = 13-10 = 3', 'dy = 24-20 = 4', '오른쪽 3 · 아래 4']][stage], 35, gap=28)
    assert (13-10, 24-20) == (3, 4)
    return image


@figure('a4e-1')
def lk_displacement():
    return animation(lk_scene)


@figure('a4e-2')
def lk_status_io():
    image, d = base('추적에 성공한 점만 다음 입력으로 만듭니다',
                    '배열 모양 · 점 개수 2 × 점 묶음 1 × 좌표 성분 2')
    code_panel(d, 52, 176, 625, 334, 'status로 고른 뒤 모양 복원', [
        'p1.shape  # (3, 1, 2)', 'status.ravel()  # [1, 0, 1]',
        'good = p1[status.ravel() == 1]', 'p0 = good.reshape(-1, 1, 2)',
        'p0.shape  # (2, 1, 2)'])
    for i, (tag, state) in enumerate(zip('ABC', ('성공 1', '실패 0', '성공 1'))):
        box(d, (739, 189+i*91, 288, 67), f'{tag}  {state}', FAINT if i == 1 else PALE, 32)
    text(d, (739, 475), '다음 입력: 2점', 32, BLUE, True)
    assert sum((1, 0, 1)) == 2
    return image


@figure('a4e-3')
def lk_reacquire():
    image, d = base('점을 전부 잃으면 현재 프레임에서 다시 찾습니다',
                    'p1 또는 status가 없을 때도 실패 경로로 처리합니다.')
    box(d, (52, 279, 270, 110), 'status 확인', size=34)
    arrow(d, (345, 332), (426, 332))
    box(d, (466, 191, 590, 104), '성공점 있음 → 그 점으로 계속 추적', size=31)
    box(d, (466, 386, 590, 104), '성공점 없음 → 특징점 다시 검출', '#ede9fe', 31)
    d.line((405, 332, 405, 243, 446, 243), fill=BLUE, width=4)
    arrow(d, (405, 243), (450, 243))
    d.line((405, 332, 405, 438, 446, 438), fill=PURPLE, width=4)
    arrow(d, (405, 438), (450, 438), PURPLE)
    return image


def flow_grid(d, x, y, cell=73, subset=False, labels=False):
    grid(d, x, y, 3, 4, cell)
    for r in range(3):
        for c in range(4):
            if subset and (r % 2 or c % 2):
                continue
            xx, yy = x+c*cell+20, y+r*cell+24
            arrow(d, (xx, yy), (xx+30, yy+23), BLUE, 3)
            if labels:
                text(d, (x+c*cell+7, y+r*cell+cell-24), 'dx,dy', 21)


def farneback_scene(stage):
    image, d = base('모든 픽셀 위치에 가로·세로 변위를 담습니다',
                    '배열·좌표 도식 · 화살표는 방향 설명용입니다.', stage,
                    ('H=3 · W=4', '성분 2개', '좌표에 변위 더하기'))
    flow_grid(d, 88, 257, 72, labels=stage == 1)
    text(d, (88, 213), '3행 × 4열', 31, BLUE, True)
    if stage == 0:
        lines(d, (580, 250), ['flow.shape = (3, 4, 2)', '높이 · 너비 · 성분 수', '모든 위치에 흐름을 계산합니다.'], 31, gap=28)
    elif stage == 1:
        box(d, (580, 240, 460, 86), 'flow[y, x] = (dx, dy)', size=30, code=True)
        lines(d, (580, 376), ['dx: 가로 변위', 'dy: 세로 변위'], 33)
    else:
        lines(d, (580, 250), ['읽기: flow[y, x]', '시작: (x, y)', '끝: (x+dx, y+dy)'], 34, gap=24)
    assert (3, 4, 2)[-1] == 2 and 3*4 == 12
    return image


@figure('a4f-1')
def farneback_dense():
    return animation(farneback_scene)


@figure('a4f-2')
def farneback_io():
    image, d = base('배열은 y·x 순서로 읽고 좌표는 x·y로 씁니다',
                    '성분은 dx·dy · 배열은 행 y, 열 x 순서입니다.')
    code_panel(d, 52, 176, 1016, 174, '입력 프레임 쌍 → 밀집 흐름', [
        'flow = cv.calcOpticalFlowFarneback(prev, gray, None, ...)',
        'flow.shape  # (3, 4, 2)'])
    box(d, (52, 395, 488, 105), 'dx, dy = flow[y, x]', size=30, code=True)
    arrow(d, (551, 447), (568, 447))
    box(d, (580, 395, 488, 105), '(x+dx, y+dy)', size=33, code=True)
    return image


@figure('a4f-3')
def farneback_display_subset():
    image, d = base('화살표 표시를 줄여도 밀집 계산은 유지됩니다',
                    '표시 위치만 고릅니다. 계산 범위는 유지합니다.')
    text(d, (92, 184), '전체 흐름 계산', 32, BLUE, True)
    text(d, (652, 184), '일부 위치만 표시', 32, BLUE, True)
    flow_grid(d, 92, 243)
    flow_grid(d, 652, 243, subset=True)
    arrow(d, (449, 346), (577, 346))
    text(d, (92, 486), '12곳의 벡터', 30)
    text(d, (652, 486), '계산 결과에서 골라 그립니다.', 29)
    return image


def raft_scene(stage):
    image, d = base('영상 쌍에서 흐름을 반복해서 갱신합니다',
                    '추론 도식 · 가중치를 갱신하는 역전파 학습과 구분합니다.', stage,
                    ('RGB 영상 쌍', '흐름 반복 갱신', '마지막 흐름 선택'))
    if stage == 0:
        for y, label in ((231, '이전 RGB 영상'), (377, '다음 RGB 영상')):
            box(d, (65, y, 410, 100), label, size=33)
            box(d, (620, y, 410, 100), 'N × 3 × H × W', size=35, code=True)
            arrow(d, (502, y+50), (586, y+50))
    elif stage == 1:
        for i, label in enumerate(('흐름 추정', '흐름 갱신', '흐름 갱신')):
            box(d, (64+i*348, 244, 296, 100), label, size=34)
            if i < 2:
                arrow(d, (373+i*348, 294), (396+i*348, 294))
        box(d, (239, 414, 642, 76), '모델 가중치 유지 · 추정 흐름만 갱신', size=30)
    else:
        code_panel(d, 65, 220, 490, 245, '반복 결과에서 마지막 선택', [
            'flows = model(img1, img2)', 'flow = flows[-1]', '# N x 2 x H x W'])
        box(d, (625, 238, 405, 100), 'N × 2 × H × W', size=35, code=True)
        lines(d, (625, 390), ['성분 0: dx', '성분 1: dy'], 34)
    return image


@figure('a4g-1')
def raft_pair_and_iterations():
    return animation(raft_scene)


@figure('a4g-2')
def raft_preprocess_io():
    image, d = base('RGB 입력 범위를 -1부터 1까지 바꿉니다',
                    '계산 예 · 실제 입력 H·W는 8의 배수로 맞춥니다.')
    for i, (before, after) in enumerate(zip(('0', '0.5', '1'), ('-1', '0', '1'))):
        x = 67+i*351
        box(d, (x, 184, 282, 74), before, size=37)
        arrow(d, (x+141, 274), (x+141, 310))
        box(d, (x, 326, 282, 74), after, size=37)
    code_panel(d, 52, 430, 1016, 84, 'x → 2*x-1', [])
    text(d, (420, 451), '입력 두 장에 같은 전처리를 적용합니다.', 29)
    assert [2*x-1 for x in (0, .5, 1)] == [-1, 0, 1]
    return image


@figure('a4g-3')
def raft_zero_flow_color():
    image, d = base('변위가 0인 곳은 흰색으로 표시됩니다',
                    'torchvision flow_to_image의 색상 규칙입니다.')
    d.rounded_rectangle((72, 195, 450, 441), 16, fill='white', outline=INK, width=3)
    centered(d, (92, 220, 338, 60), '(dx, dy) = (0, 0)', 31, code=True)
    centered(d, (92, 330, 338, 70), '흰색', 39)
    text(d, (72, 477), 'RGB = (255, 255, 255)', 29, BLUE, True)
    lines(d, (550, 216), ['방향은 색상에 대응합니다.', '크기는 채도 등에 반영됩니다.', '정규화 범위도 함께 확인합니다.', '흰색을 큰 움직임으로 읽지 않습니다.'], 29, gap=35)
    # rad=0이면 col = 1-rad*(1-col)이므로 모든 채널이 255임.
    assert [int(255*(1-0*(1-c))) for c in (0, .5, 1)] == [255, 255, 255]
    return image


@figure('a4a-41')
def template_beginner():
    image, d = base('입문 · 작은 틀을 영상 안에서 옮깁니다',
                    '틀의 크기는 2행×3열로 유지합니다.')
    video_grid(d, 90, 210, 43)
    d.rectangle((90, 210, 219, 296), outline=INK, width=4)
    arrow(d, (238, 236), (342, 271), PURPLE)
    text(d, (90, 476), '큰 영상: 6행×8열', 33, BLUE, True)
    text(d, (628, 183), '작은 틀: 2행×3열', 33, BLUE, True)
    grid(d, 628, 259, 2, 3, 68)
    for r, row in enumerate(((1, 0, 1), (0, 1, 0))):
        for c, value in enumerate(row):
            if value:
                d.rectangle((640+c*68, 271+r*68, 684+c*68, 315+r*68), fill=BLUE)
    lines(d, (628, 438), ['위치를 바꾸며 비교합니다.', '틀을 늘리거나 줄이지 않습니다.'], 28)
    return image


@figure('a4a-42')
def template_intermediate():
    image, d = base('중급 · 틀이 들어갈 좌상단 위치를 셉니다',
                    '높이와 너비를 각각 계산합니다.')
    text(d, (82, 180), '점수맵', 33, BLUE, True)
    grid(d, 82, 245, 5, 6, 44)
    text(d, (82, 485), '5행 × 6열', 34, BLUE, True)
    box(d, (542, 189, 502, 91), '세로: 6-2+1 = 5', size=36)
    box(d, (542, 321, 502, 91), '가로: 8-3+1 = 6', size=36)
    text(d, (562, 468), 'score.shape = (5, 6)', 32, code=True)
    return image


@figure('a4a-43')
def template_advanced():
    image, d = base('심화 · 비교 방법에 맞춰 극값을 고릅니다',
                    '두 계열의 점수를 같은 크기로 비교하지 않습니다.')
    for x, method, rule, loc, direction in (
            (52, 'SQDIFF 계열', '차이가 작을수록 잘 맞습니다.', 'min_loc', -1),
            (580, 'CCOEFF 계열', '계수가 클수록 잘 맞습니다.', 'max_loc', 1)):
        d.rounded_rectangle((x, 177, x+488, 511), 16, fill=FAINT, outline=LINE, width=2)
        text(d, (x+26, 204), method, 36, BLUE, True)
        text(d, (x+26, 275), rule, 28)
        start, end = ((x+65, 352), (x+65, 440)) if direction < 0 else ((x+65, 440), (x+65, 352))
        arrow(d, start, end, BLUE)
        text(d, (x+115, 364), '최솟값 선택' if direction < 0 else '최댓값 선택', 32, bold=True)
        text(d, (x+115, 435), loc, 34, code=True)
    return image


@figure('a4e-41')
def lk_beginner():
    image, d = base('입문 · 같은 점의 이전과 다음 위치를 잇습니다',
                    '좌표는 가로 x, 세로 y 순서입니다.')
    for x, title, px, py, label in (
            (62, '이전 프레임', 180, 307, '(10, 20)'),
            (622, '다음 프레임', 809, 399, '(13, 24)')):
        d.rounded_rectangle((x, 190, x+432, 505), 16, fill=FAINT, outline=LINE, width=2)
        text(d, (x+28, 218), title, 34, BLUE, True)
        d.line((x+52, 280, x+380, 280), fill=LINE, width=3)
        d.line((x+52, 280, x+52, 465), fill=LINE, width=3)
        d.ellipse((px-13, py-13, px+13, py+13), fill=BLUE)
        text(d, (x+155, 456), label, 34, BLUE, True)
    arrow(d, (513, 347), (597, 347))
    return image


@figure('a4e-42')
def lk_intermediate():
    image, d = base('중급 · 가로 3과 세로 4의 직선 길이는 5입니다',
                    '직선 길이는 가로와 세로 이동량의 합과 다릅니다.')
    p, q, r = (118, 211), (328, 211), (328, 491)
    d.line((*p, *q, *r), fill=MUTED, width=4)
    arrow(d, p, r, BLUE, 6)
    text(d, (203, 165), '가로 3', 32, bold=True)
    text(d, (354, 334), '세로 4', 32, bold=True)
    text(d, (118, 391), '길이 5', 35, BLUE, True)
    box(d, (574, 220, 470, 102), '3² + 4² = 25', size=38)
    box(d, (574, 383, 470, 102), '√25 = 5', size=38)
    assert 3*3+4*4 == 25 and hypot(3, 4) == 5
    return image


@figure('a4e-43')
def lk_advanced():
    image, d = base('심화 · 이전·다음 점에서 같은 위치를 고릅니다',
                    '한 번 만든 keep을 두 배열에 같이 적용합니다.')
    for i, (name, status) in enumerate(zip('ABC', (1, 0, 1))):
        x = 224+i*280
        box(d, (x, 184, 240, 66), f'{name} · status {status}', size=28)
        for y, prefix in ((290, '이전'), (403, '다음')):
            box(d, (x, y, 240, 70), f'{prefix} {name}', PALE if status else FAINT, 32)
        if not status:
            for y in (290, 403):
                d.line((x+17, y+12, x+223, y+58), fill=INK, width=3)
                d.line((x+223, y+12, x+17, y+58), fill=INK, width=3)
    text(d, (52, 311), 'p0', 34, code=True)
    text(d, (52, 424), 'p1', 34, code=True)
    text(d, (224, 495), 'keep = [True, False, True]  →  A·C', 29, code=True)
    assert [k for k, ok in zip('ABC', (1, 0, 1)) if ok] == ['A', 'C']
    return image


@figure('a4g-41')
def raft_beginner():
    image, d = base('입문 · 두 사진에서 같은 장면 위치를 찾습니다',
                    '장면 위치가 옮겨가면 사진 안의 좌표도 바뀝니다.')
    for x, label, center in ((62, '첫 사진', (220, 367)), (622, '다음 사진', (844, 319))):
        d.rounded_rectangle((x, 190, x+432, 508), 16, fill=FAINT, outline=LINE, width=2)
        text(d, (x+24, 216), label, 34, BLUE, True)
        cx, cy = center
        d.rectangle((x+24, 295, x+408, 477), outline=LINE, width=2)
        d.polygon(((cx, cy-39), (cx+41, cy+30), (cx-41, cy+30)),
                  fill=PALE, outline=BLUE, width=4)
        text(d, (x+260, 449), '같은 점', 28, BLUE, True)
        d.ellipse((cx-6, cy-6, cx+6, cy+6), fill=INK)
    arrow(d, (263, 363), (794, 321), PURPLE, 4)
    return image


@figure('a4g-42')
def raft_intermediate():
    image, d = base('중급 · 같은 식으로 입력 값을 바꿉니다',
                    '0부터 1까지의 값을 -1부터 1까지 옮깁니다.')
    for i, (before, expr, after) in enumerate((('0', '2×0-1', '-1'),
                                             ('0.5', '2×0.5-1', '0'),
                                             ('1', '2×1-1', '1'))):
        y = 187+i*108
        box(d, (70, y, 185, 75), before, size=36)
        arrow(d, (279, y+38), (353, y+38))
        box(d, (378, y, 348, 75), expr, FAINT, 34)
        arrow(d, (750, y+38), (824, y+38))
        box(d, (848, y, 185, 75), after, size=36)
    assert [2*x-1 for x in (0, .5, 1)] == [-1, 0, 1]
    return image


@figure('a4g-43')
def raft_advanced():
    image, d = base('심화 · 공간 크기를 유지하며 흐름을 만듭니다',
                    '136과 160은 8의 배수입니다. 가중치는 고정합니다.')
    for i, label in enumerate(('첫 RGB 영상', '다음 RGB 영상')):
        y = 182+i*112
        text(d, (68, y), label, 28, BLUE, True)
        box(d, (68, y+37, 390, 61), '1×3×136×160', size=32, code=True)
    arrow(d, (482, 299), (574, 299))
    box(d, (602, 224, 445, 100), '1×2×136×160', size=36, code=True)
    text(d, (602, 364), '마지막 흐름의 성분은 dx·dy입니다.', 28)
    box(d, (235, 449, 650, 66), '반복 추론 · 고정 가중치 · 학습 없음', size=30)
    assert 136 % 8 == 160 % 8 == 0
    assert (1, 3, 136, 160)[2:] == (1, 2, 136, 160)[2:]
    return image


def main():
    """등록한 그림만 저장하며 manifest는 변경하지 않음."""
    import sys
    module = sys.modules[__name__]
    registered = figures(module)
    assert {name for name, _, _, _ in registered} == set(CAPTIONS)
    # 모든 배치·계산 검사를 저장 전에 마침.
    rendered = [(name, fn()) for name, _, _, fn in registered]
    out = Path(ROOT) / 'ai' / 'learn' / 'al04' / 'assets'
    for name, result in rendered:
        path = save(name, result, str(out))
        problems = image_problems(path)
        assert not problems, (path, problems)
        with Image.open(path) as image:
            if name.endswith('-1'):
                assert image.n_frames == 3, (name, image.n_frames)
                for stage in range(3):
                    image.seek(stage)
                    assert image.info['duration'] == 1800, (name, stage, image.info)
        print(Path(path).relative_to(ROOT))


if __name__ == '__main__':
    main()
