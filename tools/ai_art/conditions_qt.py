"""학습률·장치·배치 정규화의 조건을 Qt로 그림. 모델은 실행하지 않음."""
import argparse
import hashlib
from pathlib import Path
import sys

from tools.ai_art import FIXED, read_manifest, write_manifest
from tools.ai_art import l01_training_qt as draw
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QFontDatabase, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[2]


def learning_rates():
    """같은 이차 손실에 학습률 세 개를 적용한 수치를 그림."""
    paths = []
    for rate in (0.01, 0.1, 0.3):
        values = [2.0]
        for _ in range(4):
            values.append(values[-1] - rate * (8 * values[-1] - 20))
        paths.append(values)
    assert abs(paths[1][-1] - 2.4992) < 1e-12 and paths[1][-1] != 2.5
    frames = []
    for frame in range(6):
        image, painter = draw.canvas()
        draw.text(painter, 20, 12, 1080, 44, '학습률이 다르면 같은 모델의 갱신 경로도 달라집니다', size=30, bold=True)
        draw.text(painter, 20, 62, 1080, 36, '손실 L=(2w−5)² · 기울기 8w−20 · 시작 w=2 · %d번 갱신' % min(frame, 4), size=24)
        for column, (rate, values) in enumerate(zip((0.01, 0.1, 0.3), paths)):
            x, y, width, height = 52 + 366 * column, 150, 302, 270
            draw.text(painter, x, 108, width, 34, '학습률 %s' % rate, size=26, bold=True)
            def point(w, loss):
                return (x + width * w / 4.4, y + height * (1 - loss / 16))
            for loss in (0, 5, 10, 15):
                draw.line(painter, point(0, loss), point(4.4, loss), draw.GRID)
                draw.text(painter, x, point(0, loss)[1]-24, 46, 24, str(loss), size=18, color=draw.MUTED)
            curve = QPainterPath(QPointF(*point(0, 25)))
            painter.save();painter.setClipRect(QRectF(x, y, width, height))
            for index in range(1, 221):
                w = index * 4.4 / 220
                curve.lineTo(QPointF(*point(w, (2*w-5)**2)))
            painter.setPen(QPen(QColor(draw.MUTED), 2));painter.drawPath(curve)
            draw.line(painter, point(2.5, 0), point(2.5, 16), draw.GRAY, dashed=True)
            shown = values[:min(frame, 4)+1]
            for a, b in zip(shown, shown[1:]):
                draw.line(painter, point(a,(2*a-5)**2), point(b,(2*b-5)**2), draw.GREEN, 3)
            for w in shown:draw.dot(painter,point(w,(2*w-5)**2),draw.GREEN)
            painter.restore()
            draw.line(painter,point(0,0),point(4.4,0),draw.INK)
            for tick in (0, 1, 2, 4):draw.text(painter, point(tick,0)[0], 424, 22, 25, str(tick), size=18)
            w = shown[-1];loss = (2*w-5)**2
            draw.text(painter,x,460,width,34,'w = %.4f' % w,size=24,color=draw.GREEN,bold=True)
            value = '0.0001 미만' if loss<0.0001 else '%.4f' % loss
            draw.text(painter,x,500,width,32,'손실 '+value,size=22)
            if frame==5:
                draw.text(painter,x,550,width,34,('느리게 가까워짐','최적점에 가까워짐','최적점에서 멀어짐')[column],size=22,bold=True)
        painter.end();frames.append(image)
    return frames


