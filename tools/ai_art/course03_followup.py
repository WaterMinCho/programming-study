"""이진화와 윤곽·모서리·원 검출의 조건을 자체 수치로 그렸음."""
from pathlib import Path

from tools.ai_art import FIXED, ROOT, figure, image_problems, record
from tools.ai_art.al01 import base, box, text

BLUE, INK, MUTED = '#2563eb', '#1f2937', '#6b7280'


@figure('a3f-1')
def binary_values():
    """회색조 세 값과 임계값의 경계 조건을 나눠 그렸음."""
    values = [30, 50, 90]
    outputs = [255 if v > 50 else 0 for v in values]
    assert outputs == [0, 0, 255]
    frames = []
    for stage in range(3):
        image, draw = base('밝기값을 읽은 뒤 두 값으로 나눕니다', '기준 50보다 클 때만 255가 됩니다.')
        text(draw, (70, 170), ['입력: 회색조 값', '판정: 기준 50과 비교', '출력: 두 값으로 선택'][stage], 32, BLUE, True)
        for i, value in enumerate(values):
            x = 90 + i * 340
            show = outputs[i] if stage == 2 else value
            draw.rounded_rectangle((x, 230, x + 240, 350), radius=12,
                                   fill=(show,) * 3, outline='#9ca3af', width=2)
            text(draw, (x + 70, 267), show, 38, 'white' if show < 120 else INK, True)
            label = ['30 < 50', '50 = 50', '90 > 50'][i]
            text(draw, (x + 50, 390), label if stage else '밝기 ' + str(value), 30)
        frames.append(image)
    return frames, [2200] * 3


@figure('a3f-2')
def local_thresholds():
    """두 위치의 평균과 기준·현재 값을 함께 표시함."""
    image, draw = base('위치마다 주변 평균에서 기준을 구합니다', '평균 방식 · C=10 · 현재 값이 기준보다 크면 255입니다.')
    for x, title, mean, value in [(65, '어두운 구역', 80, 75), (585, '밝은 구역', 140, 135)]:
        threshold = mean - 10
        assert value > threshold
        box(draw, (x, 190, 470, 72), title, size=30)
        text(draw, (x + 24, 287), f'평균 {mean} - 10 = 기준 {threshold}', 29)
        text(draw, (x + 24, 350), f'현재 밝기 {value} > {threshold}', 29)
        text(draw, (x + 24, 420), '출력 255', 36, BLUE, True)
    return image


@figure('a3f-3')
def global_histogram():
    """설명용 두 밝기 무리와 전역 선택을 그렸음."""
    image, draw = base('Otsu는 전체 밝기 분포를 살핍니다', '설명용 분포 · 두 무리의 중간값을 유일한 정답으로 정하지 않습니다.')
    draw.line((85, 430, 660, 430), fill=INK, width=3)
    draw.line((85, 210, 85, 430), fill=INK, width=3)
    for x in [180, 200, 220, 490, 510, 530]:
        draw.rectangle((x, 255 if x in [200, 510] else 300, x + 15, 430), fill=BLUE)
    text(draw, (140, 450), '40 근처', 28)
    text(draw, (450, 450), '180 근처', 28)
    text(draw, (100, 170), '밝기별 픽셀 수', 29, BLUE, True)
    box(draw, (725, 235, 300, 95), '전역 기준 선택', size=27)
    text(draw, (750, 370), 'chosen: 선택한 기준', 25)
    text(draw, (750, 420), 'binary: 결과 영상', 25)
    return image


@figure('a3f-4')
def contour_modes():
    """고리의 외곽·구멍과 검색 범위·계층을 구분함."""
    image, draw = base('고리의 외곽과 구멍을 나누어 찾습니다', '점 압축 NONE / SIMPLE은 검색 범위와 따로 고릅니다.')
    draw.rounded_rectangle((80, 190, 470, 465), radius=14, fill=INK)
    draw.ellipse((150, 210, 395, 455), fill='white', outline=BLUE, width=5)
    draw.ellipse((225, 285, 320, 380), fill=INK, outline='#ea580c', width=5)
    text(draw, (535, 210), 'EXTERNAL: 바깥 외곽', 29, BLUE, True)
    text(draw, (535, 285), 'LIST: 외곽과 구멍 경계', 29)
    text(draw, (535, 355), 'TREE: 외곽과 구멍 경계', 29)
    text(draw, (535, 410), '         + 부모·자식 관계', 29)
    return image


