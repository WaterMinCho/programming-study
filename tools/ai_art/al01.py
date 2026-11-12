# -*- coding: utf-8 -*-
"""입력 준비의 위치·값·색·마스크를 직접 그린 예로 연결함."""
from pathlib import Path

from tools.ai_art import figure, FONTS

W, H = 1120, 600
INK, BLUE, PALE, LINE = '#1f2937', '#2563eb', '#dbeafe', '#e5e7eb'


def font(size=32, bold=False):
    from PIL import ImageFont
    return ImageFont.truetype(str(Path(FONTS) / ('NanumGothic-Bold.ttf' if bold else 'NanumGothic-Regular.ttf')), size)


def text(draw, xy, value, size=32, color=INK, bold=False):
    value = str(value).replace("−", "-").replace("⁸", "^8")
    width = draw.textlength(value, font=font(size, bold))
    assert xy[0] + width <= W - 24, (value, width)
    draw.text(xy, value, fill=color, font=font(size, bold))


def base(title, subtitle='입력 준비 → 모델 → 예측 → 평가'):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((24, 24, W-24, H-24), radius=24, outline=LINE, width=2)
    text(d, (52, 47), 'AI 응용 · 입력 준비', 26, BLUE, True)
    text(d, (52, 97), title, 40, bold=True)
    text(d, (52, 529), subtitle, 27, '#6b7280')
    return im, d


def box(d, xy, label, fill=PALE, size=34):
    x,y,w,h = xy
    label = str(label).replace("−", "-").replace("⁸", "^8")
    d.rounded_rectangle((x,y,x+w,y+h), radius=16, fill=fill)
    tw=d.textlength(str(label),font=font(size,True))
    text(d,(x+(w-tw)/2,y+(h-size)/2-2),label,size,bold=True)


def chain(title, labels, note=''):
    im,d=base(title,note or '입력 표현을 바꾸며 모델의 가중치는 갱신하지 않습니다.')
    gap=30; width=(1016-gap*(len(labels)-1))/len(labels)
    for n,label in enumerate(labels):
        box(d,(52+n*(width+gap),220,width,140),label,size=28)
        if n<len(labels)-1:text(d,(57+(n+1)*width+n*gap,270),'→',26,BLUE)
    return im