def device_transfer():
    """CUDA 가용성과 텐서 반환값을 구분함."""
    frames=[]
    rows=[('CUDA를 사용할 수 있으면 cuda를 고릅니다','','','CUDA 사용 가능 여부를 검사합니다.'),
          ('텐서는 처음에 CPU에 있습니다','x: [1, 2, 3]','','x = torch.tensor([1., 2., 3.])'),
          ('반환값을 받지 않으면 x는 CPU에 남습니다','x: 원본','옮긴 사본','x.to(device)'),
          ('반환값을 받으면 x가 CUDA 텐서를 가리킵니다','원본','x: 옮긴 사본','x = x.to(device)'),
          ('CUDA를 사용할 수 없으면 CPU를 고릅니다','x: [1, 2, 3]','','같은 장치·자료형이면 to()가 원래 텐서를 반환할 수 있습니다.'),
          ('장치를 고른 뒤 반환값을 받습니다','기존 장치','선택한 장치','모델과 입력을 같은 장치로 맞춥니다.')]
    code='device = torch.device("cuda" if torch.cuda.is_available() else "cpu")'
    for index,(title,cpu,gpu,note) in enumerate(rows):
        image,painter=draw.canvas()
        draw.text(painter,20,12,1080,44,title,size=30,bold=True)
        draw.text(painter,20,68,1080,42,code,size=22,mono=True)
        for x,label,value,color in ((40,'CPU',cpu,draw.MUTED),(610,'CUDA 장치' if index!=4 else 'CUDA 사용 불가',gpu,draw.PURPLE)):
            painter.setPen(QPen(QColor(color),3));painter.setBrush(QColor('white'))
            painter.drawRoundedRect(QRectF(x,150,470,280),16,16)
            draw.text(painter,x+24,166,422,44,label,size=28,bold=True,color=color)
            draw.text(painter,x+24,270,422,52,value,size=26,bold=True)
        draw.text(painter,30,470,1060,48,note,size=26)
        if index==5:draw.text(painter,30,534,1060,40,'x = x.to(device)',size=28,mono=True,bold=True,color=draw.GREEN)
        painter.end();frames.append(image)
    return frames


def batch_norm():
    """계산식과 기본 모드, 효과의 성립 범위를 구분함."""
    image,painter=draw.canvas()
    draw.text(painter,20,12,1080,44,'배치 정규화: 계산과 사용 조건',size=32,bold=True)
    panels=[('계산',['배치 평균 μ · 분산 v','x̂ = (x−μ) / √(v+ε)','y = γx̂ + β','γ, β는 학습 파라미터','출력 분산: γ²v/(v+ε)'],draw.GREEN),
            ('구조 예시',['nn.Linear(20, 64)','nn.BatchNorm1d(64)','nn.ReLU()'],draw.INK),
            ('기본 설정의 모드',['train: 현재 배치 통계','eval: 저장한 이동 통계','track_running_stats=True','평가 전 model.eval()'],draw.ORANGE)]
    for column,(title,lines,color) in enumerate(panels):
        x=20+370*column
        painter.setPen(QPen(QColor(color),3));painter.setBrush(QColor('white'))
        painter.drawRoundedRect(QRectF(x,82,340,370),14,14)
        draw.text(painter,x+18,96,304,42,title,size=26,bold=True,color=color)
        for row,text in enumerate(lines):
            draw.text(painter,x+18,158+row*51,304,42,text,size=20 if 'track_' in text else 22,mono=text.startswith('nn.') or 'track_' in text)
    draw.text(painter,24,478,1072,42,'큰 학습률·일반화 개선은 모델과 데이터에 따라 달라집니다.',size=26)
    draw.text(painter,24,532,1072,42,'RNN에 적용할 때도 배치 구성·길이·패딩과 통계 축을 확인합니다.',size=24)
    painter.end();return [image]


def regression_conditions():
    """R²와 단일 가중치 규제의 조건을 표시함."""
    image,painter=draw.canvas()
    draw.text(painter,20,12,1080,44,'평가 지표와 규제는 성립 조건을 함께 읽습니다',size=30,bold=True)
    draw.text(painter,20,64,1080,40,'규제 예: 가중치 w 하나 · MSE=(w−0.3)² · 유한한 λ≥0',size=26)
    panels=[('R²',['정답이 상수가 아닐 때','SS_tot > 0','R² = 1−SS_res/SS_tot','음수도 가능합니다.','기울기 방향은 아닙니다.'],draw.MUTED),
            ('이 예의 Ridge',['더하는 벌점: λw²','최적의 w = 0.3/(1+λ)','유한한 λ≥0이면 w>0'],draw.PURPLE),
            ('이 예의 Lasso',['더하는 벌점: λ|w|','λ≥0.6이면 최적의 w=0','0≤λ<0.6이면','최적의 w = 0.3−λ/2'],draw.ORANGE)]
    for column,(title,lines,color) in enumerate(panels):
        x=20+370*column
        painter.setPen(QPen(QColor(color),3));painter.setBrush(QColor('white'))
        painter.drawRoundedRect(QRectF(x,126,340,340),14,14)
        draw.text(painter,x+18,142,304,42,title,size=26,bold=True,color=color)
        for row,text in enumerate(lines):draw.text(painter,x+18,202+row*47,304,40,text,size=22)
    draw.text(painter,24,488,1072,42,'SGD의 weight_decay=λ는 손실 벌점 (λ/2)w²에 해당합니다.',size=26)
    draw.text(painter,24,542,1072,40,'다른 손실 배율이나 여러 가중치의 문제에 이 최솟값을 그대로 적용하지 않습니다.',size=22)
    painter.end();return [image]


