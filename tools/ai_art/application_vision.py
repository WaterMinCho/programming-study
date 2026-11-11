"""입력 준비와 프레임별 특징 검출의 수치 예를 그리는 공통 부품임."""
from tools.ai_art.al01 import font, text as _text

W, H = 1120, 600
INK, BLUE, PURPLE = '#1f2937', '#2563eb', '#7c3aed'
PALE, LINE, GREEN = '#dbeafe', '#e5e7eb', '#059669'


def text(draw, xy, value, size=32, color=INK, bold=False):
    value = str(value).replace('θ', 'theta').replace('ρ', 'rho')
    _text(draw, xy, value, size, color, bold)


def base(title, note, phase=None):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(image)
    text(draw, (40, 28), 'AI 응용 · 입력과 특징을 연결합니다', 25, BLUE, True)
    text(draw, (40, 75), title, 37, bold=True)
    labels = ['이미지 입력', '잡음·좌표 준비', '프레임·특징', '학습 모델']
    for i, label in enumerate(labels):
        x = 40 + i * 266
        draw.rounded_rectangle((x, 136, x + 244, 180), 10,
                               fill=PALE if i == phase else '#f3f4f6')
        text(draw, (x + 13, 145), label, 24, BLUE if i == phase else '#6b7280', i == phase)
    text(draw, (40, 545), note, 25, '#6b7280')
    return image, draw


def panel(draw, x, y, w, h, label, fill=PALE, size=30):
    draw.rounded_rectangle((x, y, x + w, y + h), 14, fill=fill)
    lines = label.split('\n')
    for i, line in enumerate(lines):
        length = draw.textlength(line, font=font(size, True))
        assert length <= w - 20, (line, length, w)
        text(draw, (x + (w-length)/2, y + (h-len(lines)*(size+12))/2 + i*(size+12)), line, size, bold=True)


def chain(draw, labels, active=2, y=250):
    gap = 42
    width = (1040-gap*(len(labels)-1))/len(labels)
    for i, label in enumerate(labels):
        x = 40+i*(width+gap)
        panel(draw, x, y, width, 150, label, PALE if i <= active else '#f3f4f6', 29)
        if i < len(labels)-1:
            text(draw, (x+width+9, y+55), '→', 30, BLUE)


def grid(draw, values, x=50, y=230, size=76, binary=False, marked=None):
    for r, row in enumerate(values):
        for c, value in enumerate(row):
            xx, yy = x+c*size, y+r*size
            fill = ('#2563eb' if value else '#f3f4f6') if binary else '#eff6ff'
            draw.rounded_rectangle((xx, yy, xx+size-5, yy+size-5), 7, fill=fill,
                                   outline=PURPLE if (r,c) == marked else LINE, width=3)
            color = 'white' if binary and value else INK
            text(draw, (xx+17, yy+19), value, 29, color, True)


def point_plane(draw, points, x=75, y=245, step=42, labels=True):
    draw.line((x,y,x+365,y), fill=INK, width=3)
    draw.line((x,y,x,y+260), fill=INK, width=3)
    text(draw, (x+375,y-25), 'x', 26)
    text(draw, (x-18,y+265), 'y', 26)
    for px, py, label in points:
        xx, yy = x+px*step, y+py*step
        draw.ellipse((xx-7,yy-7,xx+7,yy+7), fill=BLUE)
        if labels:
            text(draw,(xx+10, yy-20),label,26,BLUE,True)


