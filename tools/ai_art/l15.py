"""15차시 그림을 수치와 조건으로 그리며 창을 띄우지 않음."""
from tools.ai_art import figure
from tools.ai_art.levels import grid, chain, graph

DATA = {'15a-1': {'rows': [['경로', '클래스로 읽는 이름'], ['root=train', 'bird·cloud·flower'], ['root=상위 폴더', 'train·val']], 'gif': False}, '15a-2': {'rows': [['이름', '번호'], ['bird', '0'], ['cloud', '1'], ['flower', '2']], 'gif': False}, '15a-3': {'rows': [['점검', '읽을 속성'], ['클래스 순서', 'classes'], ['이름과 번호', 'class_to_idx'], ['전체 표본', 'len(dataset)']], 'gif': False}, '15b-1': {'rows': [['연산', '가로', '세로'], ['원본', '480', '320'], ['Resize(256)', '384', '256'], ['Resize((256,256))', '256', '256']], 'gif': False}, '15b-2': {'rows': [['단계', '가로', '세로'], ['작은 원본', '12', '8'], ['짧은 변 목표', '비율 유지', '4'], ['중앙 자르기', '4', '4']], 'gif': False}, '15b-31': {'kind': 'chain', 'values': ['12', '8'], 'labels': ['가로', '세로']}, '15b-32': {'rows': [[12, 8, 4]]}, '15b-33': {'rows': [[12, 8, 4]]}, '15b-3': {'rows': [['훈련', '검증'], ['무작위 영역 허용', '고정 영역 비교'], ['라벨 유지 확인', '평가 조건 유지']], 'gif': False}, '15c-1': {'rows': [['표현', '픽셀', '축'], ['uint8', '102', 'HWC'], ['실수', '0.4', 'CHW']], 'gif': False}, '15c-2': {'rows': [['입력', '출력'], ['0', '-1'], ['0.5', '0'], ['1', '1']], 'gif': False}, '15c-31': {'kind': 'chain', 'values': ['0', '0.5', '1'], 'labels': ['어두움', '', '밝음']}, '15c-32': {'rows': [['0.5', '0.5', '0.5']]}, '15c-33': {'rows': [[0, '0.5', 1]]}, '15c-3': {'rows': [['작업', '되돌릴 대상'], ['z×0.5+0.5', '픽셀 값'], ['축 1,2,0', 'HWC 배치']], 'gif': False}, '15d-1': {'rows': [['대상', '이미지 모양', '라벨 모양'], ['한 표본', '3,224,224', '정수 하나'], ['배치 5개', '5,3,224,224', '5']], 'gif': False}, '15d-2': {'rows': [['배치 번호', '표본 수'], ['1', '5'], ['2', '5'], ['3', '4']], 'gif': True}, '15d-31': {'kind': 'chain', 'values': ['14', '5'], 'labels': ['전체', '묶은 수']}, '15d-32': {'rows': [[14, 5]]}, '15d-33': {'rows': [[14, 5]]}, '15d-3': {'rows': [['설정', '바꾸는 것'], ['shuffle', '표본 순서'], ['batch_size', '묶음의 최대 수'], ['drop_last', '남은 묶음 전달 여부']], 'gif': False}, '15e-1': {'rows': [['메서드', '반환 값'], ['__len__', '전체 길이'], ['__getitem__', '입력과 라벨']], 'gif': False}, '15e-2': {'rows': [['항목', '모양과 조건'], ['logits', 'N,3 실수'], ['labels', 'N long'], ['라벨 범위', '0·1·2']], 'gif': False}, '15e-3': {'rows': [['검증 장수', '한 장 차이'], ['10', '10%p'], ['20', '5%p'], ['100', '1%p']], 'gif': False}}

def draw(spec, mark=None):
    if spec.get("kind") == "chain":
        return chain(spec["values"], labels=spec.get("labels", []), note=spec.get("note", ""), mark=mark, color="orange")
    if spec.get("kind") == "graph":
        return graph(spec["xs"], [(spec["ys"], "blue", spec["label"])], xlabel=spec["xlabel"], ylabel=spec["ylabel"], top=spec.get("top", ""))
    return grid(spec["rows"], col_names=spec.get("cols", []), row_names=spec.get("labels", []), top=spec.get("top", ""), marks=[] if mark is None else [(mark, c) for c in range(len(spec["rows"][0]))], color="orange", code=spec.get("code", False))

@figure('15a-1', width=520, height=280)
def fig_0():
    return draw(DATA['15a-1'])

@figure('15a-2', width=520, height=280)
def fig_1():
    return draw(DATA['15a-2'])

@figure('15a-3', width=520, height=280)
def fig_2():
    return draw(DATA['15a-3'])

@figure('15b-1', width=520, height=280)
def fig_3():
    return draw(DATA['15b-1'])

@figure('15b-2', width=520, height=280)
def fig_4():
    return draw(DATA['15b-2'])

@figure('15b-31', width=520, height=280)
def fig_5():
    return draw(DATA['15b-31'])

@figure('15b-32', width=520, height=280)
def fig_6():
    return draw(DATA['15b-32'])

@figure('15b-33', width=520, height=280)
def fig_7():
    return draw(DATA['15b-33'])

@figure('15b-3', width=520, height=280)
def fig_8():
    return draw(DATA['15b-3'])

@figure('15c-1', width=520, height=280)
def fig_9():
    return draw(DATA['15c-1'])

@figure('15c-2', width=520, height=280)
def fig_10():
    return draw(DATA['15c-2'])

@figure('15c-31', width=520, height=280)
def fig_11():
    return draw(DATA['15c-31'])

@figure('15c-32', width=520, height=280)
def fig_12():
    return draw(DATA['15c-32'])

@figure('15c-33', width=520, height=280)
def fig_13():
    return draw(DATA['15c-33'])

@figure('15c-3', width=520, height=280)
def fig_14():
    return draw(DATA['15c-3'])

@figure('15d-1', width=520, height=280)
def fig_15():
    return draw(DATA['15d-1'])

@figure('15d-2', width=520, height=280)
def fig_16():
    return [draw(DATA['15d-2'], mark=i) for i in range(len(DATA['15d-2']["rows"]))]

@figure('15d-31', width=520, height=280)
def fig_17():
    return draw(DATA['15d-31'])

@figure('15d-32', width=520, height=280)
def fig_18():
    return draw(DATA['15d-32'])

@figure('15d-33', width=520, height=280)
def fig_19():
    return draw(DATA['15d-33'])

@figure('15d-3', width=520, height=280)
def fig_20():
    return draw(DATA['15d-3'])

@figure('15e-1', width=520, height=280)
def fig_21():
    return draw(DATA['15e-1'])

@figure('15e-2', width=520, height=280)
def fig_22():
    return draw(DATA['15e-2'])

@figure('15e-3', width=520, height=280)
def fig_23():
    return draw(DATA['15e-3'])
