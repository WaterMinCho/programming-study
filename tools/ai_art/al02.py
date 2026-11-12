"""필터와 기하학적 변환을 수치 예로 그린 그림임."""
from tools.ai_art.application_vision import register, register_levels

register(globals(), 2, {
    'a': ['mean', 'median', 'kernel'],
    'b': ['erode', 'dilate', 'morph'],
    'c': ['resize', 'interpolate', 'maskresize'],
    'd': ['translate', 'inverse', 'rotate'],
    'e': ['corners', 'divide', 'bridge'],
})

register_levels(globals(), {'a2a': 2, 'a2c': 3, 'a2e': 3})

from tools.ai_art import figure
from tools.ai_art.application_vision import base, grid, panel, text, BLUE, INK, LINE


def _map_figure(kind,stage=0):
    titles={'indices':'행과 열의 번호를 두 지도에 나눕니다','lookup':'출력의 빈 위치에서 원본을 조회합니다','lens':'넓은 출력 위치가 가까운 원본을 조회합니다','bounds':'원본 안과 밖의 조회 조건을 나눕니다','iterations':'iterations=2는 침식 두 번 뒤 팽창 두 번입니다'}
    im,d=base(titles[kind],'좌표를 바꾸는 고정 연산 · 학습 모델의 가중치를 갱신하지 않습니다.',1)
    if kind=='indices':
        grid(d,[[0,0,0],[1,1,1]],70,230,95);grid(d,[[0,1,2],[0,1,2]],650,230,95)
        text(d,(70,195),'map_y: 행 번호',30,BLUE,True);text(d,(650,195),'map_x: 열 번호',30,BLUE,True)
        text(d,(70,475),'같은 위치의 (map_x, map_y)를 함께 읽습니다.',31)
    elif kind=='lookup':
        for i,v in enumerate(range(0,161,20)):
            x=55+i*78;d.rounded_rectangle((x,235,x+70,315),9,fill='#dbeafe' if i in [4,5] and stage else '#f3f4f6')
            text(d,(x+10,260),v,27,bold=True);text(d,(x+23,330),i,24)
        panel(d,825,230,250,120,'출력: '+('90' if stage==2 else '미정'),size=32)
        if stage==1:
            d.line((900,380,445,380,445,315),fill=BLUE,width=4)
            d.polygon([(445,315),(435,334),(455,334)],fill=BLUE)
            text(d,(70,440),'지도: 원본 x=4.5, y=0을 조회',32,BLUE,True)
        elif stage==2:
            d.line((445,410,950,410,950,350),fill=BLUE,width=4)
            d.polygon([(950,350),(940,369),(960,369)],fill=BLUE)
            text(d,(70,455),'(80 + 100) / 2 = 90을 출력에 기록',32,BLUE,True)
        else:text(d,(70,445),'아래 작은 수는 원본의 x 좌표입니다.',30,BLUE)
    elif kind=='lens':
        for n,label in enumerate(['원본 조회 위치','출력의 위치']):
            x=60+n*540;text(d,(x+15,210),label,33,BLUE,True)
            d.line((x+10,360,x+470,360),fill=INK,width=3)
            for k in range(5):
                xx=x+30+k*100;d.line((xx,350,xx,370),fill=INK,width=2);text(d,(xx-5,385),k+2,27)
            point=x+280 if n==0 else x+430
            d.ellipse((point-9,351,point+9,369),fill=BLUE)
            text(d,(x+40,460),'x = 4.5' if n==0 else 'x = 6',36,BLUE,True)
        text(d,(60,280),'중심 x=4 · y=4로 고정한 한 줄 예',28)
    elif kind=='bounds':
        panel(d,45,290,200,110,'이웃 위치',size=29)
        panel(d,310,210,320,100,'원본 안: 픽셀 값',size=28)
        panel(d,310,370,320,100,'원본 밖: 경계 값',size=28)
        panel(d,710,290,150,110,'보간',size=31)
        panel(d,925,290,150,110,'출력 값',size=29)
        d.line((245,345,275,345,275,260,310,260),fill=BLUE,width=4)
        d.line((275,345,275,420,310,420),fill=BLUE,width=4)
        d.line((630,260,670,260,670,345,710,345),fill=BLUE,width=4)
        d.line((630,420,670,420,670,345),fill=BLUE,width=4)
        d.line((860,345,925,345),fill=BLUE,width=4)
        text(d,(45,495),'경계 근처에서는 원본 픽셀과 경계 값을 함께 보간할 수 있습니다.',27,BLUE)
    elif kind=='iterations':
        rows=[('시작', [0,0,1,1,1,0,0,0,0]),('침식2 → 팽창2',[0]*9),('열기1을 두 번',[0,0,1,1,1,0,0,0,0])]
        for n,(label,row) in enumerate(rows):
            text(d,(45,240+n*90),label,28,bold=True);grid(d,[row],410,220+n*90,69,binary=True)
        text(d,(45,495),'1×3 커널 · 양끝 0 · 두 순서의 결과를 비교합니다.',27,BLUE)
    return im


for _name,_kind,_animated in [('a2f-1','indices',False),('a2f-2','lookup',True),('a2f-3','lens',False),('a2f-4','bounds',False),('a2b-4','iterations',False)]:
    def _draw(kind=_kind,animated=_animated):
        if animated:return [_map_figure(kind,i) for i in range(3)],[2200]*3
        return _map_figure(kind)
    _draw.__name__='updated_'+_name.replace('-','_')
    globals()[_draw.__name__]=figure(_name)(_draw)


for _number in (1,2,3):
    def _draw(number=_number):
        im,d=base('조회 좌표와 읽어온 값을 구분합니다','설명용 한 줄 원본 · 보간은 주어진 두 이웃에서 계산합니다.',1)
        rows=[['원래 값 100','조회 위치 확인','새 그림에 100'],['x=2는 40 · x=3은 60','중간 좌표 x=2.5','읽는 값 50'],['map_x=3.5 · map_y=0','이웃 값 60과 80','읽는 값 70']][number-1]
        for i,row in enumerate(rows):panel(d,70,205+i*100,980,80,row,size=35)
        return im.resize((1040,560))
    _name='a2f-3'+str(_number);_draw.__name__='updated_'+_name.replace('-','_')
    globals()[_draw.__name__]=figure(_name,520,280)(_draw)


del _draw
