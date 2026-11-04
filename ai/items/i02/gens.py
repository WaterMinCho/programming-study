# -*- coding: utf-8 -*-
"""2차시 생성기. reshape의 -1 자리, axis 합, 브로드캐스팅 결과 shape, 불리언 인덱싱, transpose shape 계산.

표준 라이브러리와 aiprep.gen만 씀. 숫자는 Rng 로만 고름.
"""
import re

from aiprep.gen import Retry, blank, choice, gen

RESHAPE_SIZES = (12, 18, 24, 36, 48)


def _shape_text(shape):
    """파이썬 튜플 표기. 원소 하나면 (4,) 꼴."""
    if len(shape) == 1:
        return "(%d,)" % shape[0]
    return "(" + ", ".join(str(n) for n in shape) + ")"


def _list_text(values):
    return "[" + ", ".join(str(v) for v in values) + "]"


def _josa(text, particle):
    """text 끝 숫자를 읽은 소리에 맞춰 조사를 붙임. particle 은 받침이 있을 때 꼴(은·이·을·과·으로·이라).
    숫자로 끝나면 띄우고 괄호나 코드 표시로 끝나면 붙임."""
    plain = {"은": "는", "이": "가", "을": "를", "과": "와", "으로": "로", "이라": "라"}[particle]
    n = int(re.search(r"(\d+)\D*$", text).group(1))
    coda = "ㅇ" if n % 10 == 0 else {1: "ㄹ", 3: "ㅁ", 6: "ㄱ", 7: "ㄹ", 8: "ㄹ"}.get(n % 10, "")
    if not coda or (particle == "으로" and coda == "ㄹ"):
        word = plain
    else:
        word = particle
    return text + (" " if text[-1].isdigit() else "") + word


