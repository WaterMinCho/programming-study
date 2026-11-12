"""16차시 그림을 수치와 조건으로 그리며 창을 띄우지 않음."""
from tools.ai_art import figure
from tools.ai_art.levels import grid, chain, graph

DATA = {'16a-1': {'rows': [[1, 2, 4], [0, 3, 5], [2, 1, 6]], 'gif': False}, '16a-2': {'rows': [['항목', '새 모델의 설정'], ['입력 채널', '3'], ['출력 채널', '8'], ['커널', '3×3']], 'gif': False}, '16a-3': {'rows': [['상황', '해석'], ['stride 1 내부', '특징 위치도 이동'], ['padding 경계', '추가 조건 확인'], ['stride 2', '샘플 위치 변화']], 'gif': False}, '16b-1': {'rows': [['H', 'K', 'P', 'S'], ['17', '3', '1', '2']], 'gif': False}, '16b-2': {'rows': [['축', '입력', '출력'], ['N', '4', '4'], ['C', '3', '8'], ['H', '17', '9'], ['W', '19', '10']], 'gif': False}, '16b-31': {'kind': 'chain', 'values': ['17', '1', '1'], 'labels': ['처음', '왼쪽 추가', '오른쪽 추가']}, '16b-32': {'rows': [[17, 3, 1, 2]]}, '16b-33': {'rows': [[4, 3, 17, 19]]}, '16b-3': {'kind': 'graph', 'xs': [15, 16, 17, 18], 'ys': [8, 8, 9, 9], 'xlabel': '입력 한 변', 'ylabel': '출력 한 변', 'label': '출력', 'top': '커널 3 · 패딩 1 · 간격 2', 'gif': False}, '16c-1': {'rows': [['연산', '값'], ['전', '-2,1,5,8'], ['ReLU 뒤', '0,1,5,8']], 'gif': False}, '16c-2': {'rows': [[1, 2], [5, 8]], 'gif': False}, '16c-31': {'rows': [[1, 2, 5, 8]], 'top': '작은 값부터 큰 값으로'}, '16c-32': {'rows': [[1, 2], [5, 8]], 'top': '(1 + 2 + 5 + 8) ÷ 4칸'}, '16c-33': {'rows': [[1, 2], [5, 8]]}, '16c-3': {'rows': [['연산', '공간 변'], ['Conv 5', '28'], ['Pool 2', '14'], ['Conv 5', '10'], ['Pool 2', '5']], 'gif': False}, '16d-1': {'rows': [['구간', '채널', '공간'], ['입력', '3', '24×24'], ['첫 블록', '8', '12×12'], ['둘째 블록', '12', '6×6']], 'gif': False}, '16d-2': {'rows': [['단계', '출력 모양'], ['특징', 'N,12,6,6'], ['Flatten', 'N,432'], ['분류기 끝', 'N,4']], 'gif': False}, '16d-31': {'kind': 'chain', 'values': ['8', '2'], 'labels': ['처음', '절반 기준']}, '16d-32': {'rows': [[8, 2, 2]]}, '16d-33': {'rows': [[8, 12]]}, '16d-3': {'rows': [['입력 변', '최종 공간', '특징 길이'], ['24', '6×6', '432'], ['32', '8×8', '768']], 'gif': False}, '16e-1': {'rows': [['층', 'weight', 'bias'], ['Conv 3→8', '216', '8'], ['Conv 8→12', '864', '12']], 'gif': False}, '16e-2': {'rows': [['층', '파라미터 수'], ['Conv 1', '224'], ['Conv 2', '876'], ['Linear 1', '8660'], ['Linear 2', '84']], 'gif': False}, '16e-3': {'rows': [['요인', '변하는 대상'], ['채널과 커널', 'Conv weight'], ['Flatten 길이', '첫 Linear'], ['실행 장치', '실제 시간']], 'gif': False}, '16f-1': {'rows': [['입력', '기대 출력'], ['2,3,24,24', '2,4']], 'gif': False}, '16f-2': {'rows': [['표본 수', '배치 평균', '가중 합'], ['4', '1', '4'], ['4', '2', '8'], ['2', '3', '6']], 'gif': False}, '16f-3': {'rows': [['모델 구성', 'eval 효과'], ['Conv·ReLU·Pool·Linear', '기본 수식 유지'], ['BN·Dropout 추가', '평가 동작으로 변경']], 'gif': False}}