SPECS = {
 'mean': ('이웃 값 → 합계 → 새 중심값', '설명용 내부 영역 · 가장자리 처리는 별도입니다.', 1),
 'median': ('고립된 큰 값과 중앙값을 비교합니다', '같은 입력이라도 평균과 중앙값은 다른 값을 고릅니다.', 1),
 'kernel': ('커널이 살피는 위치 수가 늘어납니다', '넓게 섞으면 작은 무늬도 흐려질 수 있습니다.', 1),
 'erode': ('고립된 전경 점은 침식으로 사라집니다', '파란색은 전경 1 · 회색은 배경 0 · 영상 내부 예입니다.', 1),
 'dilate': ('팽창은 전경이 하나라도 있는지 봅니다', '같은 이웃에서 침식은 0, 팽창은 1입니다.', 1),
 'morph': ('열기와 닫기의 순서를 구분합니다', '구조 요소보다 작은 전경 점과 배경 틈을 비교합니다.', 1),
 'resize': ('출력 크기와 배열의 순서를 맞춥니다', 'dsize는 너비·높이 · shape는 높이·너비·채널입니다.', 1),
 'interpolate': ('원본 위치 0.25의 값을 계산합니다', '설명용 예 · 원본 좌표에 직접 수를 넣어 계산합니다.', 1),
 'maskresize': ('밝기와 범주값을 구분합니다', '범주 마스크에는 중간값이 새 범주를 뜻하지 않습니다.', 1),
 'translate': ('오른쪽 3, 아래 2만큼 옮깁니다', '좌상단 원점 · x는 오른쪽, y는 아래로 증가합니다.', 1),
 'inverse': ('출력 위치에서 원본을 역으로 읽습니다', '기본 warpAffine · 입력 M은 원본 → 출력입니다.', 1),
 'rotate': ('회전한 모서리가 출력 밖으로 나갑니다', '35도 회전 도식 · 출력 범위와 이동 성분을 함께 조절합니다.', 1),
 'corners': ('같은 모서리 A·B·C·D를 짝짓습니다', '비퇴화 평면 대응 · 양쪽 목록의 모서리 순서를 맞춥니다.', 1),
 'divide': ('동차좌표의 마지막 값으로 나눕니다', '공통 분모 w가 0이면 유한 좌표를 이 식으로 구하지 않습니다.', 1),
 'bridge': ('준비한 이미지를 프레임별 검출로 잇습니다', '고정 연산으로 특징을 뽑으며 가중치 학습과 구분합니다.', 2),
 'frames': ('사진 한 장의 처리를 시간순으로 반복합니다', '도식 · 같은 이미지 처리 규칙을 프레임마다 적용합니다.', 2),
 'read': ('읽기 성공을 확인한 다음 변환합니다', '실패는 정상 파일 끝 또는 오류일 수 있습니다.', 2),
 'fps': ('120프레임의 재생 분량을 셉니다', '고정 24FPS 예 · 연산 소요 시간은 따로 측정합니다.', 2),
 'release': ('프레임 처리를 끝내면 자원을 해제합니다', '실행 환경에 맞는 출력과 키 입력 방식을 사용합니다.', 2),
 'difference': ('공간 이웃과 시간 이웃을 나눠 봅니다', '밝기 차이만으로 물체의 종류나 정체를 확정하지 않습니다.', 2),
 'sobel': ('밝기의 순서를 뒤집으면 부호가 바뀝니다', '설명용 한 줄 커널 [-1, 0, 1] · 실제 3×3 배율과 구분합니다.', 2),
 'gradients': ('기울기의 입력과 출력을 확인합니다', '이미지 기울기와 손실 기울기는 미분 대상이 다릅니다.', 2),
 'canny': ('잡음 완화 뒤 얇고 이어진 경계를 고릅니다', '예제에서는 가우시안 전처리를 직접 명시합니다.', 2),
 'nms': ('기울기 방향으로 반응 크기를 비교합니다', '세로 경계 예 · 가로 방향 비교로 가운데 90을 남깁니다.', 2),
 'hysteresis': ('같은 약한 반응도 연결 여부를 봅니다', '낮은 기준 40 · 높은 기준 100 · 경계값 같은 수는 제외합니다.', 2),
 'votes': ('같은 직선을 지지하는 점이 표를 모읍니다', '한 점은 여러 후보에 표를 줍니다. x=3 후보에는 이 세 점이 표를 줍니다.', 2),
 'normal': ('각도는 직선에 수직인 법선 방향입니다', '이미지 좌표 x→, y↓ · 세로선의 법선 각도는 0도입니다.', 2),
 'hough': ('경계점에서 직선 후보의 표로 옮깁니다', '도형 검출 결과는 학습한 물체 범주와 구분합니다.', 2),
 'roi': ('관심 영역에서 어두운 부분을 고릅니다', '역이진화: 입력 ≤ T이면 255, 입력 > T이면 0입니다.', 2),
 'centroid': ('위치 합을 같은 집계의 면적으로 나눕니다', '윤곽선 모멘트 예 · 픽셀 개수 집계와 섞지 않습니다.', 2),
 'offset': ('잘라 낸 시작 좌표를 다시 더합니다', 'ROI 시작 (10, 30) · 내부 중심 (6, 4) → 원본 (16, 34)', 2),
}


