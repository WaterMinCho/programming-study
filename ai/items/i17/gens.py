"""17차시 패딩·Embedding·LSTM·TF-IDF 계산을 생성함. 표준 라이브러리만 사용함."""
import math
from aiprep.gen import gen,blank,fixed


@gen('i17-g01',unit='17a',tags=['토큰과 패딩'],ref=['17차시 노트북 01 [12]'],facts=['F17-102'],step='17a/3',basis='lecture-formula',family='token-padding')
def padding(r):
    """최대 길이로 자른 뒤 부족한 부분만 채움. 앞 자르기 없이 뒤를 자름."""
    limit=r.int(4,32);length=r.int(1,45);ans=max(0,limit-length)
    return blank(stem=f'토큰 길이 {length}를 앞에서 최대 {limit}개만 남기고 뒤를 PAD로 채웁니다. 최종 길이는 {limit}입니다. 추가한 PAD는 ____ 개입니다.',blanks=[{'answer':[str(ans)],'mode':'number','unit':'개'}],explain=f'남긴 길이는 {min(limit,length)}입니다. 목표와의 차이 {ans}개를 채웁니다.',params=dict(limit=limit,length=length))


@gen('i17-g02',unit='17b',tags=['Embedding'],ref=['17차시 노트북 01 [15]'],facts=['F17-201'],step='17b/3',basis='lecture-formula',family='embedding-shape')
def embedding(r):
    """표의 파라미터 수와 출력 모양을 나누어 물음. 새 표를 전부 학습함."""
    v=r.int(20,300);d=r.int(2,32);b=r.int(2,12);t=r.int(3,30);form=r.pick(['weight','shape'])
    answer=str(v*d) if form=='weight' else f'({b},{t},{d})';mode='number' if form=='weight' else 'shape'
    q=f'Embedding({v},{d})의 weight 원소 수' if form=='weight' else f'Embedding({v},{d})에 유효한 long 번호 텐서 ({b},{t})를 넣은 출력 모양'
    return blank(stem=q+('는' if form=='weight' else '은')+' ____ 입니다.',blanks=[{'answer':[answer],'mode':mode}],explain=f'표 모양은 ({v},{d})이고 출력은 ({b},{t},{d})입니다.',params=dict(v=v,d=d,b=b,t=t,form=form))


@gen('i17-g03',unit='17c',tags=['LSTM 모양'],ref=['17차시 과제 3번','PyTorch 문서 LSTM'],facts=['F17-303'],step='17c/3',basis='lecture-formula',family='lstm-shape')
def lstm(r):
    """1층·projection 없음·bias=True인 LSTM의 방향별 파라미터를 계산함."""
    i=r.int(2,32);h=r.int(2,32);bi=r.pick([True,False]);dirs=2 if bi else 1;ans=dirs*(4*h*i+4*h*h+8*h)
    return blank(stem=f'PyTorch의 1층 nn.LSTM은 방향마다 b_ih·b_hh 두 편향 벡터를 사용합니다. input_size={i}, hidden_size={h}, bidirectional={bi}, bias=True, proj_size=0입니다. 전체 학습 파라미터는 ____ 개입니다.',blanks=[{'answer':[str(ans)],'mode':'number','unit':'개'}],explain=f'방향 하나는 4H×I+4H×H+8H={ans//dirs}개입니다. 방향 수 {dirs}를 곱하면 {ans}개입니다.',params=dict(i=i,h=h,bi=bi))


@gen('i17-g04',unit='17e',tags=['TF-IDF'],ref=['17차시 노트북 00 [3]'],facts=['F17-502'],step='17e/3',basis='lecture-formula',family='tfidf-formula')
def tfidf(r):
    """노트북 식을 명시하며 문서별 L2 정규화는 하지 않음. 중간값을 반올림하지 않음."""
    n=r.int(3,30);df=r.int(1,n);tf=r.int(1,8);ans=fixed(tf*math.log(n/(df+1)),4)
    return blank(stem=f'문서 수 N={n}, 토큰이 등장한 문서 수 DF={df}, 한 문서의 토큰 횟수 TF={tf}입니다. IDF=ln(N/(DF+1))로 정의하고 문서별 정규화는 하지 않습니다. 중간값을 반올림하지 않은 TF×IDF를 소수 넷째 자리까지 쓰면 ____ 입니다.',blanks=[{'answer':[ans],'mode':'number','places':4}],explain=f'{tf}×ln({n}/({df}+1))≈{ans}입니다. scikit-learn의 기본 IDF 식과 구분합니다.',params=dict(n=n,df=df,tf=tf))


@gen('i17-g05', unit='17f', tags=['분류 지표'], ref=['17차시 노트북 02 [8]'], facts=['F17-605'],
     step='17f/5', basis='lecture-formula', family='binary-metrics')
def classification_metrics(r):
    """분모가 0이 아닌 정수 집계에서 accuracy 또는 양성 1의 F1을 계산함."""
    tp, tn, fp, fn = r.int(1, 12), r.int(0, 12), r.int(0, 12), r.int(0, 12)
    form = r.pick(['accuracy', 'f1'])
    value = (tp + tn) / (tp + tn + fp + fn) if form == 'accuracy' else 2 * tp / (2 * tp + fp + fn)
    answer = fixed(value, 4)
    name = 'accuracy=(TP+TN)/(TP+TN+FP+FN)' if form == 'accuracy' else 'F1=2TP/(2TP+FP+FN)'
    return blank(stem=f'양성 클래스를 1로 정합니다. TP={tp}, TN={tn}, FP={fp}, FN={fn}입니다. '
                      f'{name}을 중간값 반올림 없이 계산한 뒤 소수 다섯째 자리에서 반올림하여 넷째 자리까지 쓰면 ____ 입니다.',
                 blanks=[{'answer': [answer], 'mode': 'number', 'places': 4}],
                 explain=f'지문에 정한 {"accuracy" if form == "accuracy" else "F1"} 식에 집계값을 넣고 마지막에 반올림하면 {answer}입니다.',
                 params=dict(tp=tp, tn=tn, fp=fp, fn=fn, form=form))
