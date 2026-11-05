# -*- coding: utf-8 -*-
"""12차시의 특징 수, 이동 평균 무게, 검증 선택, 독립 층 수, 가릴 넓이를 계산함."""
from fractions import Fraction

from aiprep.gen import gen, blank


@gen('i12-g01', unit='12a', step='12a/3', facts=['F12-03'], tags=['깊은 CNN'], level=2, prio=3,
     ref=['12차시 노트북 01 [29]'], basis='lecture-formula', family='deep-cnn-features')
def feature_count(r):
    """풀링 구간마다 정한 채널 수와 공간 크기로 특징 수를 구함."""
    side,first,depth=r.pick([16,32,64]),r.pick([2,4,8,16]),r.int(1,3)
    last_channel=first*2**(depth-1)
    last_side=side//2**depth
    count=last_channel*last_side*last_side
    return blank(stem='공간 %d×%d에서 크기를 유지하는 합성곱과 기본 MaxPool2d(2)를 %d구간 적용합니다. 첫 풀링 전 출력 채널은 %d이고 다음 구간마다 두 배로 정했습니다. 마지막 특징을 한 장씩 펼치면 값은 ____ 개입니다.' % (side,side,depth,first),
        blanks=[{'answer':[str(count)],'mode':'number'}],
        explain='마지막 채널은 %d이고 공간 길이는 %d입니다. %d×%d×%d = %d개입니다.' % (last_channel,last_side,last_channel,last_side,last_side,count),
        params={'side':side,'first':first,'depth':depth})


@gen('i12-g02', unit='12b', step='12b/3', facts=['F12-06'], tags=['지수 이동 평균'], level=2, prio=2,
     ref=['12차시 노트북 02 [18]','PyTorch 문서 RMSprop'], basis='lecture-formula', family='ema-absolute-weight',errata=['X12-01'])
def ema_weight(r):
    """정정한 절대 무게 (1−rho)rho^k를 구하고 상대 비율과 구분함."""
    rho=Fraction(r.pick(['1/2','4/5','9/10','99/100']))
    age=r.int(0,8)
    weight=(1-rho)*rho**age
    return blank(stem='분수로 답해도 됩니다. 이전 기록 비율 rho=%s인 지수 이동 평균에서 이번 값의 무게는 1−rho입니다. %d번 전 값의 절대 무게 (1−rho)×rho^%d는 ____ 입니다.' % (rho,age,age),
        blanks=[{'answer':[str(weight)],'mode':'number'}],
        explain='정정: rho^k는 이번 값 대비 비율입니다. 실제 무게에는 1−rho도 곱하므로 (1−%s)×(%s)^%d = %s입니다.' % (rho,rho,age,weight),
        params={'rho':str(rho),'age':age})


@gen('i12-g03', unit='12c', step='12c/2', facts=['F12-07'], tags=['검증 손실'], level=1, prio=3,
     ref=['12차시 슬 p7','12차시 과제 1번'], basis='lecture-example', family='best-validation-epoch')
def best_epoch(r):
    """서로 다른 검증 손실에서 최솟값 에폭을 고름."""
    n=r.int(5,9)
    losses=r.shuffle(list(range(20,95)))[:n]
    answer=losses.index(min(losses))+1
    shown=', '.join('%.2f' % (x/100) for x in losses)
    return blank(stem='에폭을 1부터 셉니다. 검증 손실이 [%s]라면 가장 작은 손실을 기록한 에폭은 ____ 입니다.' % shown,
        blanks=[{'answer':[str(answer)],'mode':'number'}],
        explain='최솟값 %.2f는 목록의 %d번째 값입니다.' % (min(losses)/100,answer),params={'losses':losses})


@gen('i12-g04', unit='12d', step='12d/3', facts=['F12-12'], tags=['독립 BN'], level=2, prio=2,
     ref=['12차시 슬 p15','PyTorch 문서 BatchNorm2d'], basis='lecture-formula', family='independent-bn-params')
def independent_bn(r):
    """같은 채널 수의 BN을 위치마다 독립 생성한 학습 파라미터 수를 셈."""
    channels,places=r.int(1,24),r.int(2,5)
    total=2*channels*places
    return blank(stem='채널 %d개인 BatchNorm2d를 %d위치에 하나씩 독립 생성합니다. affine=True, bias=True이며 running 통계는 학습 파라미터에서 제외합니다. weight와 bias의 원소 수는 합쳐 ____ 개입니다.' % (channels,places),
        blanks=[{'answer':[str(total)],'mode':'number'}],
        explain='한 객체에 채널별 weight와 bias가 있어 %d×2개입니다. 독립 객체 %d개에서 합계 %d개입니다.' % (channels,places,total),
        params={'channels':channels,'places':places})


@gen('i12-g05', unit='12e', step='12e/3', facts=['F12-15'], tags=['지운 넓이 비율'], level=2, prio=2,
     ref=['12차시 슬 p16','PyTorch 문서 RandomErasing'], basis='lecture-formula', family='erased-area-ratio')
def erased_ratio(r):
    """지문에서 선택한 직사각형의 넓이 비율을 계산함."""
    height,width=r.int(5,20),r.int(5,20)
    erase_h,erase_w=r.int(1,height-1),r.int(1,width-1)
    ratio=Fraction(erase_h*erase_w,height*width)
    return blank(stem='분수로 답해도 됩니다. 높이 %d, 너비 %d인 이미지에서 이번에 높이 %d, 너비 %d의 직사각형을 가렸습니다. 지운 공간 넓이÷원본 공간 넓이는 ____ 입니다.' % (height,width,erase_h,erase_w),
        blanks=[{'answer':[str(ratio)],'mode':'number'}],
        explain='(%d×%d) ÷ (%d×%d) = %s입니다. 이 값은 지운 영역의 비율이고 변환 실행 확률 p와 구분합니다.' % (erase_h,erase_w,height,width,ratio),
        params={'height':height,'width':width,'erase_h':erase_h,'erase_w':erase_w})
