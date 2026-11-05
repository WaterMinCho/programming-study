"""14차시 그림을 수치와 조건으로 그리며 창을 띄우지 않음."""
from tools.ai_art import figure
from tools.ai_art.levels import grid, chain, graph

DATA = {'14a-1': {'rows': [['조건', '비교할 후보'], ['적고 비슷함', '분류기만 또는 일부 조정'], ['입력 차이 큼', '일부 또는 전체 조정'], ['자료 충분함', '전체 조정도 비교']], 'cols': (), 'top': '', 'gif': False}, '14a-2': {'rows': [['맞출 조건', '기록 내용'], ['자료', '동일 분할'], ['모델', '초기 가중치와 새 층'], ['학습', '에폭과 학습률']], 'cols': (), 'top': '', 'gif': False}, '14a-3': {'rows': [['전략', '학습 %', '검증 %'], ['가', '92', '80'], ['나', '84', '79']], 'cols': (), 'top': '', 'gif': False}, '14b-1': {'rows': [['대상', 'True 여부', '등록 여부'], ['백본', 'True', '없음'], ['분류기', 'True', '있음']], 'cols': (), 'top': '', 'gif': False}, '14b-2': {'rows': [['남은 부분', '원소 수'], ['stem', '9536'], ['10클래스 fc', '5130'], ['둘의 합', '14666']], 'cols': (), 'top': '', 'gif': False}, '14b-3': {'rows': [['검사', '확인 값'], ['기울기', 'requires_grad와 grad'], ['등록', 'param_groups'], ['BN 통계', 'train 또는 eval']], 'cols': (), 'top': '', 'gif': False}, '14c-1': {'rows': [['그룹', '학습률'], ['백본', '0.001'], ['분류기', '0.01']], 'cols': (), 'top': '', 'gif': False}, '14c-2': {'rows': [['그룹', 'lr', '기울기'], ['백본', '0.001', '2'], ['분류기', '0.01', '2']], 'cols': (), 'top': '', 'gif': False}, '14c-31': {'kind': 'chain', 'values': ['10', '2'], 'labels': ['처음', '이동 칸']}, '14c-32': {'rows': [[10, 2, '0.5']], 'cols': (), 'top': ''}, '14c-33': {'rows': [[10, 2, '0.1']], 'cols': (), 'top': ''}, '14c-3': {'rows': [['그룹', '등록 대상'], ['head', 'fc'], ['last', 'layer4'], ['rest', '나머지 전체']], 'cols': (), 'top': '', 'gif': False}, '14d-1': {'rows': [['인덱스', '배수', 'lr'], ['0~2', '1', '0.01'], ['3~5', '0.1', '0.001']], 'cols': (), 'top': '', 'gif': False}, '14d-2': {'rows': [['에폭 번호', '함수 인덱스'], ['1', '0'], ['2', '1'], ['4', '3']], 'cols': (), 'top': '', 'gif': False}, '14d-31': {'kind': 'chain', 'values': ['10', '2'], 'labels': ['묶음당', '묶음 수']}, '14d-32': {'rows': [[10, '0.5']], 'cols': (), 'top': ''}, '14d-33': {'rows': [[10, '0.1']], 'cols': (), 'top': ''}, '14d-3': {'rows': [['설정', '그룹별 의미'], ['함수 하나', '같은 배수'], ['함수 두 개', '그룹 순서대로 배수'], ['base lr 두 개', '초기값을 따로 지정']], 'cols': (), 'top': '', 'gif': False}, '14e-1': {'rows': [['에폭', '학습할 부분'], ['1~3', 'fc'], ['4~6', 'fc와 layer4'], ['7~9', 'fc와 layer4·3']], 'cols': (), 'top': '', 'gif': True}, '14e-2': {'rows': [['e', 'k', '해제 수'], ['3', '3', '0'], ['4', '3', '1'], ['7', '3', '2']], 'cols': (), 'top': '', 'gif': False}, '14e-31': {'kind': 'chain', 'values': ['1', '2', '3'], 'labels': ['첫 번호', '다음 번호', '끝 번호']}, '14e-32': {'rows': [[8, 3]], 'cols': (), 'top': ''}, '14e-33': {'rows': [[11, 3]], 'cols': (), 'top': ''}, '14e-3': {'rows': [['변경', '추가로 확인할 항목'], ['True로 해제', 'optimizer 등록'], ['새 그룹 추가', '중복 등록 없음'], ['optimizer 재생성', '이전 상태 보존']], 'cols': (), 'top': '', 'gif': False}, '14f-1': {'rows': [['원본', '면적 비율', '정사각 후보 변'], ['100×100', '0.64', '80'], ['100×100', '0.81', '90']], 'cols': (), 'top': '', 'gif': False}, '14f-2': {'rows': [['순서', '표현'], ['크롭과 반전', 'PIL 또는 지원 Tensor'], ['ToTensor', 'float Tensor'], ['정규화 뒤 지우기', '정규화 값 0']], 'cols': (), 'top': '', 'gif': False}, '14f-3': {'rows': [['구분', '변환 목적'], ['학습', '라벨을 유지하는 변형'], ['검증', '조건을 고정해 비교'], ['시험', '선택 뒤 최종 평가']], 'cols': (), 'top': '', 'gif': False}, '14g-1': {'rows': [['위치', 'x', 'F(x)', '합'], ['첫째', '2', '1', '3'], ['둘째', '5', '-2', '3']], 'cols': (), 'top': '', 'gif': False}, '14g-2': {'rows': [['경로', '입력', '출력'], ['합성곱', '64,16,16', '128,8,8'], ['투영', '64,16,16', '128,8,8']], 'cols': (), 'top': '', 'gif': False}, '14g-31': {'rows': [[2, 1], [5, -2]], 'cols': (), 'top': ''}, '14g-32': {'rows': [[1, -2]], 'cols': (), 'top': ''}, '14g-33': {'rows': [[2, 3, 4, 4]], 'cols': (), 'top': ''}, '14g-3': {'rows': [['항목', '학습 파라미터', '연산'], ['항등 직접 경로', '0', '입력 전달'], ['두 경로 합', '0', '원소별 덧셈'], ['투영 Conv', '있음', '합성곱']], 'cols': (), 'top': '', 'gif': False}, '14h-1': {'rows': [['순서', '모드'], ['바깥 model.eval', '평가'], ['함수 안 model.train', '학습'], ['하위 모듈', '함께 변경']], 'cols': (), 'top': '', 'gif': False}, '14h-2': {'rows': [['대상', '모드', '기울기'], ['백본', 'eval', '고정'], ['새 fc', 'train', '계산']], 'cols': (), 'top': '', 'gif': False}, '14h-3': {'rows': [['설정', '바꾸는 것'], ['eval', 'BN과 Dropout'], ['no_grad', '역전파 그래프 기록'], ['labels', 'long 클래스 번호']], 'cols': (), 'top': '', 'gif': False}}

