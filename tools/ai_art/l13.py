"""13차시 그림을 수치와 조건으로 그리며 창을 띄우지 않음."""
from tools.ai_art import figure
from tools.ai_art.levels import grid, chain, graph

DATA = {'13a-1': {'rows': [['이미지', '백본', '분류기'], ['새 자료', '기존 가중치', '새 가중치']], 'cols': (), 'top': '', 'gif': False}, '13a-2': {'rows': [['방법', '갱신 대상'], ['고정 특징', '새 분류기'], ['부분 조정', '마지막 블록과 분류기'], ['전체 조정', '백본과 분류기']], 'cols': (), 'top': '', 'gif': False}, '13a-3': {'rows': [['설정', '제어 대상'], ['requires_grad', '파라미터 기울기'], ['train 또는 eval', 'BN과 Dropout 동작']], 'cols': (), 'top': '', 'gif': False}, '13b-1': {'rows': [['위치', '왼쪽', '오른쪽'], ['위', '1', '3'], ['아래', '5', '7'], ['전체 평균', '4', '']], 'cols': (), 'top': '', 'gif': True}, '13b-2': {'rows': [['축', '입력', '출력'], ['배치', '3', '3'], ['채널', '2', '2'], ['공간', '2×2', '1×1']], 'cols': (), 'top': '', 'gif': False}, '13b-31': {'rows': [[1, 3], [5, 7]], 'cols': (), 'top': ''}, '13b-32': {'rows': [[1, 3], [5, 7]], 'cols': (), 'top': ''}, '13b-33': {'rows': [['N', 'C', 'H', 'W'], [3, 2, 2, 2]], 'cols': (), 'top': ''}, '13b-3': {'rows': [['연산', '출력'], ['GAP', '3, 2, 1, 1'], ['flatten 시작 1', '3, 2'], ['Linear(2, 3)', '3, 3']], 'cols': (), 'top': '', 'gif': False}, '13c-1': {'rows': [['단계', '입력 수', '출력 수'], ['원 fc', '512', '1000'], ['새 fc', '512', '3']], 'cols': (), 'top': '', 'gif': False}, '13c-2': {'rows': [['구성', '개수'], ['새 weight', '1536'], ['새 bias', '3'], ['새 분류기 합', '1539']], 'cols': (), 'top': '', 'gif': False}, '13c-31': {'kind': 'chain', 'values': ['4', '3'], 'labels': ['입력 자리', '결과 자리']}, '13c-32': {'rows': [[4, 3]], 'cols': (), 'top': ''}, '13c-33': {'rows': [[4, 3]], 'cols': (), 'top': ''}, '13c-3': {'rows': [['순서', '작업'], ['1', '기존 파라미터 고정'], ['2', 'fc 교체와 장치 이동'], ['3', '새 fc로 optimizer 생성']], 'cols': (), 'top': '', 'gif': False}, '13d-1': {'rows': [['풀링 수', '공간 변'], ['0', '112'], ['2', '28'], ['4', '7'], ['5', '3']], 'cols': (), 'top': '', 'gif': False}, '13d-2': {'rows': [['입력', '풀링 수', '공간 변'], ['112', '5', '3'], ['112', '4', '7'], ['224', '5', '7']], 'cols': (), 'top': '', 'gif': False}, '13d-31': {'kind': 'chain', 'values': ['32', '16', '8'], 'labels': ['처음', '한 번', '두 번']}, '13d-32': {'rows': [[32, 2, 2, 2, 2]], 'cols': (), 'top': ''}, '13d-33': {'rows': [[32, 512]], 'cols': (), 'top': ''}, '13d-3': {'rows': [['위치', '입력', '출력'], ['첫 Linear', '25088', '4096'], ['마지막 Linear', '4096', '3']], 'cols': (), 'top': '', 'gif': False}, '13e-1': {'rows': [['정답', '순위', 'Top-1', 'Top-3'], ['B', 'A B D C', '오답', '정답'], ['C', 'C A B D', '정답', '정답']], 'cols': (), 'top': '', 'gif': False}, '13e-2': {'rows': [['지표', '오답 수', '전체'], ['Top-1', '2', '6'], ['Top-3', '1', '6']], 'cols': (), 'top': '', 'gif': False}, '13e-31': {'kind': 'chain', 'values': ['6', '2'], 'labels': ['전체', '틀림']}, '13e-32': {'rows': [[2, 6, 100]], 'cols': (), 'top': ''}, '13e-33': {'rows': [[6, 8]], 'cols': (), 'top': ''}, '13e-3': {'rows': [['고정할 조건', '확인 항목'], ['가중치', 'V1 또는 V2 명시'], ['입력', '크기와 정규화'], ['평가', '같은 자료와 지표']], 'cols': (), 'top': '', 'gif': False}, '13f-1': {'rows': [['모델', '연결 특징'], ['AlexNet', '합성곱 5층과 FC 3층'], ['VGG', '3×3을 연속으로 배치']], 'cols': (), 'top': '', 'gif': False}, '13f-2': {'rows': [['갈래', '출력 채널'], ['1×1', '8'], ['3×3', '12'], ['5×5', '4'], ['풀링 뒤 1×1', '6']], 'cols': (), 'top': '', 'gif': False}, '13f-3': {'rows': [['연결', '조건', '결과'], ['채널 이어 붙이기', '같은 공간', '채널 수 합'], ['원소별 더하기', '같은 모양', '모양 유지']], 'cols': (), 'top': '', 'gif': False}, '13g-1': {'rows': [['순서', '대상'], ['1', 'classifier[1] 교체'], ['2', '모델 장치 이동'], ['3', 'optimizer 생성']], 'cols': (), 'top': '', 'gif': False}, '13g-2': {'rows': [['채널', '평균', '표준편차'], ['R', '0.485', '0.229'], ['G', '0.456', '0.224'], ['B', '0.406', '0.225']], 'cols': (), 'top': '', 'gif': False}, '13g-3': {'rows': [['시점', '할 일'], ['학습 전', '새 층과 optimizer 확인'], ['입력 전', '가중치별 변환 확인'], ['표시 전', '정규화 역변환']], 'cols': (), 'top': '', 'gif': False}}

