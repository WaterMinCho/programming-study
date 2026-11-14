"""16차시 합성곱·크기·풀링·Flatten·파라미터 계산을 생성함."""
from fractions import Fraction
from aiprep.gen import gen,blank


@gen('i16-g01',unit='16a',tags=['합성곱 계산'],ref=['16차시 슬 p4'],facts=['F16-101'],step='16a/3',basis='lecture-formula',family='cross-correlation')
def corr(r):
    """커널을 뒤집지 않는 2×2 창 하나를 계산함. 단일 채널, bias 0임."""
    x=[r.int(-3,9) for _ in range(4)];k=[r.int(-2,2) for _ in range(4)];ans=sum(a*b for a,b in zip(x,k))
    return blank(stem=f'한 채널의 창 [[{x[0]},{x[1]}],[{x[2]},{x[3]}]]에 필터 [[{k[0]},{k[1]}],[{k[2]},{k[3]}]]를 뒤집지 않고 곱해 더합니다. bias=0인 출력 값은 ____ 입니다.',blanks=[{'answer':[str(ans)],'mode':'number'}],explain=f'같은 위치의 네 곱을 더하면 {ans}입니다.',params=dict(x=x,k=k))


@gen('i16-g02',unit='16b',tags=['Conv 출력 크기'],ref=['16차시 슬 p5'],facts=['F16-201'],step='16b/3',basis='lecture-formula',family='conv-output-size')
def conv_size(r):
    """dilation 1, 명시한 정수 padding과 stride로 내림 계산함."""
    h=r.int(12,60);k=r.pick([3,5,7]);p=r.int(0,3);s=r.int(1,4);ans=(h+2*p-k)//s+1
    return blank(stem=f'입력 한 변 H={h}, 커널 K={k}, 양쪽 padding P={p}, stride S={s}, dilation=1입니다. floor((H+2P-K)/S)+1로 계산한 출력 한 변은 ____ 입니다.',blanks=[{'answer':[str(ans)],'mode':'number'}],explain=f'({h}+2×{p}-{k})를 {s}로 나눈 몫에 1을 더하면 {ans}입니다.',params=dict(h=h,k=k,p=p,s=s))


@gen('i16-g03',unit='16c',tags=['풀링 계산'],ref=['16차시 슬 p9'],facts=['F16-302'],step='16c/3',basis='lecture-example',family='pool-values')
def pooling(r):
    """padding 없는 2×2 창의 최댓값 또는 정확한 평균을 계산함."""
    x=[r.int(0,24) for _ in range(4)];form=r.pick(['max','mean']);ans=max(x) if form=='max' else Fraction(sum(x),4)
    call='MaxPool2d' if form=='max' else 'AvgPool2d'
    return blank(stem=f'한 채널의 2×2 창 값은 {x}입니다. padding 없이 {call}(2,2)를 적용한 값은 ____ 입니다. 평균은 분수나 유한소수로 써도 됩니다.',blanks=[{'answer':[str(ans)],'mode':'number'}],explain=f'{"최댓값" if form=="max" else "네 값의 평균"}을 구하면 {ans}입니다.',params=dict(x=x,form=form))


@gen('i16-g04',unit='16d',tags=['CNN Flatten'],ref=['16차시 과제 5번'],facts=['F16-401'],step='16d/3',basis='lecture-formula',family='cnn-flatten-chain')
def flatten_size(r):
    """공간을 유지하는 합성곱과 2×2 풀링을 명시한 수만큼 반복함."""
    side=r.int(16,80);count=r.int(1,3);c=r.int(4,48);last=side//(2**count);ans=c*last*last
    return blank(stem=f'입력 공간은 {side}×{side}입니다. 합성곱은 공간 크기를 유지하고 MaxPool2d(2,2,padding=0,ceil_mode=False)를 {count}번 거칩니다. 마지막 채널이 {c}개일 때 배치를 제외한 Flatten 길이는 ____ 입니다.',blanks=[{'answer':[str(ans)],'mode':'number'}],explain=f'공간 변은 {last}가 됩니다. {c}×{last}×{last}={ans}개입니다.',params=dict(side=side,count=count,c=c))


@gen('i16-g05',unit='16e',tags=['CNN 파라미터'],ref=['16차시 슬 p16'],facts=['F16-501'],step='16e/3',basis='lecture-formula',family='cnn-params')
def parameters(r):
    """groups=1인 Conv의 bias 포함 여부를 지문에 지정함."""
    ci=r.int(1,16);co=r.int(2,32);k=r.pick([1,3,5]);bias=r.pick([True,False]);ans=ci*co*k*k+(co if bias else 0)
    return blank(stem=f'Conv2d({ci},{co},kernel_size={k},groups=1,bias={bias})의 학습 파라미터 수는 ____ 개입니다. 입력 높이와 너비는 충분히 크다고 가정합니다.',blanks=[{'answer':[str(ans)],'mode':'number','unit':'개'}],explain=f'weight {ci*co*k*k}개와 bias {co if bias else 0}개를 합하면 {ans}개입니다.',params=dict(ci=ci,co=co,k=k,bias=bias))