def cells(d, values, x=70, y=210, scale=115, labels=True):
    for n,v in enumerate(values):
        xx=x+(n%3)*scale; yy=y+(n//3)*scale
        color=tuple(v) if isinstance(v,tuple) else (int(v),)*3
        d.rectangle((xx,yy,xx+scale-8,yy+scale-8),fill=color,outline=LINE,width=2)
        if labels and not isinstance(v,tuple):text(d,(xx+15,yy+30),v,30,'white' if v<120 else INK,True)


@figure('a1a-1')
def sampling():
    values=[20,60,100,140,180,220]
    quant=[min((0,85,170,255),key=lambda q:abs(q-v)) for v in values]
    assert quant==[0,85,85,170,170,255]
    frames=[]
    for n,title in enumerate(['공간에서 읽을 위치를 고릅니다','선택한 위치의 밝기를 읽습니다','값을 정해진 단계로 나타냅니다']):
        im,d=base(title,'개념도 · 위치 선택과 값의 단계는 서로 다른 선택입니다.')
        cells(d, quant if n==2 else values, labels=n>0)
        text(d,(500,220),['공간 격자 2행 × 3열','읽은 위치 6개','예시 단계 0 · 85 · 170 · 255'][n],32,bold=True)
        text(d,(500,295),['픽셀 수: 6개','밝기값: 위치마다 하나','100에 가까운 단계: 85'][n],30)
        text(d,(500,370),['샘플링은 위치를 고릅니다.','위치마다 밝기값을 읽었습니다.','밝기 단계만 바꾸며 격자는 6개입니다.'][n],30)
        frames.append(im)
    return frames,[2200]*3


@figure('a1a-2')
def bit_range():
    return chain('8비트는 값을 256개 구분합니다',['2⁸ = 256','0부터 시작','최대값 255'],'uint8 범위 · 0은 검정, 255는 흰색입니다.')


@figure('a1a-3')
def pixel_count():
    im,d=base('픽셀과 색 성분의 개수를 나눕니다')
    values=[(v,min(255,v+20),max(0,v-20)) for v in [20,60,100,140,180,220]]
    cells(d,values,labels=False)
    text(d,(500,215),'2 × 3 = 6픽셀',38,bold=True)
    text(d,(500,285),'한 픽셀의 색 성분 확대',30)
    for n,label in enumerate(['R: 20','G: 40','B: 0']):
        box(d,(500+n*180,350,160,90),label,size=28)
    text(d,(500,465),'6 × 3 = 18개 값',34,BLUE,True)
    assert 2*3*3==18
    return im


@figure('a1b-1')
def channels():
    frames=[]
    for n,title in enumerate(['BGR의 이름에 맞춰 값을 읽습니다','RGB에 맞게 첫째와 셋째를 옮깁니다','값의 순서가 바뀌어도 같은 색입니다']):
        im,d=base(title)
        vals=[('B',10),('G',40),('R',220)] if n==0 else [('R',220),('G',40),('B',10)]
        for j,(name,value) in enumerate(vals):
            x=52+j*330
            box(d,(x,220,300,160),str(value),fill={'R':'#fee2e2','G':'#d1fae5','B':'#dbeafe'}[name],size=52)
            text(d,(x+100,405),name,38,bold=True)
        text(d,(52,470),'BGR → RGB: [10, 40, 220] → [220, 40, 10]',30)
        if n==2:d.rectangle((950,400,1035,485),fill=(220,40,10))
        frames.append(im)
    return frames,[2200]*3


@figure('a1b-2')
def shape():
    im,d=base('shape는 축마다 길이를 적습니다')
    for n,(label,value) in enumerate([('높이 H','4'),('너비 W','6'),('채널 C','3')]):
        box(d,(52+n*340,220,310,125),value,size=54)
        text(d,(90+n*340,375),label,32)
    text(d,(52,455),'shape = (4, 6, 3) · ndim = 3개 축',34,BLUE,True)
    return im


@figure('a1b-3')
def input_axes():
    return chain('모델 조건에 맞게 축을 옮깁니다',['HWC: 6,8,3','CHW: 3,6,8','NCHW: 1,3,6,8'],'resize의 (너비 8, 높이 6) → shape는 (6, 8, 3)입니다.')


@figure('a1c-1')
def arithmetic():
    frames=[]
    for n,(title,result) in enumerate([('수학적인 합은 268입니다',268),('uint8 포화 덧셈은 255입니다',255),('uint8 배열 덧셈은 12로 돌아옵니다',12)]):
        im,d=base(title)
        box(d,(52,220,280,150),'238 + 30',size=40)
        text(d,(375,275),'→',40,BLUE)
        box(d,(475,220,280,150),result,size=58)
        if n:
            d.rectangle((830,220,1035,370),fill=(result,)*3,outline=LINE,width=3)
        else:
            d.rectangle((830,220,1035,370),outline=LINE,width=3)
            text(d,(840,255),'uint8 범위 밖',26)
        text(d,(52,445),['범위를 제한하기 전의 계산입니다.','표현할 수 있는 최대값에서 멈춥니다.','268 = 256 + 12입니다.'][n],34)
        frames.append(im)
    assert (238+30)%256==12 and min(255,238+30)==255
    return frames,[2200]*3


@figure('a1c-2')
def clip():
    return chain('범위를 넘기 전에 자료형을 넓힙니다',['uint8: 238','uint16: 268','clip: 255'],'양수 30을 더한 예 · 음수 뺄셈에는 자료형을 다시 고릅니다.')


@figure('a1c-3')
def masking():
    im,d=base('마스크가 허용한 위치만 남깁니다','원본 → 마스크 → 새 결과 · 검정 배경은 투명이 아닙니다.')
    values=[20,60,100,140,180,220];mask=[0,255,0,0,255,0];out=[v if m else 0 for v,m in zip(values,mask)]
    assert out==[0,60,0,0,180,0]
    for x,vs,label in [(52,values,'원본'),(420,mask,'마스크'),(785,out,'결과')]:
        cells(d,vs,x,230,95)
        text(d,(x,180),label,30,BLUE,True)
    return im


@figure('a1d-1')
def hsv():
    frames=[]
    for n,title in enumerate(['두 픽셀의 색 성분을 읽습니다','범위 안인지 각 성분을 비교합니다','마스크로 고른 원본 위치를 남깁니다']):
        im,d=base(title,'이 예의 조건: H 100~130 · S와 V 80~255')
        for j,(values,ok) in enumerate([('[110,150,180]',True),('[70,150,180]',False)]):
            x=52+j*535
            box(d,(x,215,490,110),values,size=38)
            text(d,(x+20,365),('범위 안 → 255' if ok else '범위 밖 → 0') if n else 'H · S · V',34,BLUE,True)
            if n==2:box(d,(x,430,490,65),'원본 BGR 픽셀 유지' if ok else '결과 0',size=30)
        frames.append(im)
    return frames,[2200]*3


@figure('a1d-2')
def histogram():
    im,d=base('밝기값별 픽셀 수를 셉니다','가로축: 밝기값 · 세로축: 픽셀 수 · 전체 4픽셀')
    counts=[2,1,0,1]
    assert sum(counts)==4
    d.line((130,435,990,435),fill=INK,width=3)
    d.line((130,185,130,435),fill=INK,width=3)
    for n,c in enumerate(counts):
        x=210+n*190
        if c:d.rectangle((x,435-c*100,x+95,435),fill=BLUE)
        text(d,(x+25,445),n,30)
        text(d,(x+25,395-c*100),c,30,BLUE,True)
    text(d,(52,170),'개수',26)
    return im


@figure('a1d-3')
def normalization():
    assert [(x-80)/60 for x in [80,110,140]]==[0,0.5,1]
    return chain('최소·최대로 0~1 범위를 맞춥니다',['80 → 0','110 → 0.5','140 → 1'],'min-max: (값 − 80) ÷ (140 − 80) · 분모가 0이면 따로 처리합니다.')


def level_base(title):
    from PIL import Image, ImageDraw
    im=Image.new('RGB',(1040,560),'white')
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((24,24,1016,536),radius=24,outline=LINE,width=2)
    text(d,(50,55),title,34,bold=True)
    return im,d


@figure('a1b-31',520,280)
def level_pixel_grid():
    im,d=level_base('가로 칸과 세로 줄을 세어 봅니다')
    for row in range(4):
        for col in range(6):
            d.rectangle((60+col*80,150+row*70,130+col*80,210+row*70),fill=PALE,outline=BLUE,width=2)
    text(d,(600,190),'가로 6칸',38,BLUE,True)
    text(d,(600,280),'세로 4줄',38,BLUE,True)
    return im


@figure('a1b-32',520,280)
def level_components():
    im,d=level_base('위치마다 담은 색 성분도 셉니다')
    for n,(label,value) in enumerate([('높이',4),('너비',6),('성분 수',3)]):
        box(d,(60+n*315,165,285,120),value,size=52)
        text(d,(95+n*315,315),label,32)
    text(d,(60,420),'한 장: 4 × 6 × 3 = 72개 값',38,BLUE,True)
    return im


@figure('a1b-33',520,280)
def level_bytes():
    im,d=level_base('축 순서와 자료형을 나누어 봅니다')
    box(d,(60,155,420,110),'HWC: 4,6,3',size=36)
    box(d,(555,155,420,110),'CHW: 3,4,6',size=36)
    text(d,(500,190),'→',32,BLUE)
    text(d,(60,330),'uint8: 72바이트',36,bold=True)
    text(d,(555,330),'float32: 288바이트',36,bold=True)
    text(d,(60,430),'원소 수 유지 · 값마다 1바이트 → 4바이트',32,BLUE)
    assert 4*6*3==72 and 72*4==288
    return im

# 갱신된 실습의 입력·출력과 상태 변화를 별도로 그림.
def _update_figure(kind, stage=0):
    from PIL import ImageDraw
    titles = {
        'blend':'같은 위치의 두 값을 비율에 맞춰 섞습니다',
        'difference':'방향이 있는 뺄셈과 차이의 크기를 나눕니다',
        'channels':'채널을 나눈 순서대로 다시 합칩니다',
        'read':'파일 읽기 성공 뒤 배열의 모양을 확인합니다',
        'save':'배열 저장과 도표 저장을 나눕니다',
        'format':'저장 형식 변경은 잃은 정보를 되살리지 않습니다',
        'copy':'원본 공유와 독립 복사를 구분합니다',
        'coords':'같은 위치를 점 좌표와 배열 인덱스로 찾습니다',
        'shapes':'처리 결과에 맞는 표시를 선택합니다',
        'baseline':'문자열은 왼쪽 기준선에서 배치합니다',
        'environment':'로컬 창과 노트북의 입력 방식을 비교합니다',
        'mouse':'누름·이동·뗌에 따라 그리기 상태가 바뀝니다',
        'slider':'설정을 바꿀 때마다 원본에서 다시 계산합니다',
    }
    im,d=base(titles[kind],'설명용 그림 · 값·좌표·상태의 변화를 직접 표시했습니다.')
    if kind=='blend':
        labels=[['입력 A\n40','입력 B\n200'],['A × 0.5\n20','B × 0.5\n100'],['반영한 값\n20 + 100','결과\n120']][stage]
        for n,label in enumerate(labels):
            for j,line in enumerate(label.split('\n')):box(d,(70+n*540,215+j*100,440,85),line,size=37)
        text(d,(70,445),['동일한 위치의 두 값을 고릅니다.','각 입력의 절반만 반영합니다.','추가 밝기는 0으로 두었습니다.'][stage],32,BLUE)
    elif kind=='difference':
        for r,(label,vals) in enumerate([('입력 A',[40,100,200]),('입력 B',[200,60,100]),('포화 뺄셈 A - B',[0,40,100]),('절대차 |A - B|',[160,40,100])]):
            y=185+r*76;text(d,(65,y+15),label,31,bold=True)
            for c,v in enumerate(vals):box(d,(530+c*170,y,145,65),v,size=34)
    elif kind=='channels':
        box(d,(65,230,400,150),'BGR: 10, 40, 220',size=30)
        text(d,(490,280),'→',38,BLUE)
        for n,(label,v) in enumerate([('B',10),('G',40),('R',220)]):
            box(d,(575+n*165,210,145,90),label,size=34);box(d,(575+n*165,330,145,90),v,size=34)
        text(d,(65,465),'merge([b, g, r])로 같은 순서로 묶습니다.',32,BLUE)
    elif kind=='read':
        box(d,(55,270,230,100),'sample.png',size=30)
        box(d,(325,270,230,100),'imread',size=30)
        box(d,(700,200,350,100),'실패: None → 중단',fill=PALE if stage==1 else '#f3f4f6',size=29)
        box(d,(700,355,350,100),'성공: (4, 6, 3)',fill=PALE if stage==2 else '#f3f4f6',size=29)
        d.line((285,320,325,320),fill=BLUE,width=4)
        d.line((555,320,625,320,625,250,700,250),fill=BLUE,width=4)
        d.line((625,320,625,405,700,405),fill=BLUE,width=4)
        text(d,(65,475),['읽기 결과에 따라 다음 동작을 나눕니다.','실패하면 경로·파일을 확인하고 변환을 멈춥니다.','성공한 경우에만 배열의 높이·너비·채널을 읽습니다.'][stage],29,BLUE)
    elif kind=='save':
        for n,(name,note) in enumerate([('imwrite','픽셀 배열을 파일로'),('savefig','축·여백이 있는 도표를 파일로')]):
            x=60+n*540;d.rounded_rectangle((x,190,x+490,470),16,outline=LINE,width=3)
            text(d,(x+25,205),name,36,BLUE,True)
            if n==0:
                for yy in range(3):
                    for xx in range(4):d.rectangle((x+65+xx*70,275+yy*45,x+130+xx*70,315+yy*45),fill=(60+xx*45,)*3)
            else:
                d.line((x+60,410,x+60,275,x+420,275),fill=INK,width=3)
                d.line((x+75,390,x+150,365,x+220,380,x+330,300),fill=BLUE,width=5)
            text(d,(x+22,430),note,25)
    elif kind=='format':
        for n,label in enumerate(['원본 정보','JPEG에서\n일부 손실','그 결과를\nPNG로 저장']):
            x=55+n*355
            for j,line in enumerate(label.split('\n')):box(d,(x,215+j*83,320,75),line,size=30)
            if n<2:text(d,(381+n*355,270),'→',26,BLUE)
        text(d,(65,450),'이미 잃은 정보는 저장 확장자 변경으로 돌아오지 않습니다.',30,BLUE)
    elif kind=='copy':
        if stage==2:
            text(d,(65,170),'비교: 처음 원본에서 따로 복사한 경우',28,BLUE,True)
        source=[1,2,3] if stage!=1 else [1,9,3]
        box(d,(65,215,420,115),'원본: '+str(source),size=33)
        box(d,(620,215,420,115),['기본 슬라이스: [2, 3]','뷰에 9 기록','복사본에만 9 기록'][stage],size=31)
        d.line((485,275,620,275),fill=BLUE if stage<2 else LINE,width=5)
        text(d,(65,400),['같은 데이터를 함께 가리킵니다.','원본의 같은 위치도 9로 바뀝니다.','따로 복사했다면 원본은 [1, 2, 3]입니다.'][stage],31,BLUE)
    elif kind=='coords':
        for y in range(6):
            for x in range(8):
                xx,yy=75+x*45,195+y*45
                d.rectangle((xx,yy,xx+42,yy+42),fill='#fee2e2' if 2<=x<=4 and 1<=y<=3 else '#f3f4f6',outline=LINE)
                if 2<=x<=4 and 1<=y<=3:d.ellipse((xx+15,yy+15,xx+24,yy+24),fill='#dc2626')
        for n,line in enumerate(['점: (2, 1)부터 (4, 3)','배열: [1:4, 2:5]','3행 × 3열 = 9픽셀']):text(d,(500,220+n*90),line,32,BLUE,n==2)
        text(d,(75,480),'x는 오른쪽 · y는 아래쪽',27)
    elif kind=='shapes':
        labels=['line · arrowedLine','rectangle','circle','ellipse','polylines','drawMarker']
        for i,label in enumerate(labels):
            x=55+(i%3)*355;y=185+(i//3)*155
            d.rounded_rectangle((x,y,x+325,y+140),12,outline=LINE,width=2)
            if i==0:d.line((x+40,y+45,x+285,y+45),fill=BLUE,width=5);d.polygon([(x+285,y+45),(x+266,y+34),(x+266,y+56)],fill=BLUE)
            elif i==1:d.rectangle((x+100,y+22,x+220,y+80),outline=BLUE,width=5)
            elif i in (2,3):d.ellipse((x+(125 if i==2 else 80),y+15,x+(195 if i==2 else 245),y+85),outline=BLUE,width=4)
            elif i==4:d.line((x+90,y+80,x+160,y+20,x+230,y+80,x+90,y+80),fill=BLUE,width=4)
            else:d.line((x+160,y+20,x+160,y+80),fill=BLUE,width=4);d.line((x+130,y+50,x+190,y+50),fill=BLUE,width=4)
            text(d,(x+30,y+100),label,25,BLUE,True)
    elif kind=='baseline':
        d.line((80,340,1030,340),fill=BLUE,width=3)
        d.text((170,340),'Objectg',font=font(90),fill=INK,anchor='ls')
        d.ellipse((163,333,177,347),fill='#dc2626')
        text(d,(80,200),'org는 왼쪽 기준선 위치입니다.',33,BLUE,True)
        text(d,(170,395),'org = (x, y)',34,BLUE)
        text(d,(640,395),'g의 아래 획은 기준선 아래로',27)
    elif kind=='environment':
        for n,lines in enumerate([['로컬 OpenCV GUI','imshow · waitKey','setMouseCallback','createTrackbar'],['Colab 노트북','cv2_imshow','ipycanvas','ipywidgets']]):
            x=65+n*535;d.rounded_rectangle((x,190,x+485,490),16,outline=LINE,width=3)
            for j,line in enumerate(lines):text(d,(x+30,215+j*65),line,30,BLUE if j==0 else INK,j==0)
    elif kind=='mouse':
        lines=[('누름 (2, 3)','그리기 켬','시작 위치 저장'),('이동 (4, 4)','그리기 켜짐','이전 → 현재로 선'),('뗌 (4, 4)','그리기 끔','이후 이동에는 안 그림')]
        for r,row in enumerate(lines):
            for c,value in enumerate(row):box(d,(55+c*355,200+r*95,325,78),value,size=28)
    elif kind=='slider':
        level=[100,150,50][stage];result=int(40*level/100)
        box(d,(65,210,400,170),'원본 40',size=43)
        box(d,(630,210,400,170),f'결과 {result}',size=43)
        text(d,(490,265),'→',43,BLUE)
        text(d,(65,430),f'level {level} → 배율 {level/100:g}',36,BLUE,True)
        text(d,(630,430),'원본에서 다시 계산',31)
    return im


def _new_draw_function(kind, animated=False, level=False):
    def draw():
        if animated:return [_update_figure(kind,s) for s in range(3)],[2200]*3
        im=_update_figure(kind)
        return im.resize((1040,560)) if level else im
    return draw


for _name,_kind,_animated in [
    ('a1e-1','blend',True),('a1e-2','difference',False),('a1e-3','channels',False),
    ('a1f-1','read',True),('a1f-2','save',False),('a1f-3','format',False),
    ('a1g-1','copy',True),('a1g-2','coords',False),('a1g-3','shapes',False),('a1g-4','baseline',False),
    ('a1h-1','environment',False),('a1h-2','mouse',False),('a1h-3','slider',True),
]:
    _fn=_new_draw_function(_kind,_animated);_fn.__name__='updated_'+_name.replace('-','_')
    globals()[_fn.__name__]=figure(_name)(_fn)


def _extra_level(kind,number):
    title={'weight':'입력별 비율과 결과를 구분합니다','copy':'함께 가리키는 원본과 별도 복사를 나눕니다'}[kind]
    im,d=base(title,'예제 조건을 유지하며 초급·중급·심화의 계산을 더합니다.')
    if kind=='weight':
        rows=[['입력 A 80','입력 B 80','반씩 섞음 80'],['40 × 0.5 = 20','200 × 0.5 = 100','결과 120'],['A 60 · B 20','비율 2와 0','결과 120']][number-1]
    else:
        rows=[['독립 복사','복사본에 점 3개','원본의 새 점 0개'],['원본 [1:3, 2:5]','2행 · 3열 공유','대입 위치 6개'],['원본 [1, 2, 3]','view 첫 값에 9','원본 [1, 9, 3]']][number-1]
    for n,row in enumerate(rows):box(d,(70,190+n*95,980,78),row,size=38)
    return im.resize((1040,560))


for _prefix,_kind in [('a1e-3','weight'),('a1g-2','copy')]:
    for _number in (1,2,3):
        _name=_prefix+str(_number)
        def _draw(kind=_kind,number=_number):return _extra_level(kind,number)
        _draw.__name__='updated_'+_name.replace('-','_')
        globals()[_draw.__name__]=figure(_name,520,280)(_draw)


del _fn, _draw