def draw(spec, mark=None):
    if spec.get("kind") == "chain":
        return chain(spec["values"], labels=spec.get("labels", []), note=spec.get("note", ""), mark=mark, color="orange")
    if spec.get("kind") == "graph":
        return graph(spec["xs"], [(spec["ys"], "blue", spec["label"])], xlabel=spec["xlabel"], ylabel=spec["ylabel"], top=spec.get("top", ""))
    return grid(spec["rows"], col_names=spec.get("cols", []), row_names=spec.get("labels", []), top=spec.get("top", ""), marks=[] if mark is None else [(mark, c) for c in range(len(spec["rows"][0]))], color="orange", code=spec.get("code", False))

@figure('13a-1', width=520, height=280)
def fig_0():
    return draw(DATA['13a-1'])

@figure('13a-2', width=520, height=280)
def fig_1():
    return draw(DATA['13a-2'])

@figure('13a-3', width=520, height=280)
def fig_2():
    return draw(DATA['13a-3'])

@figure('13b-1', width=520, height=280)
def fig_3():
    return [draw(DATA['13b-1'], mark=i) for i in range(len(DATA['13b-1']["rows"]))]

@figure('13b-2', width=520, height=280)
def fig_4():
    return draw(DATA['13b-2'])

@figure('13b-31', width=520, height=280)
def fig_5():
    return draw(DATA['13b-31'])

@figure('13b-32', width=520, height=280)
def fig_6():
    return draw(DATA['13b-32'])

@figure('13b-33', width=520, height=280)
def fig_7():
    return draw(DATA['13b-33'])

@figure('13b-3', width=520, height=280)
def fig_8():
    return draw(DATA['13b-3'])

@figure('13c-1', width=520, height=280)
def fig_9():
    return draw(DATA['13c-1'])

@figure('13c-2', width=520, height=280)
def fig_10():
    return draw(DATA['13c-2'])

@figure('13c-31', width=520, height=280)
def fig_11():
    return draw(DATA['13c-31'])

@figure('13c-32', width=520, height=280)
def fig_12():
    return draw(DATA['13c-32'])

@figure('13c-33', width=520, height=280)
def fig_13():
    return draw(DATA['13c-33'])

@figure('13c-3', width=520, height=280)
def fig_14():
    return draw(DATA['13c-3'])

@figure('13d-1', width=520, height=280)
def fig_15():
    return draw(DATA['13d-1'])

@figure('13d-2', width=520, height=280)
def fig_16():
    return draw(DATA['13d-2'])

@figure('13d-31', width=520, height=280)
def fig_17():
    return draw(DATA['13d-31'])

@figure('13d-32', width=520, height=280)
def fig_18():
    return draw(DATA['13d-32'])

@figure('13d-33', width=520, height=280)
def fig_19():
    return draw(DATA['13d-33'])

@figure('13d-3', width=520, height=280)
def fig_20():
    return draw(DATA['13d-3'])

@figure('13e-1', width=520, height=280)
def fig_21():
    return draw(DATA['13e-1'])

@figure('13e-2', width=520, height=280)
def fig_22():
    return draw(DATA['13e-2'])

@figure('13e-31', width=520, height=280)
def fig_23():
    return draw(DATA['13e-31'])

@figure('13e-32', width=520, height=280)
def fig_24():
    return draw(DATA['13e-32'])

@figure('13e-33', width=520, height=280)
def fig_25():
    return draw(DATA['13e-33'])

@figure('13e-3', width=520, height=280)
def fig_26():
    return draw(DATA['13e-3'])

@figure('13f-1', width=520, height=280)
def fig_27():
    return draw(DATA['13f-1'])

@figure('13f-2', width=520, height=280)
def fig_28():
    return draw(DATA['13f-2'])

@figure('13f-3', width=520, height=280)
def fig_29():
    return draw(DATA['13f-3'])

@figure('13g-1', width=520, height=280)
def fig_30():
    return draw(DATA['13g-1'])

@figure('13g-2', width=520, height=280)
def fig_31():
    return draw(DATA['13g-2'])

@figure('13g-3', width=520, height=280)
def fig_32():
    return draw(DATA['13g-3'])