@figure('a3g-1')
def corner_windows():
    """계산한 검출 결과가 아닌 밝기 배치의 개념도를 그렸음."""
    frames = []
    labels = ['평탄한 영역: 어느 방향이든 변화가 작습니다.',
              '곧은 경계: 나란히 옮길 때와 가로지를 때를 나눕니다.',
              '모서리: 어느 방향으로 옮겨도 변화가 큽니다.']
    for stage, label in enumerate(labels):
        image, draw = base('작은 창을 옮겨 주변 밝기를 비교합니다', label)
        draw.rectangle((120, 190, 440, 470), fill='#d1d5db', outline=INK, width=2)
        if stage == 1:
            draw.rectangle((280, 190, 440, 470), fill=INK)
        elif stage == 2:
            draw.rectangle((280, 330, 440, 470), fill=INK)
        draw.rectangle((230, 280, 330, 380), outline=BLUE, width=7)
        draw.line((210, 330, 350, 330), fill='#ea580c', width=3)
        draw.line((280, 260, 280, 400), fill='#ea580c', width=3)
        descriptions = [
            ['어느 방향으로 옮겨도', '밝기 변화가 작습니다.'],
            ['경계와 나란히: 변화 작음', '경계를 가로질러: 변화 큼'],
            ['어느 방향으로 옮겨도', '밝기 변화가 큽니다.'],
        ]
        for line, value in enumerate(descriptions[stage]):
            text(draw, (535, 235 + line * 58), value, 28, BLUE, True)
        text(draw, (535, 385), '중심 밝기 하나보다', 30)
        text(draw, (535, 440), '주변 밝기 배치를 봅니다.', 30)
        frames.append(image)
    return frames, [2200] * 3


@figure('a3g-2')
def quality_and_distance():
    """품질 기준과 두 후보의 거리 선택을 계산해 표시함."""
    assert 100 * 0.25 == 25 and 5 - 2 < 4
    image, draw = base('점수와 거리 조건을 차례로 적용합니다', '점수 100·40·20 → 기준 25 → A와 B → 거리 3인 B 제외')
    for x, label, value in [(80, 'A', 100), (400, 'B', 40), (720, 'C', 20)]:
        box(draw, (x, 190, 260, 95), f'{label}: {value}', size=34)
        text(draw, (x + 30, 310), '품질 통과' if value >= 25 else '품질 제외', 29, BLUE if value >= 25 else MUTED)
    text(draw, (100, 390), 'A=(2,2)  ·  B=(5,2)  →  거리 3', 31)
    text(draw, (100, 453), '최소 거리 4: 높은 점수의 A를 남깁니다.', 31, BLUE, True)
    return image


@figure('a3g-3')
def circle_radius():
    """실제 검출을 실행하지 않고 후보 반지름의 조건을 그렸음."""
    image, draw = base('중심 거리와 반지름 범위를 구분합니다', '다른 조건을 통과한 두 후보 · 허용 반지름 5~10')
    for x, radius, label, keep in [(290, 70, '반지름 7', True), (800, 130, '반지름 13', False)]:
        draw.ellipse((x - radius, 310 - radius, x + radius, 310 + radius), outline=BLUE if keep else MUTED, width=5)
        draw.line((x, 310, x + radius, 310), fill='#ea580c', width=4)
        draw.ellipse((x - 5, 305, x + 5, 315), fill=INK)
        text(draw, (x - 100, 465), label + (': 남김' if keep else ': 제외'), 29)
    return image


@figure('a3g-4')
def missing_detection():
    """None 검사 뒤에 개수를 읽는 순서를 그렸음."""
    image, draw = base('결과가 있는지 확인한 뒤 위치를 읽습니다', '미검출을 직전 위치나 새 위치로 바꾸어 기록하지 않습니다.')
    for x, top, bottom in [(80, 'circles is None', 'count = 0'), (600, '원 두 개를 찾음', 'count = 2')]:
        box(draw, (x, 200, 440, 100), top, size=30)
        text(draw, (x + 200, 325), '↓', 38, BLUE)
        box(draw, (x, 385, 440, 95), bottom, size=34)
    return image


def main():
    """새 그림 여덟 개만 저장하고 기존 그림 해시를 유지함."""
    from PIL import Image

    assets = Path(ROOT) / 'ai/learn/al03/assets'
    palette = Image.new('P', (1, 1))
    colors = [tuple(bytes.fromhex(value[1:])) for value in FIXED]
    colors.extend((v, v, v) for v in [0, 30, 50, 90, 255])
    assert len(colors) <= 64
    flat = [v for color in colors for v in color]
    palette.putpalette(flat + [255] * (768 - len(flat)))
    functions = [binary_values, local_thresholds, global_histogram, contour_modes,
                 corner_windows, quality_and_distance, circle_radius, missing_detection]
    for function in functions:
        name = function.ai_figure[0]
        result = function()
        if isinstance(result, tuple):
            images, durations = result
            images = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
            output = assets / (name + '.gif')
            images[0].save(output, save_all=True, append_images=images[1:], duration=durations,
                           loop=0, optimize=False, disposal=1)
        else:
            output = assets / (name + '.png')
            result.quantize(palette=palette, dither=Image.Dither.NONE).save(output, optimize=True)
        assert not image_problems(str(output)), image_problems(str(output))
        print(output.name)
    record('al03', script='tools/ai_art/course03_followup.py')


if __name__ == '__main__':
    main()
