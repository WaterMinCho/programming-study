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
