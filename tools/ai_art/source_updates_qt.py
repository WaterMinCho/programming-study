"""16·17차시의 추가 실습을 수치와 흐름으로 그림. 모델은 실행하지 않음."""
import argparse
import hashlib
import json
from pathlib import Path

from PyQt6.QtGui import QColor, QFontDatabase
from PyQt6.QtWidgets import QApplication

from tools.ai_art import FIXED
from tools.ai_art import l01_training_qt as art
from tools.ai_art.lesson_bridges_qt import cube, rectangle

ROOT = Path(__file__).resolve().parents[2]


def heading(painter, title, subtitle):
    art.text(painter, 30, 18, 1060, 44, title, size=30, bold=True)
    art.text(painter, 30, 70, 1060, 36, subtitle, size=23, color=art.MUTED)


def card(painter, x, y, width, title, detail, color=art.BLUE):
    rectangle(painter, (x, y, width, 114), art.PALE, color)
    art.text(painter, x+16, y+12, width-32, 36, title, color, 25, True)
    art.text(painter, x+16, y+58, width-32, 42, detail, size=22)


def cnn_shapes():
    image, p = art.canvas()
    heading(p, '사진 크기·채널·배치를 따로 따라갑니다', '새 예 · RGB 32×32 · 배치 4장 · 숫자 10종 분류')
    sides = [32, 16, 8, 4]
    channels = [3, 32, 64, 128]
    for i, (side, channel) in enumerate(zip(sides, channels)):
        x = 42 + i*275
        width = [120, 96, 76, 60][i]
        cube(p, x+12, 265-width/2, width, width, 3+i, art.BLUE if i == 0 else art.PURPLE)
        art.text(p, x, 348, 250, 40, f'({4}, {channel}, {side}, {side})', size=25, bold=True)
        art.text(p, x, 400, 250, 34, '입력' if i == 0 else f'Conv·ReLU·Pool {i}', size=21)
        if i < 3:
            art.arrow(p, (x+175, 258), (x+245, 258), art.PURPLE)
    assert 128*4*4 == 2048
    card(p, 32, 474, 1056, 'Flatten은 배치 4장을 남깁니다', '(4, 2048) → Linear 256·ReLU → Linear 10 → (4, 10)')
    p.end()
    return image


def hooks():
    image, p = art.canvas()
    heading(p, 'hook은 등록한 모듈의 출력을 관찰합니다', '모양 확인은 학습 파라미터를 갱신하는 단계가 아닙니다.')
    for x, title, detail, color in [(36, 'Conv 모듈', '등록한 hook 호출', art.BLUE),
                                    (398, 'F.relu 함수', '독립 모듈이 아님', art.ORANGE),
                                    (760, 'Pool 모듈', '등록한 hook 호출', art.BLUE)]:
        card(p, x, 174, 324, title, detail, color)
    art.arrow(p, (366, 232), (388, 232), art.GRAY)
    art.arrow(p, (728, 232), (750, 232), art.GRAY)
    for x, title, detail in [(36, '등록', 'handle을 보관합니다'),
                             (398, '순전파', '출력 shape를 읽습니다'),
                             (760, '해제', 'handle.remove()')]:
        card(p, x, 384, 324, title, detail, art.GREEN)
    art.text(p, 36, 526, 1048, 42, '관찰이 끝난 hook을 해제하면 다음 순전파에서 같은 기록을 반복하지 않습니다.', size=23)
    p.end()
    return image


def dropout():
    image, p = art.canvas()
    heading(p, 'Dropout의 가림과 그래프 기록은 따로 제어합니다', '입력 [2, 4, 6, 8] · p=0.5 · 가능한 가림 한 예')
    card(p, 40, 164, 500, 'train · 유지 표시 [1, 0, 1, 0]', '1은 남김 · 0은 가림 · 남은 값은 2배', art.PURPLE)
    card(p, 580, 164, 500, 'eval · 가림을 끕니다', '입력값을 그대로 통과시킵니다.', art.GREEN)
    train_values = [4, 0, 12, 0]
    assert train_values == [2*2, 0, 6*2, 0]
    art.text(p, 64, 310, 440, 70, str(train_values), art.PURPLE, 35, True)
    art.text(p, 604, 310, 440, 70, '[2, 4, 6, 8]', art.GREEN, 35, True)
    card(p, 40, 430, 1040, 'no_grad()는 별도 설정입니다', 'train 상태에서 no_grad()만 써도 Dropout의 가림은 계속 적용됩니다.', art.ORANGE)
    p.end()
    return image


