# -*- coding: utf-8 -*-
"""11차시 합성곱 출력 크기, 가중치 수, 풀링, 샘플별 펼치기를 계산함."""
from aiprep.gen import gen, blank


@gen('i11-g01', unit='11b', step='11b/3', facts=['F11-05'], tags=['합성곱 출력 크기'], level=2, prio=3,
     ref=['11차시 슬 p12','PyTorch 문서 Conv2d'], basis='lecture-formula', family='conv-output')
def conv_side(r):
    """dilation 1인 한 축의 출력 길이를 구함."""
    length,kernel,padding,stride=r.int(7,48),r.pick([2,3,5]),r.int(0,2),r.pick([1,2,3])
    answer=(length+2*padding-kernel)//stride+1
    return blank(stem='dilation=1인 Conv2d의 입력 가로 %d, 커널 가로 %d, padding=%d, stride=%d입니다. 출력 가로는 ____ 입니다.' % (length,kernel,padding,stride),
        blanks=[{'answer':[str(answer)],'mode':'number'}],
        explain='floor((입력 + 2×패딩 − 커널) ÷ 스트라이드) + 1입니다. floor((%d + 2×%d − %d) ÷ %d) + 1 = %d입니다.' % (length,padding,kernel,stride,answer),
        params={'length':length,'kernel':kernel,'padding':padding,'stride':stride})


@gen('i11-g02', unit='11c', step='11c/3', facts=['F11-09'], tags=['합성곱 파라미터 수'], level=2, prio=2,
     ref=['11차시 슬 p11'], basis='lecture-formula', family='conv-params')
def conv_params(r):
    """groups 1, bias True인 Conv2d의 학습 파라미터 수를 구함."""
    cin,cout,kernel=r.int(1,8),r.int(2,12),r.pick([1,2,3,5])
    answer=cout*(cin*kernel*kernel+1)
    return blank(stem='groups=1, bias=True인 nn.Conv2d(%d, %d, kernel_size=%d)의 학습 파라미터 수는 ____ 개입니다.' % (cin,cout,kernel),
        blanks=[{'answer':[str(answer)],'mode':'number'}],
        explain='출력 채널×입력 채널×커널 높이×커널 너비에 편향을 더합니다. %d×%d×%d×%d+%d = %d개입니다.' % (cout,cin,kernel,kernel,cout,answer),
        params={'cin':cin,'cout':cout,'kernel':kernel})


@gen('i11-g03', unit='11d', step='11d/3', facts=['F11-11'], tags=['최대 풀링'], level=2, prio=2,
     ref=['11차시 슬 p12','PyTorch 문서 MaxPool2d'], basis='lecture-formula', family='pool-output',errata=['X11-01'])
def pool_side(r):
    """정정한 홀수 길이 처리에 따라 기본 최대 풀링의 한 축 길이를 구함."""
    length,kernel=r.int(5,70),r.pick([2,3,4])
    answer=(length-kernel)//kernel+1
    return blank(stem='입력 가로가 %d이고 nn.MaxPool2d(%d)를 씁니다. stride는 생략하고 padding=0, dilation=1, ceil_mode=False입니다. 출력 가로는 ____ 입니다.' % (length,kernel),
        blanks=[{'answer':[str(answer)],'mode':'number'}],
        explain='정정: stride 기본값은 커널 크기이며 끝의 불완전 구역은 내립니다. floor((%d−%d) ÷ %d)+1 = %d입니다.' % (length,kernel,kernel,answer),
        params={'length':length,'kernel':kernel})


@gen('i11-g04', unit='11e', step='11e/2', facts=['F11-13'], tags=['Flatten'], level=2, prio=3,
     ref=['11차시 슬 p14','11차시 과제 4번'], basis='lecture-formula', family='flatten-shape')
def flattened(r):
    """배치 축을 남긴 기본 Flatten의 모양을 구함."""
    batch,channels,height,width=r.int(1,9),r.int(1,8),r.int(2,9),r.int(2,9)
    count=channels*height*width
    return blank(stem='입력 텐서 [%d, %d, %d, %d]를 기본 nn.Flatten()으로 펼치면 모양은 ____ 입니다.' % (batch,channels,height,width),
        blanks=[{'answer':['[%d, %d]' % (batch,count)],'mode':'shape'}],
        explain='샘플 축 %d를 남기고 한 샘플의 %d×%d×%d = %d개를 합칩니다.' % (batch,channels,height,width,count),
        params={'batch':batch,'channels':channels,'height':height,'width':width})