def draw(kind, stage=2):
    title, note, phase = SPECS[kind]
    image, d = base(title, note, phase)
    if kind in ('mean', 'median'):
        grid(d, [[18,18,18],[18,90,18],[18,18,18]], marked=(1,1))
        if kind == 'mean':
            panel(d, 400, 235, 270, 110, ['9칸의 값','합계 234','234 ÷ 9'][stage], size=33)
            panel(d, 760, 235, 280, 110, ['중심 90','같은 비중','새 중심 26'][stage], size=33)
            text(d,(400,420),'18 × 8 + 90 = 234',36,BLUE,True)
        else:
            text(d,(370,240),'정렬: 18 · 18 · 18 · 18 · 18',28)
            text(d,(450,290),'18 · 18 · 18 · 90',28)
            panel(d,380,380,290,100,'중앙값 18')
            panel(d,740,380,290,100,'평균 26')
        assert (18*8+90)/9 == 26
    elif kind == 'kernel':
        grid(d, [[1]*3 for _ in range(3)], 85,245,70,True)
        grid(d, [[1]*5 for _ in range(5)], 560,220,51,True)
        text(d,(95,485),'3 × 3 = 9곳',32,BLUE,True)
        text(d,(570,485),'5 × 5 = 25곳',32,BLUE,True)
        assert 3*3 == 9 and 5*5 == 25
    elif kind in ('erode','dilate'):
        values=([[0,0,0],[0,1 if stage<2 else 0,0],[0,0,0]] if kind=='erode'
                else [[1,1,1],[1,1,1],[1,1,0]])
        grid(d,values,marked=(1,1),binary=True)
        if kind=='erode':
            panel(d,405,235,610,105,['전경 점 하나와 주변 배경','구조 요소 아래 배경이 있습니다','중심값 0 · 점을 지웁니다'][stage])
            text(d,(405,415),'모든 칸이 전경일 때만 남깁니다.',31,BLUE,True)
        else:
            panel(d,405,235,290,105,'침식 → 0')
            panel(d,760,235,290,105,'팽창 → 1')
            text(d,(405,415),'하나라도 1 → 팽창은 1',32,BLUE,True)
        assert min(sum(values,[])) == 0
    elif kind == 'morph':
        text(d,(50,220),'열기 · 작은 전경 점 제거',29,BLUE,True)
        panel(d,50,270,260,85,'침식');text(d,(335,292),'→',32,BLUE);panel(d,390,270,260,85,'팽창')
        text(d,(50,390),'닫기 · 작은 배경 틈 줄이기',29,PURPLE,True)
        panel(d,50,440,260,70,'팽창',fill='#ede9fe');text(d,(335,454),'→',32,PURPLE);panel(d,390,440,260,70,'침식',fill='#ede9fe')
        grid(d,[[0,0,0],[0,1,0],[0,0,0]],790,245,65,True)
    elif kind == 'resize':
        for x,w,h,label in [(55,240,144,'높이 3 · 너비 5'),(540,400,240,'높이 6 · 너비 10')]:
            d.rectangle((x,220,x+w,220+h),fill=PALE,outline=BLUE,width=3)
            for c in range(1,5 if x==55 else 10):
                xx=x+c*w/(5 if x==55 else 10);d.line((xx,220,xx,220+h),fill='white',width=2)
            for r in range(1,3 if x==55 else 6):
                yy=220+r*h/(3 if x==55 else 6);d.line((x,yy,x+w,yy),fill='white',width=2)
            text(d,(x,480),label,30,BLUE,True)
        text(d,(355,275),['원본','각 축 2배','dsize (10, 6)'][stage],25)
        assert 3*5*4 == 6*10
    elif kind == 'interpolate':
        d.line((120,345,970,345),fill=INK,width=4)
        for x,label,value in [(120,'위치 0','20'),(332,'위치 0.25','30'),(970,'위치 1','60')]:
            d.ellipse((x-8,337,x+8,353),fill=BLUE)
            text(d,(x-40,250),value,42,BLUE,True);text(d,(x-60,390),label,28)
        text(d,(130,470),'20 × 0.75 + 60 × 0.25 = 30',35,bold=True)
        assert 20*.75+60*.25 == 30
    elif kind == 'maskresize':
        for y,left,right,fill in [(230,'사진 · 밝기값','선형 등 비교',PALE),(390,'마스크 · 범주 0 | 1','최근접 · 기존 값 선택','#ede9fe')]:
            panel(d,60,y,420,105,left,fill,30)
            text(d,(520,y+30),'→',34,BLUE)
            panel(d,610,y,440,105,right,fill,30)
    elif kind in ('translate','inverse'):
        # 영상 좌표의 y축은 아래로 증가하도록 직접 그림.
        for x0,label in [(70,'원본'),(640,'이동 과정' if kind=='translate' and stage<2 else '출력')]:
            d.rectangle((x0,235,x0+340,490),outline=LINE,width=3)
            text(d,(x0,198),label,28,BLUE,True)
        destination = (2+1.5*stage, 1+stage) if kind == 'translate' else (5,3)
        for x0,px,py,label in [(70,2,1,'(2, 1)'),(640,*destination,f'({destination[0]:g}, {destination[1]:g})')]:
            x,y=x0+px*48,250+py*48
            d.ellipse((x-9,y-9,x+9,y+9),fill=BLUE)
            if kind != 'translate' or stage != 1 or x0 == 70:
                text(d,(x-40,y+20),label,28,BLUE,True)
        text(d,(425,270),'오른쪽 3',28);text(d,(440,315),'아래 2',28)
        text(d,(465,385),'←' if kind=='inverse' else ['원본','→','→'][stage],40,BLUE)
        assert (2+3,1+2) == (5,3)
    elif kind == 'rotate':
        import math
        angle=math.radians(35);c,s=math.cos(angle),math.sin(angle)
        corners=[(-150,-100),(150,-100),(150,100),(-150,100)]
        rotated=[(310+c*x+s*y,365-s*x+c*y) for x,y in corners]
        edges=[(rotated[(i+1)%4][0]-p[0],rotated[(i+1)%4][1]-p[1]) for i,p in enumerate(rotated)]
        assert abs(sum(a*b for a,b in zip(edges[0],edges[1])))<1e-8
        assert abs(math.hypot(*edges[0])-300)<1e-8 and abs(math.hypot(*edges[1])-200)<1e-8
        d.rectangle((160,265,460,465),fill='#eff6ff',outline=BLUE,width=4)
        d.polygon([(round(x),round(y)) for x,y in rotated],outline=PURPLE,width=4)
        d.ellipse((303,358,317,372),fill=INK)
        panel(d,650,245,380,100,'출력 테두리',size=33)
        panel(d,650,390,380,100,'회전한 물체',fill='#ede9fe')
    elif kind == 'corners':
        start=[(90,260),(390,220),(440,475),(60,465)]
        end=[(680,240),(1000,240),(1000,480),(680,480)]
        target=[(round((x+590)*(1-stage/2)+u*stage/2), round(y*(1-stage/2)+v*stage/2)) for (x,y),(u,v) in zip(start,end)]
        shapes=[start,target]
        for points in shapes:
            d.polygon(points,fill='#eff6ff',outline=BLUE,width=4)
            for (x,y),label in zip(points,'ABCD'):
                text(d,(x-15,y-36),label,30,PURPLE,True)
        text(d,(500,330),['네 모서리','같은 이름','→'][stage],28,BLUE,True)
    elif kind == 'divide':
        chain(d,['곱한 결과\n12 · 8 · 2','공통 분모\n2로 나누기','출력 좌표\n6 · 4'],stage)
        assert (12/2,8/2) == (6,4)
    elif kind == 'bridge':
        chain(d,['1강\n픽셀·색','2강\n잡음·좌표','3강\n프레임·특징'])
        text(d,(130,465),'입력 준비 → 특징·도형·위치 → 학습 모델에 연결',31,BLUE,True)
    elif kind == 'frames':
        for i in range(3):
            x=55+i*355
            d.rounded_rectangle((x,230,x+300,440),12,fill='#eff6ff',outline=BLUE,width=3)
            px=x+60+i*62
            d.ellipse((px,315,px+55,370),fill=PURPLE if i<=stage else '#d1d5db')
            text(d,(x+18,250),f'프레임 {i+1}',30,BLUE,True)
        text(d,(80,480),'시간 →      읽기 · 준비 · 검출을 반복합니다.',32,bold=True)
    elif kind == 'read':
        panel(d,55,295,280,110,'프레임 읽기',size=32)
        panel(d,650,220,380,95,'성공 → 변환',fill='#d1fae5',size=32)
        panel(d,650,375,380,95,'실패 → 중단',fill='#ede9fe',size=32)
        d.line((335,350,470,350,470,267,630,267),fill=GREEN,width=4)
        d.line((470,350,470,422,630,422),fill=PURPLE,width=4)
        text(d,(610,249),'→',30,GREEN);text(d,(610,403),'→',30,PURPLE)
        text(d,(65,495),'실패한 프레임을 변환하지 않습니다.',34,BLUE,True)
    elif kind == 'fps':
        chain(d,['120프레임','24장 / 초','재생 5초'])
        text(d,(115,465),'처리 시간은 필터·검출 연산과 장치로 달라집니다.',30,BLUE,True)
        assert 120/24 == 5
    elif kind == 'release':
        chain(d,['파일 열기','프레임 처리','release()'])
        text(d,(100,465),'예외가 생겨도 해제하도록 finally를 사용할 수 있습니다.',29,BLUE,True)
    elif kind == 'difference':
        panel(d,55,225,440,100,'같은 프레임 · 옆 칸\n30 → 90',size=28)
        panel(d,650,225,375,100,'공간 차이 60' if stage>0 else '공간 차이 계산',size=32)
        panel(d,55,390,440,100,'다음 프레임 · 같은 칸\n30 → 45' if stage==2 else '다음 프레임의 같은 칸',fill='#ede9fe' if stage==2 else '#f3f4f6',size=28)
        panel(d,650,390,375,100,'시간 차이 15' if stage==2 else '시간 차이 계산',fill='#ede9fe' if stage==2 else '#f3f4f6',size=32)
        text(d,(545,255),'→',34,BLUE);text(d,(545,420),'→',34,PURPLE)
        assert abs(90-30) == 60 and abs(45-30) == 15
    elif kind == 'sobel':
        text(d,(60,225),'한 줄 커널   -1       0       1',32,BLUE,True)
        grid(d,[[20,20,80]],60,295,110)
        panel(d,600,285,400,100,['곱해 더할 입력','-20 + 0 + 80','응답 +60'][stage],size=32)
        text(d,(70,465),'반대로 [80, 20, 20] → 응답 -60',34,bold=True)
        assert -20+80 == 60 and -80+20 == -60
    elif kind == 'gradients':
        chain(d,['이미지 위치\nx · y','밝기 변화\nSobel'])
        text(d,(70,460),'학습 모델: 가중치 변화 → 손실 변화',32,PURPLE,True)
    elif kind == 'canny':
        chain(d,['잡음 완화\n기울기 계산','비최대 억제\n얇은 후보','두 임계값\n연결 확인'],stage)
    elif kind == 'nms':
        grid(d,[[30,90,50]],90,280,125,marked=(0,1))
        d.line((278,220,278,480),fill=PURPLE,width=5)
        text(d,(80,220),'기울기 방향 →',29,BLUE,True)
        panel(d,650,290,330,105,'가운데 90 유지',size=31)
        text(d,(660,450),'선의 방향은 위아래',28,PURPLE,True)
        assert 90 > max(30,50)
    elif kind == 'hysteresis':
        for x,label,fill in [(70,'130\n강한 후보',PALE),(430,'70\n연결되어 유지','#d1fae5'),(790,'70\n고립되어 제거','#f3f4f6')]:
            panel(d,x,265,260,145,label,fill,29)
        d.line((330,330,430,330),fill=GREEN,width=8)
        text(d,(70,465),'같은 크기 70 · 강한 경계와 이어졌는지 확인합니다.',29,bold=True)
    elif kind == 'votes':
        point_plane(d,[(3,1,'(3,1)'),(3,2,'(3,2)'),(3,4,'(3,4)')],x=85,y=240)
        d.line((211,220,211,490),fill=PURPLE,width=3)
        panel(d,640,260,370,140,['경계점 3개','이 후보에 한 표씩','x=3에 3표'][stage],size=32)
        text(d,(650,450),'같은 직선 후보를 지지',28,BLUE,True)
    elif kind == 'normal':
        d.line((180,240,180,480),fill=PURPLE,width=5)
        d.line((75,370,180,370),fill=BLUE,width=4)
        text(d,(220,260),'x=3 · 세로선',31,PURPLE,True)
        text(d,(220,365),'법선 → · theta=0도',29,BLUE,True)
        d.line((650,410,1030,410),fill=PURPLE,width=5)
        d.line((800,245,800,405),fill=BLUE,width=4)
        text(d,(650,455),'y=4 · theta=90도',29,BLUE,True)
    elif kind == 'hough':
        chain(d,['경계점\nx · y','직선 후보\nρ · θ','누적 표\n후보 선택'])
        text(d,(90,465),'직선 존재 확인 ≠ 물체 범주 학습',32,PURPLE,True)
    elif kind == 'roi':
        d.rectangle((70,220,470,510),outline=LINE,width=3)
        if stage>0:
            d.rectangle((70,325,470,510),fill='#eff6ff' if stage==1 else INK,outline=BLUE,width=4)
        d.ellipse((240,380,300,440),fill='white' if stage==2 else INK)
        text(d,(95,240),'원본',28)
        if stage>0:text(d,(95,345),'ROI',30,BLUE,True)
        panel(d,620,255,410,100,['관심 영역 선택','어두운 부분 선택','전경 마스크'][stage],size=30)
        panel(d,620,400,410,100,'작은 밝기 → 255',fill='#ede9fe')
    elif kind == 'centroid':
        chain(d,['m00 = 8\n같은 집계','m10 = 48\nm01 = 32','cx = 6\ncy = 4'])
        text(d,(80,465),'분모가 0이면 중심 계산을 건너뜁니다.',33,BLUE,True)
        assert (48/8,32/8) == (6,4)
    elif kind == 'offset':
        chain(d,['ROI 시작\n(10, 30)','내부 중심\n(6, 4)','원본 중심\n(16, 34)'])
        text(d,(90,470),'미검출 프레임은 새 중심을 찾았다고 기록하지 않습니다.',29,BLUE,True)
        assert (10+6,30+4) == (16,34)
    else:
        raise ValueError(kind)
    return image