def _shapes_of(total, dims):
    """원소 수 total을 길이 2 이상인 축 dims 개로 나누는 모든 shape. 순서가 정해진 목록."""
    if dims == 1:
        return [(total,)] if total >= 2 else []
    out = []
    for first in range(2, total + 1):
        if total % first == 0:
            for rest in _shapes_of(total // first, dims - 1):
                out.append((first,) + rest)
    return out


@gen("i02-g01", unit="2c", step="2c/3", level=2, tags=["reshape"], family="reshape-fill", prio=2,
     facts=["F02-29", "F02-14"], basis="lecture-example",
     ref=["2차시 노트북 01 [36]", "2차시 노트북 01 [40]", "2차시 노트북 04 [6]"])
def reshape_minus_one(r):
    """원소 N 개(12, 18, 24, 36, 48)를 축 2~3개로 나눈 shape에서 한 자리를 -1 로 가린 reshape의 결과 shape."""
    total = r.pick(RESHAPE_SIZES)
    dims = r.pick([2, 3])
    shape = r.pick(_shapes_of(total, dims))
    hole = r.int(0, dims - 1)
    asked = list(shape)
    asked[hole] = -1
    rest = 1
    for k, n in enumerate(shape):
        if k != hole:
            rest *= n
    return blank(
        stem="원소 %d개인 배열 `a`에 `a.reshape(%s)`를 하면 shape은 ____ 입니다." % (total, ", ".join(str(n) for n in asked)),
        blanks=[{"answer": [_shape_text(shape)], "mode": "shape", "hint": "모양"}],
        explain="-1 자리는 원소 수를 나머지 자리의 곱으로 나눈 몫입니다. %d ÷ %d = %s shape은 %s 입니다."
                % (total, rest, _josa(str(shape[hole]), "이라"), _shape_text(shape)),
        params={"total": total, "asked": asked})


@gen("i02-g02", unit="2e", step="2e/3", level=2, tags=["axis"], family="axis-sum", prio=3,
     facts=["F02-48"], basis="lecture-example",
     ref=["2차시 노트북 03 [11]", "2차시 노트북 03 [12]"])
def axis_sum(r):
    """2×3 또는 3×2 정수 배열(원소 0~9)의 sum(axis=0) 이나 sum(axis=1) 값."""
    rows, cols = r.pick([(2, 3), (3, 2)])
    mat = [[r.int(0, 9) for _ in range(cols)] for _ in range(rows)]
    axis = r.int(0, 1)
    if axis == 0:
        result = [sum(mat[i][j] for i in range(rows)) for j in range(cols)]
        how = "위아래로 더해 열마다 값 하나가 남습니다"
    else:
        result = [sum(row) for row in mat]
        how = "옆으로 더해 행마다 값 하나가 남습니다"
    other = [sum(mat[i][j] for i in range(rows)) for j in range(cols)] if axis == 1 else [sum(row) for row in mat]
    return blank(
        stem="`m = np.array(%s)`에서 `m.sum(axis=%d)`은 ____ 입니다." % (_list_text([_list_text(row) for row in mat]), axis),
        blanks=[{"answer": [_list_text(result)], "mode": "values", "hint": "배열"}],
        explain="axis=%d 은 %s. 결과는 %s 이고, %s axis=%d 을 준 결과입니다."
                % (axis, how, _list_text(result), _josa(_list_text(other), "은"), 1 - axis),
        params={"mat": mat, "axis": axis})


@gen("i02-g03", unit="2d", step="2d/4", level=2, tags=["브로드캐스팅"], family="broadcast-shape", prio=3,
     facts=["F02-47", "F02-43", "F02-44"], basis="lecture-example",
     ref=["2차시 노트북 03 [5]", "2차시 노트북 03 [6]", "2차시 슬 p9"])
def broadcast_shape(r):
    """(n, m) + (m,), (n,) + (m, 1), 길이가 다른 (a,) + (b,) 세 꼴의 결과 shape 고르기. 길이는 2~5 이고 서로 다르게 고름."""
    form = r.pick(["bias", "both", "error"])
    n, m = r.sample([2, 3, 4, 5], 2)
    error_text = "ValueError가 납니다."
    if form == "bias":
        left, right = (n, m), (m,)
        result = _shape_text((n, m))
        right_answer = "shape %s 인 배열이 됩니다." % result
        wrongs = [("shape %s 인 배열이 됩니다." % _shape_text((m, n)), "행과 열을 바꿔 생각함",
                   "%s %s 보고 0번 축만 늘어나므로 결과는 %s 입니다." % (
                       _josa(_shape_text((m,)), "은"), _josa("(1, %d)" % m, "으로"), result)),
                  ("shape %s 인 배열이 됩니다." % _shape_text((m,)), "작은 쪽 모양을 따른다고 생각함",
                   "브로드캐스팅은 작은 쪽을 늘려 맞추므로 결과는 큰 쪽과 같은 %s 입니다." % result),
                  (error_text, "모양이 다르면 늘 오류라고 생각함",
                   "오른쪽 끝 축의 길이가 둘 다 %s 같아 오류 없이 더할 수 있습니다." % _josa(str(m), "으로"))]
        why = "오른쪽 끝 축의 길이가 둘 다 %s 같습니다. %s %s 보아 길이 1 인 축이 %s 늘어납니다." % (
            _josa(str(m), "으로"), _josa(_shape_text((m,)), "은"), _josa("(1, %d)" % m, "으로"), _josa(str(n), "으로"))
    elif form == "both":
        left, right = (n,), (m, 1)
        result = _shape_text((m, n))
        right_answer = "shape %s 인 배열이 됩니다." % result
        wrongs = [("shape %s 인 배열이 됩니다." % _shape_text((n, m)), "축 순서를 바꿔 생각함",
                   "%s %s 보므로 %s 1번 축의 길이가 되어 결과는 %s 입니다." % (
                       _josa(_shape_text((n,)), "은"), _josa("(1, %d)" % n, "으로"), _josa(str(n), "은"), result)),
                  ("shape %s 인 배열이 됩니다." % _shape_text((m, 1)), "한쪽만 늘어난다고 생각함",
                   "(%d, 1)의 길이 1 인 1번 축도 %s 늘어나 결과는 %s 입니다." % (m, _josa(str(n), "으로"), result)),
                  (error_text, "모양이 다르면 늘 오류라고 생각함",
                   "오른쪽 끝부터 %s 1, 1 과 %s 비교하면 축마다 한쪽이 1 이라 더할 수 있습니다." % (
                       _josa(str(n), "과"), _josa(str(m), "을")))]
        why = "%s %s 보아 아래로, %s 옆으로 늘어나 둘 다 %s 됩니다." % (
            _josa(_shape_text((n,)), "은"), _josa("(1, %d)" % n, "으로"), _josa("(%d, 1)" % m, "은"), _josa(_shape_text((m, n)), "이"))
    else:
        left, right = (n,), (m,)
        right_answer = error_text
        wrongs = [("shape %s 인 배열이 됩니다." % _shape_text((max(n, m),)), "큰 쪽에 맞춘다고 생각함",
                   "늘어나는 것은 길이가 1 인 축뿐이라 길이 %s %s 큰 쪽에 맞춰지지 않습니다." % (
                       _josa(str(n), "과"), _josa(str(m), "은"))),
                  ("shape %s 인 배열이 됩니다." % _shape_text((n, m)), "두 길이를 축 둘로 펼친다고 생각함",
                   "1차원 배열 둘을 더해도 축이 새로 생기지 않아 2차원 결과는 나오지 않습니다."),
                  ("shape %s 인 배열이 됩니다." % _shape_text((m, n)), "두 길이를 축 둘로 펼친다고 생각함",
                   "%s %s 축이 하나씩이라 %s %d 만 비교하고, 둘이 달라 ValueError가 납니다." % (
                       _josa(_shape_text((n,)), "과"), _josa(_shape_text((m,)), "은"), _josa(str(n), "과"), m))]
        why = "오른쪽 끝 길이 %s %s 같지 않고 어느 쪽도 1 이 아니라 맞출 수 없습니다." % (_josa(str(n), "과"), _josa(str(m), "이"))
    options = [(right_answer, True, why)]
    for text, aim, wrong_why in wrongs:
        options.append((text, False, wrong_why))
    return choice(
        stem="shape %s 인 배열과 shape %s 인 배열을 더한 결과로 **옳은** 것을 고르세요." % (_shape_text(left), _shape_text(right)),
        options=options, pick="right",
        explain="브로드캐스팅은 두 shape을 오른쪽 끝 축부터 비교해 길이가 같거나 한쪽이 1 인 축만 맞춥니다. " + why,
        params={"left": list(left), "right": list(right), "form": form})


@gen("i02-g04", unit="2b", step="2b/3", level=2, tags=["불리언 인덱싱"], family="boolsel", prio=2,
     facts=["F02-23", "F02-24"], basis="lecture-example",
     ref=["2차시 노트북 03 [14]", "2차시 노트북 04 [28]", "2차시 과제 3번"])
def mask_select(r):
    """서로 다른 정수 5~7개(1~20)에 `>` 나 `>=` 조건을 건 불리언 인덱싱 결과. 고른 값이 하나 이상, 전부보다 적게."""
    size = r.int(5, 7)
    values = r.sample(list(range(1, 21)), size)
    op = r.pick([">", ">="])
    t = r.pick(values)
    picked = [v for v in values if (v > t if op == ">" else v >= t)]
    if not picked or len(picked) == size:
        raise Retry()
    mask = ["True" if v in picked else "False" for v in values]
    return blank(
        stem="`d = np.array(%s)` 일 때 `d[d %s %d]`의 결과는 ____ 입니다." % (_list_text(values), op, t),
        blanks=[{"answer": [_list_text(picked)], "mode": "values", "hint": "배열"}],
        explain="%s %s 마스크를 만들고 True 자리 값만 원래 순서대로 모읍니다. 그래서 결과는 원소 %d개인 %s 입니다."
                % (_josa("`d %s %d`" % (op, t), "은"), _list_text(mask), len(picked), _list_text(picked)),
        params={"values": values, "op": op, "t": t})


@gen("i02-g05", unit="2c", step="2c/5", level=2, tags=["transpose"], family="transpose-shape", prio=2,
     facts=["F02-35", "F02-36"], basis="lecture-example",
     ref=["2차시 노트북 01 [52]", "2차시 노트북 01 [55]"])
def transpose_shape(r):
    """서로 다른 길이 2~6 인 3차원 shape에 axes 순열(또는 axes 없음)을 준 np.transpose의 결과 shape."""
    shape = r.sample([2, 3, 4, 5, 6], 3)
    axes = r.pick([None, (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)])
    if axes is None:
        new = shape[::-1]
        call = "np.transpose(a)"
        how = "axes를 주지 않아 축 순서를 뒤집습니다"
    else:
        new = [shape[k] for k in axes]
        call = "np.transpose(a, (%d, %d, %d))" % axes
        how = "새 0번, 1번, 2번 축에 옛 %d번, %d번, %d번 축의 길이가 옵니다" % axes
    return blank(
        stem="shape %s 인 배열 `a`에 `%s`를 하면 shape은 ____ 입니다." % (_shape_text(shape), call),
        blanks=[{"answer": [_shape_text(new)], "mode": "shape", "hint": "모양"}],
        explain="%s. 결과 shape은 %s 입니다." % (how, _shape_text(new)),
        params={"shape": list(shape), "axes": list(axes) if axes else None})