def training_weight():
    """전체 분포의 산술 예와 훈련용 가중치를 분리함."""
    assert abs(9461/539-17.5528756957)<1e-9
    image,painter=draw.canvas()
    draw.text(painter,20,12,1080,44,'전체 분포를 보는 일과 훈련 가중치를 정하는 일',size=30,bold=True)
    panels=[('전체 분포의 산술 예',['정상 9,461건','사기 539건','9,461 / 539 ≈ 17.55','훈련 빈도는 아닙니다.'],draw.MUTED),
            ('분할 뒤 훈련 라벨 집계',['훈련 음성 수 = N₀','훈련 양성 수 = N₁','pos_weight = N₀ / N₁','N₁이 0이면 자료 확인'],draw.BLUE),
            ('손실과 평가',['가중치는 정답 1인 항에','BCEWithLogitsLoss 사용','모델 출력은 logit','평가: eval() + no_grad()'],draw.INK)]
    for column,(title,lines,color) in enumerate(panels):
        x=20+370*column
        painter.setPen(QPen(QColor(color),3));painter.setBrush(QColor('white'))
        painter.drawRoundedRect(QRectF(x,94,340,368),14,14)
        draw.text(painter,x+18,110,304,42,title,size=24,bold=True,color=color)
        for row,text in enumerate(lines):draw.text(painter,x+18,180+row*58,304,44,text,size=22)
    draw.text(painter,24,484,1072,42,'stratify=y는 양쪽 클래스 비율을 원래 비율에 가깝게 나눕니다.',size=26)
    draw.text(painter,24,538,1072,40,'scaler도 훈련 데이터로만 fit하고, 검증·테스트 데이터에는 transform만 합니다.',size=24)
    painter.end();return [image]


def training_then_evaluation():
    """갱신 뒤 평가 모드·새 예측·정확도를 순서대로 연결함."""
    image,painter=draw.canvas()
    draw.text(painter,20,12,1080,44,'학습으로 갱신한 뒤 평가 모드에서 새로 예측합니다',size=30,bold=True)
    draw.text(painter,20,70,1080,40,'학습: 기울기를 계산하고 파라미터를 갱신합니다.',size=26,color=draw.BLUE)
    top=['model.train()','zero_grad()','예측 → 손실','backward()','step()']
    bottom=['model.eval()','no_grad() 안','새 예측 z','z ≥ 0.0','정확도 계산']
    for row,(labels,y,color) in enumerate(((top,150,draw.BLUE),(bottom,400,draw.PURPLE))):
        for index,label in enumerate(labels):
            x=20+220*index
            painter.setPen(QPen(QColor(color),3));painter.setBrush(QColor('white'))
            painter.drawRoundedRect(QRectF(x,y,200,100),12,12)
            draw.text(painter,x+12,y+10,176,30,str(1+index+row*5),size=20,color=color,bold=True)
            draw.text(painter,x+12,y+45,176,40,label,size=20,mono='(' in label,bold=True)
            if index<4:draw.arrow(painter,(x+201,y+50),(x+218,y+50),color)
    draw.line(painter,(1000,252),(1000,312),draw.MUTED,3)
    draw.line(painter,(1000,312),(120,312),draw.MUTED,3)
    draw.arrow(painter,(120,312),(120,398),draw.MUTED,3)
    draw.text(painter,240,340,850,42,'평가: 기울기를 기록하지 않고 평가 자료로 예측합니다.',size=26,color=draw.PURPLE)
    draw.text(painter,24,528,1072,32,'7~10번은 no_grad() 안에서 계산하며 파라미터를 갱신하지 않습니다.',size=24)
    draw.text(painter,24,568,1072,28,'BCEWithLogitsLoss의 logit은 0을 기준으로 나눕니다.',size=22)
    painter.end();return [image]


