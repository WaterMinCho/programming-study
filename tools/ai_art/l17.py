"""17차시 그림을 수치와 조건으로 그리며 창을 띄우지 않음."""
from tools.ai_art import figure
from tools.ai_art.levels import grid, chain, graph

DATA = {'17a-1': {'rows': [['순서', '작업'], ['1', '소문자와 토큰화'], ['2', '어휘와 번호'], ['3', '자르기와 패딩']], 'gif': False}, '17a-2': {'rows': [['항목', '의미'], ['PAD 0', '길이 채우기'], ['UNK 1', '모르는 토큰'], ['최대 길이 5', '자르기와 뒤 채우기']], 'gif': False}, '17a-31': {'kind': 'chain', 'values': ['5', '3'], 'labels': ['전체 자리', '채운 자리']}, '17a-32': {'rows': [[3, 5, 4]]}, '17a-33': {'rows': [[2, 4, 7, 8, 9]]}, '17a-3': {'rows': [['분할', '어휘 작업'], ['학습', '빈도와 어휘 결정'], ['검증·시험', '같은 대응으로 변환']], 'gif': False}, '17b-1': {'rows': [['대상', '모양'], ['weight', '12,4'], ['한 토큰', '4'], ['번호 범위', '0~11']], 'gif': False}, '17b-2': {'rows': [['축', '길이'], ['문장', '3'], ['토큰 자리', '5'], ['벡터 값', '4']], 'gif': False}, '17b-31': {'kind': 'chain', 'values': ['1', '3', '2', '4'], 'labels': ['앞', '다음', '다음', '끝']}, '17b-32': {'rows': [[3, 5, 4]]}, '17b-33': {'rows': [[12, 4]]}, '17b-3': {'rows': [['설정', '제어하는 것'], ['padding_idx', '표의 특정 행 기울기'], ['문장 실제 길이', 'LSTM 계산 구간'], ['모델 마스크', '지원 연산의 참조 범위']], 'gif': False}, '17c-1': {'rows': [['부분', '조절할 값'], ['망각 게이트', '이전 셀 상태'], ['입력 게이트', '새 후보'], ['출력 게이트', '은닉 상태 출력']], 'gif': False}, '17c-2': {'rows': [['대상', '1층 양방향 모양'], ['입력', '3,5,4'], ['output', '3,5,12'], ['h_n', '2,3,6'], ['연결 상태', '3,12']], 'gif': False}, '17c-31': {'kind': 'chain', 'values': ['3', '5'], 'labels': ['문장 수', '자리 수']}, '17c-32': {'rows': [[6, 6]]}, '17c-33': {'rows': [[2, 2, 3, 6]]}, '17c-3': {'rows': [['구분', '읽을 대상'], ['마지막 층 두 방향', 'h_n[-2]와 h_n[-1]'], ['뒤 PAD 제외', '실제 길이'], ['분류기 입력', '두 방향 특징 연결']], 'gif': False}, '17d-1': {'rows': [['구성', '참조 방식'], ['LSTM', '시간별 상태 전달'], ['인코더 attention', '허용 위치 가중합'], ['마스크', '참조 범위 제한']], 'gif': False}, '17d-2': {'rows': [['길이', '동적 목표'], ['3', '6'], ['6', '6']], 'gif': False}, '17d-3': {'rows': [['항목', '원 논문 수'], ['BERT-base', '110M'], ['DistilBERT', '66M'], ['남은 비율', '60%']], 'gif': False}, '17e-1': {'rows': [['단위', '세는 것'], ['TF', '한 문서의 토큰 횟수'], ['DF', '등장한 문서 수'], ['N', '전체 문서 수']], 'gif': False}, '17e-2': {'rows': [['정의', '설정'], ['이 예 IDF', 'ln(N/(DF+1))'], ['단어 가중치', 'TF×IDF'], ['정규화', '이 예에서는 없음']], 'gif': False}, '17e-3': {'rows': [['대상', '코사인', '거리'], ['1,0 과 2,0', '1', '1'], ['1,0 과 0,1', '0', '약 1.414']], 'gif': False}, '17e-4': {'rows': [['표현', '만드는 방법'], ['TF-IDF', '토큰 빈도와 문서 빈도'], ['Embedding', '과제 손실로 벡터 학습'], ['CBOW', '주변에서 중심 토큰 예측']], 'gif': False}}

def draw(spec, mark=None):
    if spec.get("kind") == "chain":
        return chain(spec["values"], labels=spec.get("labels", []), note=spec.get("note", ""), mark=mark, color="orange")
    if spec.get("kind") == "graph":
        return graph(spec["xs"], [(spec["ys"], "blue", spec["label"])], xlabel=spec["xlabel"], ylabel=spec["ylabel"], top=spec.get("top", ""))
    return grid(spec["rows"], col_names=spec.get("cols", []), row_names=spec.get("labels", []), top=spec.get("top", ""), marks=[] if mark is None else [(mark, c) for c in range(len(spec["rows"][0]))], color="orange", code=spec.get("code", False))

@figure('17a-1', width=520, height=280)
def fig_0():
    return draw(DATA['17a-1'])

@figure('17a-2', width=520, height=280)
def fig_1():
    return draw(DATA['17a-2'])

@figure('17a-31', width=520, height=280)
def fig_2():
    return draw(DATA['17a-31'])

@figure('17a-32', width=520, height=280)
def fig_3():
    return draw(DATA['17a-32'])

@figure('17a-33', width=520, height=280)
def fig_4():
    return draw(DATA['17a-33'])

@figure('17a-3', width=520, height=280)
def fig_5():
    return draw(DATA['17a-3'])

@figure('17b-1', width=520, height=280)
def fig_6():
    return draw(DATA['17b-1'])

@figure('17b-2', width=520, height=280)
def fig_7():
    return draw(DATA['17b-2'])

@figure('17b-31', width=520, height=280)
def fig_8():
    return draw(DATA['17b-31'])

@figure('17b-32', width=520, height=280)
def fig_9():
    return draw(DATA['17b-32'])

@figure('17b-33', width=520, height=280)
def fig_10():
    return draw(DATA['17b-33'])

@figure('17b-3', width=520, height=280)
def fig_11():
    return draw(DATA['17b-3'])

@figure('17c-1', width=520, height=280)
def fig_12():
    return draw(DATA['17c-1'])

@figure('17c-2', width=520, height=280)
def fig_13():
    return draw(DATA['17c-2'])

@figure('17c-31', width=520, height=280)
def fig_14():
    return draw(DATA['17c-31'])

@figure('17c-32', width=520, height=280)
def fig_15():
    return draw(DATA['17c-32'])

@figure('17c-33', width=520, height=280)
def fig_16():
    return draw(DATA['17c-33'])

@figure('17c-3', width=520, height=280)
def fig_17():
    return draw(DATA['17c-3'])

@figure('17d-1', width=520, height=280)
def fig_18():
    return draw(DATA['17d-1'])

@figure('17d-2', width=520, height=280)
def fig_19():
    return draw(DATA['17d-2'])

@figure('17d-3', width=520, height=280)
def fig_20():
    return draw(DATA['17d-3'])

@figure('17e-1', width=520, height=280)
def fig_21():
    return draw(DATA['17e-1'])

@figure('17e-2', width=520, height=280)
def fig_22():
    return draw(DATA['17e-2'])

@figure('17e-3', width=520, height=280)
def fig_23():
    return draw(DATA['17e-3'])

@figure('17e-4', width=520, height=280)
def fig_24():
    return draw(DATA['17e-4'])
