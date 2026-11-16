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
    return blank(stem=f'에폭은 1부터 셉니다. 1~{k}에폭은 fc만 학습하고 {k+1}번 에폭 시작에 백본 블록 하나를 해제합니다. 이후 {k}에폭마다 한 블록씩 추가로 해제하며 백본은 총 4블록입니다. {epoch}번 에폭 시작에 해제된 백본 블록은 ____ 개입니다. fc는 세지 않습니다.',
                 blanks=[{'answer':[str(count)],'mode':'number','unit':'개'}],explain=f'해제 수는 min(4,({epoch}-1)//{k})={count}입니다. 첫 구간에는 백본을 해제하지 않습니다.',params=dict(k=k,epoch=epoch))


@gen('i14-g04',unit='14g',tags=['잔차 연결'],ref=['14차시 슬 p3','문서 ResNet 원 논문'],facts=['F14-703'],step='14g/3',basis='lecture-formula',family='residual-shape')
def projection(r):
    """직접 경로의 bias 없는 1×1 합성곱 weight만 셈. BN 원소는 포함하지 않음."""
    ci=r.int(4,64); co=r.int(65,192)
    answer=ci*co
    return blank(stem=f'잔차 블록의 직접 경로에서 입력 {ci}채널을 출력 {co}채널로 맞추는 1×1 합성곱을 사용합니다. groups=1이고 bias=False입니다. 이 합성곱의 weight 원소는 ____ 개입니다. BN 파라미터는 포함하지 않습니다.',
                 blanks=[{'answer':[str(answer)],'mode':'number','unit':'개'}],explain=f'출력 채널×입력 채널×1×1={co}×{ci}={answer}개입니다.',params=dict(ci=ci,co=co))


@gen("i14-g05", unit="14b", step="14b/4", level=3, core=False, deep=False, prio=2,
     tags=["동결과 갱신", "optimizer 등록"], family="trainable-registered", basis="lecture-example",
     facts=["F14-201", "F14-202", "F14-205"],
     ref=["14차시 노트북 01 [17]", "14차시 노트북 01 [18]", "14차시 노트북 02 [33]", "PyTorch 문서 Optimizer"])
def registered_sgd_update(r):
    """등록 여부와 저장된 grad로 SGD 갱신을 판단함. requires_grad 변경은 남은 grad를 지우지 않음."""
    initial = r.int(-8, 8)
    lr = r.pick(["0.1", "0.2", "0.5"])
    registered = r.chance(0.5)
    requires_grad = r.chance(0.5)
    stored_grad = r.pick([None, -4, -2, -1, 1, 2, 4])
    parameters = "[p]" if registered else "[q]"
    grad_text = "None" if stored_grad is None else f"torch.tensor({stored_grad}.0)"
    code = (f"optimizer = torch.optim.SGD({parameters}, lr={lr}, momentum=0, weight_decay=0)\n"
            f"p.requires_grad_({requires_grad})\n"
            "optimizer.step()")
    stem = ("p와 q는 서로 다른 실수 스칼라 Parameter입니다. 코드 실행 전 p.requires_grad는 True이고 "
            f"p의 값은 {initial}.0, p.grad는 {grad_text}입니다. "
            "아래 세 줄만 실행하며 기울기를 새로 계산하거나 비우는 호출은 없습니다. "
            "부동소수점의 반올림 오차는 무시하세요.\n\n"
            f"```python\n{code}\n```\n\n"
            "optimizer.step() 직후 p의 값은 ____ 입니다.")
    value = Decimal(initial)
    if not registered:
        explain = ("이 optimizer에는 q만 등록했습니다. p의 requires_grad나 저장된 grad와 관계없이 "
                   f"이 step은 p를 갱신하지 않아 값은 {initial}입니다.")
    elif stored_grad is None:
        explain = ("p를 등록했지만 p.grad가 None이므로 SGD가 p를 건너뜁니다. "
                   f"requires_grad 값과 관계없이 저장된 기울기가 없어 값은 {initial}입니다.")
    else:
        value -= Decimal(lr) * stored_grad
        explain = (f"등록한 p에 저장된 기울기 {stored_grad}를 사용합니다. "
                   f"{initial} − {lr} × ({stored_grad}) = {value}입니다.")
        if not requires_grad:
            explain += " requires_grad를 False로 바꿔도 기존 grad를 지우지 않으므로 이번 step은 p를 갱신합니다."
    return blank(stem=stem, blanks=[{"answer": [str(value)], "mode": "number"}], explain=explain,
                 params={"initial": initial, "lr": lr, "registered": registered,
                         "requires_grad": requires_grad, "stored_grad": stored_grad})


registered_sgd_update.gen_spec.meta.update(
    template_revision="intro-registered-sgd-update-1", author_difficulty=3,
    display_params=["initial", "lr", "registered", "requires_grad", "stored_grad"])