def momentum_conditions():
    """손실 곡선의 최적점과 모멘텀 식을 구분함."""
    image,painter=draw.canvas()
    draw.text(painter,20,12,1080,44,'모멘텀은 과거 누적값을 이번 갱신에 반영합니다',size=30,bold=True)
    def f(x):return x*(x+1)*(x+2)*(x-2)
    def derivative(x):return 4*x**3+3*x**2-8*x-4
    roots=[]
    for low,high in ((-2,-1),(1,2)):
        for _ in range(60):
            middle=(low+high)/2
            if derivative(middle)>0:high=middle
            else:low=middle
        roots.append((low+high)/2)
    assert [round(x,2) for x in roots]==[-1.61,1.33]
    def point(x,y):return 50+(x+2.8)/5*420,140+(12-y)/22*330
    painter.save();painter.setClipRect(QRectF(50,140,420,330))
    curve=QPainterPath(QPointF(*point(-2.8,f(-2.8))))
    for index in range(1,301):
        x=-2.8+index/60;curve.lineTo(QPointF(*point(x,f(x))))
    for y in (-5,0,5,10):draw.line(painter,point(-2.8,y),point(2.2,y),draw.GRID)
    painter.setPen(QPen(QColor(draw.RED),3));painter.drawPath(curve)
    for x in roots:draw.dot(painter,point(x,f(x)),draw.BLUE,8)
    painter.restore()
    draw.line(painter,point(-2.8,-10),point(2.2,-10),draw.INK)
    draw.line(painter,point(-2.8,-10),point(-2.8,12),draw.INK)
    for value in (-5,0,5,10):draw.text(painter,12,point(-2.8,value)[1]-12,35,25,str(value),size=18)
    for value in (-2,-1,0,1,2):draw.text(painter,point(value,-10)[0]-12,472,34,24,str(value),size=18)
    draw.text(painter,40,82,460,42,'f(x)=x(x+1)(x+2)(x−2)',size=26)
    draw.text(painter,40,504,460,32,'국소 x≈−1.61 · 전역 x≈1.33',size=24,color=draw.BLUE)
    draw.text(painter,40,540,460,36,'도달하는 곳은 출발점에도 달려 있습니다.',size=22)
    for row,text in enumerate(('SGD의 기본 모멘텀','첫 갱신: v=g','그 뒤: v=μv+g','새 W=W−lr·v','예시 W: 1→1.01904→1.054774')):
        draw.text(painter,530,90+row*57,560,45,text,size=26 if row<4 else 24,bold=row==0,color=draw.PURPLE if row<4 else draw.INK)
    draw.text(painter,530,394,560,80,'optim.SGD([W, B], lr=0.001,\n          momentum=0.9)',size=22,mono=True)
    draw.text(painter,530,484,560,36,'dampening=0, nesterov=False',size=22,mono=True)
    draw.text(painter,530,532,560,48,'흔들림·손실 감소는 항상 보장되지 않습니다.',size=24)
    painter.end();return [image]


