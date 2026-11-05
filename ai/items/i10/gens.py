# -*- coding: utf-8 -*-
"""10차시의 정규화, 배치, 드롭아웃, 평균 손실, 다중 분류 합계를 계산함."""
from fractions import Fraction

from aiprep.gen import gen, blank


@gen('i10-g01', unit='10b', step='10b/3', facts=['F10-05'], tags=['정규화'], level=2, prio=2,
     ref=['10차시 슬 p12'], basis='lecture-formula', family='image-normalize')
def normalized(r):
    """텐서 값을 정해진 평균과 표준편차로 바꾼 값을 구함."""
    x = r.int(0, 20)
    mean = r.int(2, 12)
    std = r.int(1, 8)
    result = Fraction(x - mean, std)
    return blank(stem='분수로 답해도 됩니다. Normalize의 식 (입력 − 평균) ÷ 표준편차에 입력 %d, 평균 %d, 표준편차 %d를 넣은 결과는 ____ 입니다.' % (x, mean, std),
        blanks=[{'answer':[str(result)], 'mode':'number'}],
        explain='(%d − %d) ÷ %d = %s입니다.' % (x, mean, std, result), params={'x':x,'mean':mean,'std':std})


@gen('i10-g02', unit='10c', step='10c/2', facts=['F10-07'], tags=['DataLoader'], level=2, prio=3,
     ref=['10차시 슬 p14'], basis='lecture-formula', family='batches')
def batches(r):
    """마지막 불완전 배치를 포함할 때 배치 수를 구함."""
    n, size = r.int(7, 95), r.int(2, 12)
    count = (n + size - 1) // size
    return blank(stem='샘플 %d개를 batch_size=%d, drop_last=False로 읽으면 한 에폭의 배치 수는 ____ 개입니다.' % (n, size),
        blanks=[{'answer':[str(count)],'mode':'number'}],
        explain='완전한 배치 %d개에 나머지 %d개가 있으면 마지막 배치 하나를 더 셉니다. 전체 배치 수는 %d개입니다.' % (n//size,n%size,count),
        params={'n':n,'size':size})


@gen('i10-g03', unit='10d', step='10d/2', facts=['F10-10'], tags=['드롭아웃'], level=2, prio=2,
     ref=['10차시 노트북 01 [12]','PyTorch 문서 Dropout'], basis='lecture-formula', family='dropout-given-mask')
def dropout_value(r):
    """남긴 여부를 지문에 준 원소의 드롭아웃 출력을 계산함."""
    value, denominator = r.int(1, 45), r.pick([2,3,4,5])
    p = Fraction(1, denominator)
    kept = r.pick([0,1])
    result = Fraction(value * kept, 1) / (1-p)
    return blank(stem='학습 모드 Dropout의 p는 %s입니다. 입력 원소 %d를 이번에 %s. 남은 원소는 1 ÷ (1−p)배 합니다. 이 원소의 출력은 ____ 입니다.' % (p,value,'남겼습니다' if kept else '0으로 만들었습니다'),
        blanks=[{'answer':[str(result)],'mode':'number'}],
        explain='이번 선택 값 %d를 입력에 곱한 뒤 1−p로 나눕니다. %d × %d ÷ (1−%s) = %s입니다.' % (kept,value,kept,p,result),
        params={'value':value,'denominator':denominator,'kept':kept})


@gen('i10-g04', unit='10e', step='10e/2', facts=['F10-13'], tags=['평균 손실'], level=2, prio=3,
     ref=['10차시 노트북 01 [16]'], basis='lecture-formula', family='sample-weighted-loss')
def epoch_mean(r):
    """배치 평균 손실과 배치 크기로 전체 평균을 구함."""
    a,b = r.int(2,12), r.int(1,5)
    loss_a,loss_b = r.int(1,8),r.int(1,8)
    result=Fraction(a*loss_a+b*loss_b,a+b)
    return blank(stem='첫 배치 %d개의 평균 손실은 %d이고 마지막 배치 %d개의 평균 손실은 %d입니다. 전체 샘플의 평균 손실을 분수로 써도 됩니다. 평균 손실은 ____ 입니다.' % (a,loss_a,b,loss_b),
        blanks=[{'answer':[str(result)],'mode':'number'}],
        explain='각 배치 평균에 샘플 수를 곱해 더합니다. (%d × %d + %d × %d) ÷ (%d + %d) = %s입니다.' % (a,loss_a,b,loss_b,a,b,result),
        params={'a':a,'b':b,'loss_a':loss_a,'loss_b':loss_b})


@gen('i10-g05', unit='10f', step='10f/3', facts=['F10-17'], tags=['micro'], level=2, prio=2,
     ref=['10차시 슬 p28'], basis='lecture-formula', family='micro-single-label', errata=['X10-03'])
def micro_single(r):
    """정정한 합계 규칙으로 전체 클래스를 포함한 단일 라벨 분류의 micro F1을 계산함."""
    total = r.int(5,80)
    correct = r.int(1,total-1)
    result = Fraction(correct,total)
    return blank(stem='분수로 답해도 됩니다. 정답과 예측이 샘플마다 하나인 분류에서 전체 클래스를 평가합니다. %d개 중 %d개를 맞혔다면 micro F1은 ____ 입니다.' % (total,correct),
        blanks=[{'answer':[str(result)],'mode':'number'}],
        explain='정정: 전체 클래스를 포함한 단일 라벨 분류에서는 micro F1과 정확도가 같습니다. %d ÷ %d = %s입니다.' % (correct,total,result),
        params={'total':total,'correct':correct})
