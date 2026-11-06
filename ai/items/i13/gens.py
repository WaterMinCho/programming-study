"""13차시 공간 평균·분류기·풀링·Top-k 계산을 생성함. 표준 라이브러리만 사용함."""
from decimal import Decimal
from aiprep.gen import blank, gen, fixed


@gen('i13-g01', unit='13b', tags=['적응형 평균 풀링'], ref=['13차시 노트북 01 [10]'],
     facts=['F13-201'], step='13b/3', basis='lecture-example', family='gap-shape')
def gap(r):
    """배치와 채널은 유지하며 출력 공간을 1×1로 지정함."""
    n, c, h, w = r.int(2, 12), r.int(2, 32), r.int(2, 20), r.int(2, 20)
    return blank(stem=f'입력 ({n}, {c}, {h}, {w})에 AdaptiveAvgPool2d((1,1))와 torch.flatten(x,1)을 순서대로 적용한 모양은 ____ 입니다.',
                 blanks=[{'answer': [f'({n}, {c})'], 'mode': 'shape'}],
                 explain=f'출력 공간은 1×1입니다. 배치 축을 남기고 펴면 ({n}, {c})입니다.', params=dict(n=n,c=c,h=h,w=w))


@gen('i13-g02', unit='13c', tags=['분류기 교체'], ref=['13차시 노트북 01 [26]'],
     facts=['F13-302'], step='13c/3', basis='lecture-formula', family='transfer-head-params')
def head(r):
    """분류기 교체 전후의 전체 파라미터 수를 계산함."""
    f, old, new = r.pick([64, 128, 256, 512, 1280]), r.int(20, 50), r.int(2, 12)
    backbone = r.int(20, 200)*1000
    total = backbone+f*old+old
    answer = backbone+f*new+new
    return blank(stem=f'bias가 있는 Linear({f},{old})를 Linear({f},{new})로 교체합니다. 교체 전 모델 전체 파라미터가 {total}개이면 교체 뒤에는 ____ 개입니다. 다른 층은 바꾸지 않습니다.',
                 blanks=[{'answer': [str(answer)], 'mode': 'number', 'unit': '개'}],
                 explain=f'원 분류기 {f*old+old}개를 빼고 새 분류기 {f*new+new}개를 더하면 {answer}개입니다.', params=dict(f=f,old=old,new=new,total=total))


@gen('i13-g03', unit='13d', tags=['VGG 공간 크기'], ref=['13차시 노트북 01 [72]'],
     facts=['F13-402'], step='13d/3', basis='lecture-formula', family='vgg-pool-chain')
def pool(r):
    """합성곱은 공간 크기와 채널 수를 유지하는 축소 모형임. 풀링은 padding 0, ceil_mode=False임."""
    side, count, channels = r.int(32, 256), r.int(2, 4), r.pick([8,16,32,64])
    out = side
    for _ in range(count):
        out = (out-2)//2+1
    answer = channels*out*out
    return blank(stem=f'입력은 (3,{channels},{side},{side})입니다. 채널과 공간을 유지하는 합성곱 사이에 MaxPool2d(2,2)를 {count}번 적용합니다. padding은 0, ceil_mode는 False이며 마지막은 Identity입니다. 배치 축을 남기고 펴면 이미지 하나의 특징 수는 ____ 입니다.',
                 blanks=[{'answer':[str(answer)],'mode':'number'}],
                 explain=f'각 공간 변을 {count}번 내림 나눗셈하면 {out}입니다. 특징 수는 {channels}×{out}×{out}={answer}입니다.', params=dict(side=side,count=count,channels=channels))


@gen('i13-g04', unit='13e', tags=['Top-k 오차'], ref=['13차시 슬 p6'],
     facts=['F13-501'], step='13e/3', basis='lecture-formula', family='topk-error')
def topk(r):
    """후보에 정답이 없는 개수를 백분율로 바꿈. 백분율 기호도 받음."""
    total=r.int(20,200); wrong=r.int(1,total-1); k=r.int(2,5)
    ans=fixed(Decimal(wrong*100)/Decimal(total),1)
    return blank(stem=f'자료 {total}개 가운데 상위 {k}개 후보에 정답이 없는 자료가 {wrong}개입니다. Top-{k} 오차율을 소수 첫째 자리까지 쓰면 ____ %입니다.',
                 blanks=[{'answer':[ans],'mode':'number','places':1,'unit':'%'}],
                 explain=f'오답 수를 전체 수로 나눠 100을 곱합니다. {wrong}÷{total}×100≈{ans}%입니다.',params=dict(total=total,wrong=wrong,k=k))