def register(module, number, kinds):
    from tools.ai_art import figure
    for unit, names in kinds.items():
        for i, kind in enumerate(names, 1):
            def render(kind=kind, animate=i == 1):
                if animate:
                    from PIL import ImageDraw
                    frames = []
                    for stage, label in enumerate(['입력 살피기', '규칙 적용', '결과 확인']):
                        image = draw(kind, stage)
                        text(ImageDraw.Draw(image), (870, 511), label, 24, BLUE, True)
                        frames.append(image)
                    return frames, [2200]*3
                return draw(kind)
            render.__name__ = kind
            module[kind] = figure(f'a{number}{unit}-{i}')(render)


def draw_level(unit, level):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (1040, 560), 'white')
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((20,20,1020,540),20,outline=LINE,width=2)
    titles = {'a2a':'주변 값을 모아 새 값을 구합니다', 'a2c':'위치별 비중으로 값을 정합니다',
              'a2e':'같은 분모로 가로·세로를 나눕니다', 'a3a':'재생 분량과 처리량을 구분합니다',
              'a3b':'밝기의 차이와 크기를 구분합니다', 'a3e':'내부 좌표를 원본 좌표로 옮깁니다'}
    text(d,(45,50),titles[unit],35,BLUE,True)
    if unit == 'a2a':
        if level == 1:
            grid(d,[[18,18,18],[18,90,18],[18,18,18]],80,160,105,marked=(1,1))
            text(d,(515,230),'가운데에 90',34,bold=True)
            text(d,(515,335),'나머지 칸을 세어 보세요.',30)
        else:
            labels = [('중심',90),('평균',26)] if level == 2 else [('새 중심',180),('새 평균',36)]
            for i,(label,value) in enumerate(labels):
                y=190+i*145
                text(d,(65,y),label,32,BLUE,True)
                width=value*(7 if level==2 else 3)
                d.rounded_rectangle((230,y,230+width,y+65),9,fill=PALE)
                text(d,(250+width,y+12),'?' if level==3 and i==1 else value,34,bold=True)
            text(d,(70,465),'합계 234 · 전체 값을 같은 비중으로 더합니다.' if level==2 else '중심을 180으로 바꾼 뒤 평균을 다시 구합니다.',29)
            assert sum([18]*8+[90])/9 == 26
    elif unit == 'a2c':
        xs = [135,327 if level<3 else 713,905]
        d.line((135,300,905,300),fill=INK,width=4)
        for x,label in zip(xs,['20','새 위치','60']):
            d.ellipse((x-10,290,x+10,310),fill=BLUE)
            text(d,(x-45,220),label,32,BLUE,True)
        if level > 1:
            text(d,(65,390),'t = 0.25' if level==2 else 't = 0.75',34,bold=True)
            text(d,(65,460),'왼쪽 비중 0.75 · 오른쪽 비중 0.25' if level==2 else 'value = 20 × 0.25 + 60 × 0.75',31)
        else:
            text(d,(100,420),'양 끝과 그 사이 한 곳을 살펴봅니다.',32)
    elif unit == 'a2e':
        if level==1:
            panel(d,70,180,260,110,'앞 숫자 12',size=30)
            panel(d,390,180,260,110,'앞 숫자 8',size=30)
            panel(d,710,180,260,110,'마지막 2',size=30)
            text(d,(100,395),'앞의 수를 마지막 수로 각각 나눕니다.',32)
        elif level==2:
            panel(d,70,190,390,120,'세로 8 ÷ 2 = 4',size=32)
            panel(d,550,190,420,120,'분모 1이면?',fill='#ede9fe',size=32)
            text(d,(80,420),'같은 분자에서 분모를 바꿔 봅니다.',32)
        else:
            panel(d,60,175,420,110,'w ≠ 0 → u/w, v/w',size=29)
            panel(d,555,175,420,110,'w = 0 → None',fill='#ede9fe',size=30)
            text(d,(80,400),'분모 확인 뒤 유한 좌표를 돌려줍니다.',32)
    elif unit == 'a3a':
        if level==1:
            for i in range(5):
                panel(d,60+i*192,180,165,130,'24장',size=32)
                text(d,(80+i*192,350),f'{i+1}초째',28)
            text(d,(75,455),'매초 같은 수의 사진이 지나갑니다.',32)
        elif level==2:
            panel(d,60,190,420,110,'120 ÷ 24 = 5초',size=32)
            panel(d,550,190,420,110,'72 ÷ 24 = ?초',size=32)
            text(d,(80,420),'장수를 초당 장수로 나눕니다.',32)
        else:
            panel(d,60,190,420,120,'재생 분량\ncount / fps',size=30)
            panel(d,550,190,420,120,'처리량\ncount / elapsed',fill='#ede9fe',size=30)
            text(d,(80,440),'같은 장수 · 분모의 의미가 다릅니다.',32)
    elif unit == 'a3b':
        if level==1:
            grid(d,[[20,20,80]],110,190,160)
            text(d,(100,440),'같은 값이 적힌 칸을 세어 보세요.',32)
        elif level==2:
            grid(d,[[80,20,20]],85,180,130)
            panel(d,570,205,390,100,'20 − 80',size=40)
            text(d,(100,430),'오른쪽에서 왼쪽 값을 뺍니다.',32)
        else:
            panel(d,60,190,420,110,'signed = 20 - 80',size=32)
            panel(d,550,190,420,110,'stored = max(0, signed)',size=28)
            text(d,(80,420),'음수가 잘린 뒤 abs(stored)는 얼마일까요?',31)
    elif unit == 'a3e':
        if level==1:
            d.rectangle((80,160,460,495),outline=LINE,width=3)
            d.rectangle((150,370,460,495),fill=PALE,outline=BLUE,width=3)
            d.ellipse((185,391,199,405),fill=PURPLE)
            text(d,(530,190),'시작: 가로 10 · 세로 30',29)
            text(d,(530,290),'내부: 가로 6 · 세로 4',29)
            text(d,(530,390),'원본에서 어디일까요?',31,BLUE,True)
        elif level==2:
            panel(d,60,190,420,110,'시작 30 + 내부 ?',size=31)
            panel(d,550,190,420,110,'원본 34',size=34)
            text(d,(80,420),'반대로 원본에서 시작 위치를 빼 봅니다.',31)
        else:
            panel(d,60,180,420,110,'m00 확인\n0이면 미검출',size=30)
            panel(d,550,180,420,110,'m01 / m00\n+ y_offset',size=30)
            text(d,(80,420),'모멘트로 내부 중심을 구한 뒤 원본으로 옮깁니다.',29)
    return image


def register_levels(module, positions):
    from tools.ai_art import figure
    for unit, step in positions.items():
        for level in (1,2,3):
            def render(unit=unit, level=level):
                return draw_level(unit, level)
            render.__name__ = f'{unit}_level_{level}'
            module[render.__name__] = figure(f'{unit}-{step}{level}',520,280)(render)