def split_example():
    """자료 수만으로 정하지 않는 분할 비율의 계산 예임."""
    assert 3000+1000+1000==5000
    image,painter=draw.canvas()
    draw.text(painter,20,12,1080,44,'데이터 5,000개를 60/20/20으로 나누는 예입니다',size=30,bold=True)
    draw.text(painter,20,68,1080,40,'자료의 시간 순서와 중복·집단 구조를 보고 분할 방법을 정합니다.',size=26)
    painter.setPen(QPen(QColor(draw.RED),3))
    curve=QPainterPath(QPointF(1000,178));curve.cubicTo(900,115,500,115,350,178);painter.drawPath(curve)
    draw.arrow(painter,(365,169),(350,178),draw.RED)
    draw.text(painter,650,114,48,48,'×',size=34,bold=True,color=draw.RED)
    x=20
    parts=[(648,'학습 데이터','3,000개','파라미터를 학습합니다.',draw.BLUE),
           (216,'검증 데이터','1,000개','설정을 고릅니다.',draw.ORANGE),
           (216,'테스트 데이터','1,000개','마지막 평가입니다.',draw.PURPLE)]
    for width,title,count,use,color in parts:
        painter.fillRect(QRectF(x,190,width-3,132),QColor(color))
        draw.text(painter,x+12,204,width-27,44,title,size=26,bold=True,color='white')
        draw.text(painter,x+12,262,width-27,44,count,size=26,color='white')
        draw.text(painter,x+12,346,width-27,50,use,size=22)
        x+=width
    draw.text(painter,24,418,1072,42,'평가용 자료를 학습에 섞으면 데이터 누수가 생깁니다.',size=26,color=draw.RED)
    draw.text(painter,24,482,1072,42,'평균 등 전처리 값도 학습 데이터에서만 구해 세 묶음에 적용합니다.',size=26)
    draw.text(painter,24,540,1072,40,'60/20/20은 이 예의 비율이며 자료 수만으로 정하는 규칙이 아닙니다.',size=24)
    painter.end();return [image]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pillow-site')
    parser.add_argument('--only', nargs='+', choices=('1a-3','3h-1','4f-4','4g-3','5f-4','7f-4','8e-4','8e-5'))
    args=parser.parse_args()
    if args.pillow_site:sys.path.append(args.pillow_site)
    from PIL import Image
    app=QApplication.instance() or QApplication([])
    for name in ('NanumGothic-Regular.ttf','D2Coding-Regular.ttf'):
        key=QFontDatabase.addApplicationFont(str(ROOT/'gui/fonts'/name))
        assert key>=0
        draw.FONTS['code' if name.startswith('D2') else 'body']=QFontDatabase.applicationFontFamilies(key)[0]
    path=ROOT/'tools/ai_art/manifest.json';manifest=read_manifest(str(path))
    for lesson,name,fn in (('l01','1a-3',learning_rates),('l03','3h-1',device_transfer),('l05','5f-4',batch_norm),
                           ('l07','7f-4',regression_conditions),('l08','8e-4',training_then_evaluation),('l08','8e-5',training_weight),
                           ('l04','4f-4',momentum_conditions),('l04','4g-3',split_example)):
        if args.only and name not in args.only:continue
        images=fn();suffix='.gif' if len(images)>1 else '.png'
        target=ROOT/'ai/learn'/lesson/'assets'/(name+suffix)
        if len(images)>1:draw.save_gif(images,target,Image)
        else:
            rgba=images[0].convertToFormat(draw.QImage.Format.Format_RGBA8888)
            frame=Image.frombytes('RGBA',(draw.WIDTH,draw.HEIGHT),rgba.constBits().asstring(rgba.sizeInBytes())).convert('RGB')
            palette=frame.quantize(colors=64)
            fixed=[channel for color in FIXED for channel in (QColor(color).red(),QColor(color).green(),QColor(color).blue())]
            colors=fixed+palette.getpalette()[:(64-len(FIXED))*3]
            palette.putpalette(colors+[0]*(768-len(colors)))
            frame.quantize(palette=palette,dither=Image.Dither.NONE).save(target,optimize=True)
            with Image.open(target) as saved:assert saved.size==(1120,600)
            assert target.stat().st_size<=150*1024
        key=target.relative_to(ROOT/'ai').as_posix()
        manifest['files'][key]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'script':'tools/ai_art/conditions_qt.py','fn':fn.__name__}
        print(key,target.stat().st_size,flush=True)
    write_manifest(manifest,str(path))
    assert not any(name in sys.modules for name in ('torch','numpy','matplotlib'))
    return app


if __name__=='__main__':main()