def draw(spec, mark=None):
    if spec.get("kind") == "chain":
        return chain(spec["values"], labels=spec.get("labels", []), note=spec.get("note", ""), mark=mark, color="orange")
    if spec.get("kind") == "graph":
        return graph(spec["xs"], [(spec["ys"], "blue", spec["label"])], xlabel=spec["xlabel"], ylabel=spec["ylabel"], top=spec.get("top", ""))
    return grid(spec["rows"], col_names=spec.get("cols", []), row_names=spec.get("labels", []), top=spec.get("top", ""), marks=[] if mark is None else [(mark, c) for c in range(len(spec["rows"][0]))], color="orange", code=spec.get("code", False))

@figure('14a-1', width=520, height=280)
def fig_0():
    return draw(DATA['14a-1'])

@figure('14a-2', width=520, height=280)
def fig_1():
    return draw(DATA['14a-2'])

@figure('14a-3', width=520, height=280)
def fig_2():
    return draw(DATA['14a-3'])

@figure('14b-1', width=520, height=280)
def fig_3():
    return draw(DATA['14b-1'])

@figure('14b-2', width=520, height=280)
def fig_4():
    return draw(DATA['14b-2'])

@figure('14b-3', width=520, height=280)
def fig_5():
    return draw(DATA['14b-3'])

@figure('14c-1', width=520, height=280)
def fig_6():
    return draw(DATA['14c-1'])

@figure('14c-2', width=520, height=280)
def fig_7():
    return draw(DATA['14c-2'])

@figure('14c-31', width=520, height=280)
def fig_8():
    return draw(DATA['14c-31'])

@figure('14c-32', width=520, height=280)
def fig_9():
    return draw(DATA['14c-32'])

@figure('14c-33', width=520, height=280)
def fig_10():
    return draw(DATA['14c-33'])

@figure('14c-3', width=520, height=280)
def fig_11():
    return draw(DATA['14c-3'])

@figure('14d-1', width=520, height=280)
def fig_12():
    return draw(DATA['14d-1'])

@figure('14d-2', width=520, height=280)
def fig_13():
    return draw(DATA['14d-2'])

@figure('14d-31', width=520, height=280)
def fig_14():
    return draw(DATA['14d-31'])

@figure('14d-32', width=520, height=280)
def fig_15():
    return draw(DATA['14d-32'])

@figure('14d-33', width=520, height=280)
def fig_16():
    return draw(DATA['14d-33'])

@figure('14d-3', width=520, height=280)
def fig_17():
    return draw(DATA['14d-3'])

@figure('14e-1', width=520, height=280)
def fig_18():
    return [draw(DATA['14e-1'], mark=i) for i in range(len(DATA['14e-1']["rows"]))]

@figure('14e-2', width=520, height=280)
def fig_19():
    return draw(DATA['14e-2'])

@figure('14e-31', width=520, height=280)
def fig_20():
    return draw(DATA['14e-31'])

@figure('14e-32', width=520, height=280)
def fig_21():
    return draw(DATA['14e-32'])

@figure('14e-33', width=520, height=280)
def fig_22():
    return draw(DATA['14e-33'])

@figure('14e-3', width=520, height=280)
def fig_23():
    return draw(DATA['14e-3'])

@figure('14f-1', width=520, height=280)
def fig_24():
    return draw(DATA['14f-1'])

@figure('14f-2', width=520, height=280)
def fig_25():
    return draw(DATA['14f-2'])

@figure('14f-3', width=520, height=280)
def fig_26():
    return draw(DATA['14f-3'])

@figure('14g-1', width=520, height=280)
def fig_27():
    return draw(DATA['14g-1'])

@figure('14g-2', width=520, height=280)
def fig_28():
    return draw(DATA['14g-2'])

@figure('14g-31', width=520, height=280)
def fig_29():
    return draw(DATA['14g-31'])

@figure('14g-32', width=520, height=280)
def fig_30():
    return draw(DATA['14g-32'])

@figure('14g-33', width=520, height=280)
def fig_31():
    return draw(DATA['14g-33'])

@figure('14g-3', width=520, height=280)
def fig_32():
    return draw(DATA['14g-3'])

@figure('14h-1', width=520, height=280)
def fig_33():
    return draw(DATA['14h-1'])

@figure('14h-2', width=520, height=280)
def fig_34():
    return draw(DATA['14h-2'])

@figure('14h-3', width=520, height=280)
def fig_35():
    return draw(DATA['14h-3'])