def crop():
    image, p = art.canvas()
    heading(p, 'padding을 양쪽에 붙인 뒤 잘라냅니다', 'RandomCrop(32, padding=4) · 입력 32×32')
    assert 32 + 2*4 == 40
    rectangle(p, (54, 154, 320, 320), art.PALE, art.GRAY)
    rectangle(p, (86, 186, 256, 256), '#ffffff', art.BLUE)
    art.text(p, 108, 288, 220, 44, '원래 32×32', art.BLUE, 27, True)
    art.text(p, 46, 488, 360, 40, '4 + 32 + 4 = 40', size=28, bold=True)
    art.arrow(p, (416, 316), (526, 316), art.GREEN)
    rectangle(p, (578, 154, 320, 320), art.PALE, art.GRAY)
    rectangle(p, (594, 202, 256, 256), '#ffffff', art.GREEN)
    art.text(p, 624, 292, 220, 44, '잘라낸 32×32', art.GREEN, 27, True)
    art.text(p, 584, 488, 490, 40, '40×40 안에서 위치를 골라 자릅니다.', size=24)
    art.text(p, 40, 544, 1040, 32, '좌우 반전 등 다른 변형은 숫자의 라벨이 유지되는지 따로 확인합니다.', size=23)
    p.end()
    return image


def split():
    image, p = art.canvas()
    heading(p, '학습·선택·최종 확인에 쓸 자료를 나눕니다', '테스트 점수로 모델을 고르면 그 자료가 선택 과정에 사용됩니다.')
    for x, title, detail, color in [(38, '학습 자료', '손실 → 기울기 → 갱신', art.BLUE),
                                    (400, '검증 자료', '설정·저장 모델 선택', art.GREEN),
                                    (762, '테스트 자료', '선택이 끝난 뒤 확인', art.ORANGE)]:
        card(p, x, 200, 320, title, detail, color)
    art.arrow(p, (362, 258), (390, 258), art.GRAY)
    art.arrow(p, (724, 258), (752, 258), art.GRAY)
    card(p, 38, 404, 1044, '다음 모델을 고르는 기준은 검증 결과입니다', '최종 테스트 결과를 보고 설정을 반복 변경하면 새 자료의 성능을 과대평가할 수 있습니다.', art.PURPLE)
    p.end()
    return image


def tokens():
    image, p = art.canvas()
    heading(p, '같은 토크나이저에서 만든 번호를 분류기로 보냅니다', '감성 분류의 새 예 · 문장 2개 · 부정 0 / 긍정 1 · 설명용 PAD=0')
    for x, title, detail in [(32, '토큰화', 'input_ids'), (400, '동적 패딩', '배치 최장 길이 5'), (768, '분류 모델', 'logits (2, 2)')]:
        card(p, x, 146, 320, title, detail)
    art.arrow(p, (360, 200), (390, 200), art.BLUE)
    art.arrow(p, (728, 200), (758, 200), art.BLUE)
    values = [[4, 8, 6, 0, 0], [4, 7, 9, 8, 6]]
    masks = [[1, 1, 1, 0, 0], [1, 1, 1, 1, 1]]
    assert sum(masks[0]) == 3 and sum(masks[1]) == 5
    art.text(p, 44, 304, 510, 38, '설명용 번호 · 실제 어휘 번호와 구분', size=24, bold=True)
    for row, values_row in enumerate(values):
        art.text(p, 44, 350+row*48, 510, 42, str(values_row), size=27)
    art.text(p, 598, 304, 490, 38, 'attention_mask · 1은 실제 자리', size=24, bold=True)
    for row, mask_row in enumerate(masks):
        art.text(p, 598, 350+row*48, 490, 42, str(mask_row), size=27)
    card(p, 32, 456, 1056, '정답 labels=[1, 0]은 손실 계산에 사용합니다', '토큰 번호나 attention_mask에 이번 정답을 넣지 않습니다.', art.GREEN)
    p.end()
    return image


def trainer():
    image, p = art.canvas()
    heading(p, 'Trainer가 학습 기본 패턴을 관리합니다', '학습 자료로 가중치를 바꾸고 검증 자료로 바뀐 모델을 확인합니다.')
    for x, title, detail in [(32, '예측', '현재 모델의 logit'), (400, '손실·기울기', '정답과 비교·역전파'), (768, '갱신', 'optimizer가 변경')]:
        card(p, x, 168, 320, title, detail, art.PURPLE)
    art.arrow(p, (360, 226), (390, 226), art.PURPLE)
    art.arrow(p, (728, 226), (758, 226), art.PURPLE)
    card(p, 32, 376, 508, 'train_dataset', '학습할 배치와 정답을 제공합니다.', art.BLUE)
    card(p, 580, 376, 508, 'eval_dataset', '선택에 쓸 검증 배치를 제공합니다.', art.GREEN)
    art.text(p, 32, 530, 1056, 40, '학습 때는 이전 기울기를 초기화합니다. 검증에서는 파라미터를 갱신하지 않습니다.', size=23)
    p.end()
    return image


