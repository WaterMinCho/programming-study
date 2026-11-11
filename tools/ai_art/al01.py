# -*- coding: utf-8 -*-
"""입력 준비의 위치·값·색·마스크를 직접 그린 예로 연결함."""
from pathlib import Path

from tools.ai_art import figure, FONTS

W, H = 1120, 600
INK, BLUE, PALE, LINE = '#111827', '#2563eb', '#dbeafe', '#e5e7eb'


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
    text(d, (52, 529), subtitle, 27, '#4b5563')
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