def draw(spec, mark=None):
    if spec.get("kind") == "chain":
        return chain(spec["values"], labels=spec.get("labels", []), note=spec.get("note", ""), mark=mark, color="orange")
    if spec.get("kind") == "graph":
        from tools.ai_art import canvas, COLORS
        fig, ax = canvas(520, 280)
        ax.plot(spec["xs"], spec["ys"], "o", color=COLORS["blue"], markersize=12)
        ax.set_xticks(spec["xs"])
        ax.set_yticks(sorted(set(spec["ys"])))
        ax.set_xlabel(spec["xlabel"], fontsize=22)
        ax.set_ylabel(spec["ylabel"], fontsize=22)
        ax.set_title(spec.get("top", ""), fontsize=22)
        ax.tick_params(labelsize=22)
        ax.grid(alpha=0.25)
        return fig
    return grid(spec["rows"], col_names=spec.get("cols", []), row_names=spec.get("labels", []), top=spec.get("top", ""), marks=[] if mark is None else [(mark, c) for c in range(len(spec["rows"][0]))], color="orange", code=spec.get("code", False))

@figure('16a-1', width=520, height=280)
def fig_0():
    return draw(DATA['16a-1'])

@figure('16a-2', width=520, height=280)
def fig_1():
    return draw(DATA['16a-2'])

@figure('16a-3', width=520, height=280)
def fig_2():
    return draw(DATA['16a-3'])

@figure('16b-1', width=520, height=280)
def fig_3():
    return draw(DATA['16b-1'])

@figure('16b-2', width=520, height=280)
def fig_4():
    return draw(DATA['16b-2'])

@figure('16b-31', width=520, height=280)
def fig_5():
    return draw(DATA['16b-31'])

@figure('16b-32', width=520, height=280)
def fig_6():
    return draw(DATA['16b-32'])

@figure('16b-33', width=520, height=280)
def fig_7():
    return draw(DATA['16b-33'])

@figure('16b-3', width=520, height=280)
def fig_8():
    return draw(DATA['16b-3'])

@figure('16c-1', width=520, height=280)
def fig_9():
    return draw(DATA['16c-1'])

@figure('16c-2', width=520, height=280)
def fig_10():
    return draw(DATA['16c-2'])

@figure('16c-31', width=520, height=280)
def fig_11():
    return draw(DATA['16c-31'])

@figure('16c-32', width=520, height=280)
def fig_12():
    return draw(DATA['16c-32'])

@figure('16c-33', width=520, height=280)
def fig_13():
    return draw(DATA['16c-33'])

@figure('16c-3', width=520, height=280)
def fig_14():
    return draw(DATA['16c-3'])

@figure('16d-1', width=520, height=280)
def fig_15():
    return draw(DATA['16d-1'])

@figure('16d-2', width=520, height=280)
def fig_16():
    return draw(DATA['16d-2'])

@figure('16d-31', width=520, height=280)
def fig_17():
    return draw(DATA['16d-31'])

@figure('16d-32', width=520, height=280)
def fig_18():
    return draw(DATA['16d-32'])

@figure('16d-33', width=520, height=280)
def fig_19():
    return draw(DATA['16d-33'])

@figure('16d-3', width=520, height=280)
def fig_20():
    return draw(DATA['16d-3'])

@figure('16e-1', width=520, height=280)
def fig_21():
    return draw(DATA['16e-1'])

@figure('16e-2', width=520, height=280)
def fig_22():
    return draw(DATA['16e-2'])

@figure('16e-3', width=520, height=280)
def fig_23():
    return draw(DATA['16e-3'])

@figure('16f-1', width=520, height=280)
def fig_24():
    return draw(DATA['16f-1'])

@figure('16f-2', width=520, height=280)
def fig_25():
    return draw(DATA['16f-2'])

@figure('16f-3', width=520, height=280)
def fig_26():
    return draw(DATA['16f-3'])
