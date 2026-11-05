"""14차시 학습률·해제 시간표·잔차 투영의 조건을 생성함. 표준 라이브러리만 사용함."""
from decimal import Decimal
from aiprep.gen import blank, gen


@gen('i14-g01',unit='14c',tags=['차등 학습률'],ref=['14차시 과제 6번'],facts=['F14-301'],step='14c/3',basis='lecture-formula',family='lr-groups')
def groups(r):
    """SGD의 그룹 학습률과 정해진 기울기로 한 번 갱신함. 모멘텀·정규화 없음."""
    initial=r.int(2,20); grad=r.int(1,20); base=Decimal(r.int(1,9))/100
    factor=r.pick([Decimal('0.1'),Decimal('0.2'),Decimal('0.5')]); lr=base*factor; out=Decimal(initial)-lr*grad
    return blank(stem=f'모멘텀과 weight decay가 없는 SGD입니다. 생성자 lr={base}이고 한 그룹 lr는 그 값의 {factor}배입니다. 이 그룹의 파라미터 값 {initial}, 기울기 {grad}를 한 번 갱신하면 ____ 입니다.',
                 blanks=[{'answer':[str(out)],'mode':'number'}],explain=f'그룹 lr는 {lr}입니다. {initial}-{lr}×{grad}={out}입니다.',params=dict(initial=initial,grad=grad,base=str(base),factor=str(factor)))


@gen('i14-g02',unit='14d',tags=['LambdaLR'],ref=['14차시 슬 p13'],facts=['F14-401'],step='14d/3',basis='lecture-formula',family='lambda-lr')
def schedule(r):
    """함수 인덱스와 초기 학습률을 지문에 명시함. 매번 초기값을 기준으로 계산함."""
    base=Decimal(r.int(1,20))/100; boundary=r.int(2,8); index=r.int(boundary,boundary+8); factor=r.pick([Decimal('0.1'),Decimal('0.2'),Decimal('0.25'),Decimal('0.5')])
    out=base*factor
    return blank(stem=f'LambdaLR의 초기 lr는 {base}입니다. 함수는 인덱스 e가 {boundary} 미만이면 1, 그 이상이면 {factor}를 반환합니다. 현재 함수 인덱스가 {index}이면 lr는 ____ 입니다.',
                 blanks=[{'answer':[str(out)],'mode':'number'}],explain=f'초기값 {base}×{factor}={out}이며 직전 lr에 반복해서 곱하지 않습니다.',params=dict(base=str(base),boundary=boundary,index=index,factor=str(factor)))


@gen('i14-g03',unit='14e',tags=['점진적 해제'],ref=['14차시 슬 p15'],facts=['F14-501'],step='14e/3',basis='lecture-formula',family='gradual-unfreeze')
def unfreeze(r):
    """첫 구간은 fc만, 이후 최대 네 블록을 해제함. 에폭 번호는 1부터 셈."""
    k=r.int(2,9); epoch=r.int(1,k*6); count=min(4,(epoch-1)//k)
    return blank(stem=f'에폭은 1부터 셉니다. 첫 {k}에폭은 fc만 학습하고 이후 {k}에폭마다 백본 블록 하나를 추가로 해제합니다. 백본은 총 4블록입니다. {epoch}번 에폭에 해제한 백본 블록은 ____ 개입니다. fc는 세지 않습니다.',
                 blanks=[{'answer':[str(count)],'mode':'number','unit':'개'}],explain=f'해제 수는 min(4,({epoch}-1)//{k})={count}입니다. 첫 구간에는 백본을 해제하지 않습니다.',params=dict(k=k,epoch=epoch))


@gen('i14-g04',unit='14g',tags=['잔차 연결'],ref=['14차시 노트북 01 [14]','문서 ResNet 원 논문'],facts=['F14-703'],step='14g/3',basis='lecture-formula',family='residual-shape')
def projection(r):
    """직접 경로의 bias 없는 1×1 합성곱 weight만 셈. BN 원소는 포함하지 않음."""
    ci=r.int(4,64); co=r.int(65,192)
    answer=ci*co
    return blank(stem=f'잔차 블록의 직접 경로에서 입력 {ci}채널을 출력 {co}채널로 맞추는 1×1 합성곱을 사용합니다. groups=1이고 bias=False입니다. 이 합성곱의 weight 원소는 ____ 개입니다. BN 파라미터는 포함하지 않습니다.',
                 blanks=[{'answer':[str(answer)],'mode':'number','unit':'개'}],explain=f'출력 채널×입력 채널×1×1={co}×{ci}={answer}개입니다.',params=dict(ci=ci,co=co))
