"""15차시 크기 변환·픽셀 범위·마지막 배치를 생성함. 표준 라이브러리만 사용함."""
from decimal import Decimal
from aiprep.gen import gen,blank,fixed


@gen('i15-g01',unit='15b',tags=['Resize와 Crop'],ref=['15차시 노트북 01 [13]'],facts=['F15-201'],step='15b/3',basis='lecture-formula',family='resize-crop')
def resize(r):
    """종횡비가 유리수인 정수 크기를 골라 반올림 경계를 피함. max_size 없음."""
    short=r.int(4,12)*20;ratio=r.int(2,5);long=short*ratio;target=r.int(2,9)*16
    ans=target*ratio
    return blank(stem=f'RGB 이미지 가로 {long}, 세로 {short}에 Resize({target})를 적용합니다. max_size는 지정하지 않습니다. 출력 가로는 ____ 픽셀입니다.',blanks=[{'answer':[str(ans)],'mode':'number','unit':'픽셀'}],explain=f'짧은 변의 비율 {target}÷{short}을 긴 변에도 적용합니다. 출력 가로는 {ans}입니다.',params=dict(long=long,short=short,target=target))


@gen('i15-g02',unit='15c',tags=['픽셀 정규화'],ref=['15차시 노트북 01 [14]'],facts=['F15-302'],step='15c/3',basis='lecture-formula',family='pixel-normalize')
def normalize(r):
    """uint8 픽셀을 255로 나누고 고정 상수로 정규화함. 소수 셋째 자리로 반올림하며 중간값은 반올림하지 않음."""
    pixel=r.int(0,255);out=(Decimal(pixel)/255-Decimal('.5'))/Decimal('.5');answer=fixed(out,3)
    return blank(stem=f'RGB uint8 픽셀 {pixel}을 ToTensor로 바꾼 뒤 (x-0.5)/0.5로 정규화합니다. 결과를 소수 셋째 자리까지 쓰면 ____ 입니다.',blanks=[{'answer':[answer],'mode':'number','places':3}],explain=f'(2×{pixel}-255)÷255를 마지막에 반올림하면 {answer}입니다.',params=dict(pixel=pixel))


@gen('i15-g03',unit='15d',tags=['마지막 배치'],ref=['15차시 노트북 01 [21]'],facts=['F15-402'],step='15d/3',basis='lecture-formula',family='loader-last-batch')
def batches(r):
    """drop_last=False인 배치 수와 마지막 배치 크기를 나눠 물음."""
    size=r.int(3,32);n=r.int(size+1,size*20);count=(n+size-1)//size;last=n-(count-1)*size
    form=r.pick(['count','last']);ans=count if form=='count' else last
    asked='전체 배치 수' if form=='count' else '마지막 배치의 표본 수'
    return blank(stem=f'표본 {n}개를 batch_size={size}, drop_last=False로 읽습니다. 기본 샘플링에서 {asked}는 ____ 입니다.',blanks=[{'answer':[str(ans)],'mode':'number'}],explain=f'배치 수는 올림한 {count}이며 마지막에는 {last}개를 보냅니다.',params=dict(n=n,size=size,form=form))