def checkpoint():
    image, p = art.canvas()
    heading(p, '검증 결과로 저장 모델을 선택합니다', '설명용 기록 · accuracy가 클수록 좋음 · epoch 단위 평가·저장')
    scores = [0.82, 0.86, 0.83]
    assert scores.index(max(scores)) == 1
    for i, value in enumerate(scores):
        x = 94 + i*250
        color = art.PURPLE if i == 1 else art.GRAY
        height = value*240
        rectangle(p, (x, 420-height, 130, height), color, color)
        art.text(p, x, 428, 180, 36, 'epoch %d' % (i+1), size=25)
        art.text(p, x, 420-height-46, 180, 38, '%.2f' % value, size=30, bold=True)
    card(p, 842, 190, 246, '선택 · epoch 2', '검증 0.86', art.PURPLE)
    card(p, 32, 478, 1056, '선택이 끝난 뒤 별도 테스트 자료를 사용합니다', '테스트 점수로 고른 모델을 독립적인 최종 평가로 설명하지 않습니다.', art.GREEN)
    p.end()
    return image


def metrics():
    image, p = art.canvas()
    heading(p, '맞춘 비율과 양성 분류의 균형을 따로 읽습니다', '양성은 1 · TP=2 / TN=4 / FP=1 / FN=1 · 설명용 8개 문장')
    labels = [('실제 양성', ['TP  2', 'FN  1']), ('실제 음성', ['FP  1', 'TN  4'])]
    art.text(p, 166, 138, 215, 40, '예측 양성', size=24, bold=True)
    art.text(p, 398, 138, 215, 40, '예측 음성', size=24, bold=True)
    for row, (name, values) in enumerate(labels):
        art.text(p, 30, 222+row*124, 130, 40, name, size=23)
        for column, value in enumerate(values):
            rectangle(p, (164+column*232, 192+row*124, 210, 110), art.PALE, art.GREEN if row == column else art.ORANGE)
            art.text(p, 192+column*232, 220+row*124, 160, 44, value, size=30, bold=True)
    assert (2+4)/(2+4+1+1) == .75
    assert round(2*2/(2*2+1+1), 3) == .667
    card(p, 672, 180, 416, 'accuracy · 전체 정답 비율', '(2+4) / 8 = 0.75', art.BLUE)
    card(p, 672, 330, 416, 'F1 · 양성 분류의 균형', '4 / (4+1+1) ≈ 0.667', art.PURPLE)
    art.text(p, 38, 526, 1048, 40, '분류 기준과 양성 클래스를 고정해 같은 자료에서 비교합니다.', size=24)
    p.end()
    return image


FIGURES = {'16g-1': cnn_shapes, '16g-2': hooks, '16g-3': dropout, '16g-4': crop, '16g-5': split,
           '17f-1': tokens, '17f-2': trainer, '17f-3': checkpoint, '17f-4': metrics}


def main():
    from PIL import Image
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', nargs='+', choices=FIGURES, required=True)
    opts = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    for name in ('NanumGothic-Regular.ttf', 'NanumGothic-Bold.ttf', 'D2Coding-Regular.ttf', 'D2Coding-Bold.ttf'):
        key = QFontDatabase.addApplicationFont(str(ROOT/'gui/fonts'/name))
        assert key >= 0
        art.FONTS['code' if name.startswith('D2') else 'body'] = QFontDatabase.applicationFontFamilies(key)[0]
    manifest_path = ROOT/'tools/ai_art/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for name in opts.only:
        frame = FIGURES[name]().convertToFormat(art.QImage.Format.Format_RGBA8888)
        rgb = Image.frombytes('RGBA', (art.WIDTH, art.HEIGHT), frame.constBits().asstring(frame.sizeInBytes())).convert('RGB')
        palette = rgb.quantize(colors=64)
        fixed = [channel for color in FIXED for channel in (QColor(color).red(), QColor(color).green(), QColor(color).blue())]
        colors = fixed + palette.getpalette()[:(64-len(FIXED))*3]
        palette.putpalette(colors + [0]*(768-len(colors)))
        target = ROOT/'ai/learn'/('l'+name[:2])/'assets'/(name+'.png')
        rgb.quantize(palette=palette, dither=Image.Dither.NONE).save(target, optimize=True)
        assert target.stat().st_size <= 150*1024
        key = 'learn/l%s/assets/%s.png' % (name[:2], name)
        manifest['files'][key] = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                  'script': 'tools/ai_art/source_updates_qt.py', 'fn': FIGURES[name].__name__}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1)+'\n')
        print(name, target.stat().st_size)
    return app


if __name__ == '__main__':
    main()