@gen('i16-g06', unit='16g', tags=['SVHN CNN'], ref=['16차시 노트북 02 [11]'], facts=['F16-701', 'F16-702'],
     step='16g/2', basis='lecture-formula', family='three-pool-classifier')
def svhn_classifier(r):
    """공간 유지 Conv와 세 번의 풀링 뒤 특징 수 또는 첫 Linear 원소 수를 계산함."""
    side = r.pick([24, 32, 40, 48, 56])
    channels = r.pick([32, 64, 96, 128])
    hidden = r.pick([64, 128, 256, 512])
    form = r.pick(['features', 'linear'])
    width = side // 8
    features = channels * width * width
    answer = features if form == 'features' else (features + 1) * hidden
    condition = (f'입력 공간은 {side}×{side}입니다. 공간을 유지하는 Conv 뒤에 padding=0, ceil_mode=False인 '
                 f'MaxPool2d(2,2)를 세 번 적용하고 마지막 채널 수는 {channels}입니다. ')
    question = ('이미지 하나의 Flatten 길이' if form == 'features' else
                f'펼친 특징을 받는 첫 Linear의 출력 수가 {hidden}일 때 bias 포함 파라미터 수')
    return blank(stem=condition + question + '는 ____ 입니다.',
                 blanks=[{'answer': [str(answer)], 'mode': 'number'}],
                 explain=f'공간 한 변은 {width}, 특징 수는 {channels}×{width}×{width}={features}입니다. '
                         + (f'첫 Linear는 {features}×{hidden}+{hidden}={answer}개입니다.' if form == 'linear' else '배치 수는 곱하지 않습니다.'),
                 params=dict(side=side, channels=channels, hidden=hidden, form=form))


@gen('i16-g07', unit='16d', step='16d/4', facts=['F16-401', 'F16-403'], level=3,
     family='flatten-linear-repair', basis='lecture-example', tags=['Flatten', 'Linear 입력'],
     ref=['16차시 노트북 01 [8]', '16차시 과제 5번', 'PyTorch 문서 Flatten'])
def flatten_linear_repair(r):
    """배치 축과 Linear 입력 수를 각각 바꿔 필요한 수정 줄을 고르게 함."""
    from aiprep.gen import choice
    n, c, h, w = r.int(2, 5), r.pick([2, 4, 8]), r.int(2, 6), r.int(2, 6)
    classes = r.pick([3, 5, 10])
    start_dim = r.pick([0, 1])
    features = c * h * w
    in_features = r.pick([features, n * features])
    change_flatten, change_linear = start_dim != 1, in_features != features
    code = (f'x = torch.zeros({n}, {c}, {h}, {w})\n'
            f'flat = nn.Flatten(start_dim={start_dim})\n'
            f'fc = nn.Linear({in_features}, {classes})\ny = fc(flat(x))')
    options = [
        ('수정하지 않습니다.', not change_flatten and not change_linear,
         '현재 두 설정이 모두 목표와 맞는지 확인합니다.'),
        ('flat의 start_dim만 1로 바꿉니다.', change_flatten and not change_linear,
         'fc의 입력 수가 이미 맞을 때 이 수정만으로 연결됩니다.'),
        (f'fc의 첫 인자만 {features}로 바꿉니다.', not change_flatten and change_linear,
         'flat이 이미 배치 축을 남길 때 이 수정만으로 연결됩니다.'),
        (f'flat의 start_dim을 1로, fc의 첫 인자를 {features}로 바꿉니다.', change_flatten and change_linear,
         '두 설정이 모두 어긋났을 때 필요한 수정입니다.')]
    before_shape = [n, features] if start_dim == 1 else [n * features]
    after = ('fc 입력 수와 맞지 않아 마지막 줄에서 오류가 납니다.' if before_shape[-1] != in_features
             else f'코드는 실행되지만 결과 shape은 [{classes}]라 이미지별 출력이 사라집니다.' if start_dim == 0
             else f'현재 코드도 목표 shape인 [{n}, {classes}]를 만듭니다.')
    return choice(
        stem=(f'x의 축 순서는 배치·채널·높이·너비입니다. 이미지 {n}개를 각각 분류해 y.shape이 '
              f'[{n}, {classes}]가 되게 하려 합니다. 이미 맞는 설정은 그대로 둘 때, 필요한 수정은 무엇인가요?'
              f'\n\n```python\n{code}\n```'),
        options=options,
        explain=(f'이미지 하나의 특징 수는 {c} × {h} × {w} = {features}입니다. '
                 f'배치 축을 남기면 [{n}, {features}]가 되고 Linear는 마지막 축의 {features}개 값을 받습니다. '
                 f'현재 flat(x)의 shape은 {before_shape}입니다. {after}'),
        params={'n': n, 'c': c, 'h': h, 'w': w, 'classes': classes,
                'start_dim': start_dim, 'in_features': in_features})


flatten_linear_repair.gen_spec.meta.update(template_revision='flatten-linear-repair-1', author_difficulty=3,
                                           display_params=['n', 'c', 'h', 'w', 'classes', 'start_dim', 'in_features'])
