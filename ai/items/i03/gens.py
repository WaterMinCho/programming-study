# -*- coding: utf-8 -*-
"""3차시 생성기. squeeze·unsqueeze 를 이어 쓴 뒤의 shape, 2×2 행렬곱 값, y = a·x² + c 를 backward 한 뒤의 x.grad.

텐서 동작은 torch 없이 PyTorch 문서의 규칙대로 파이썬으로 계산함. squeeze(dim=d) 는 그 축의 크기가 1 이 아니면
그대로 두는데 numpy 의 squeeze(axis=d) 는 오류를 내므로 numpy 로 정답을 만들지 않음(factcheck i03 (c)3).
"""
from aiprep.gen import gen, blank, Retry


ORDINAL = ("첫째", "둘째", "셋째")


def shape_text(shape):
    return "[" + ", ".join(str(s) for s in shape) + "]"


@gen("i03-g01", unit="3d", step="3d/4", facts=["F03-26", "F03-27", "F03-28", "F03-29"], level=2, prio=2,
     family="squeeze-chain", basis="lecture-example", tags=["squeeze", "unsqueeze"],
     ref=["3차시 노트북 02 [59]", "3차시 노트북 02 [60]", "3차시 노트북 02 [77]"])
def squeeze_chain(r):
    """shape 하나에 squeeze(dim=d), squeeze(), unsqueeze(dim=d) 를 두세 번 차례로 쓴 뒤의 shape. 축 2~4개, 크기 1~5."""
    start = [r.pick([1, 1, 2, 3, 4, 5]) for _ in range(r.int(2, 4))]
    if 1 not in start:
        raise Retry()
    cur, ops, lines, notes = list(start), [], [], []
    for k in range(r.int(2, 3)):
        kind = r.pick(["squeeze", "squeeze", "unsqueeze", "squeeze_all"])
        if kind == "squeeze":
            d = r.pick(list(range(len(cur))) + [-1])
            idx = d % len(cur)
            if cur[idx] == 1:
                new = cur[:idx] + cur[idx + 1:]
                note = "축 %d의 크기가 1이라 지웁니다" % idx
            else:
                new = list(cur)
                note = "축 %d의 크기가 1이 아니라 그대로 둡니다" % idx
            if d == -1:
                note = note.replace("축 %d의" % idx, "맨 뒤 축(-1은 축 %d)의" % idx)
            lines.append("x = x.squeeze(dim=%d)" % d)
            ops.append(["squeeze", d])
        elif kind == "unsqueeze":
            d = r.int(0, len(cur))
            new = cur[:d] + [1] + cur[d:]
            note = "%d번 자리에 크기 1인 축을 넣습니다" % d
            lines.append("x = x.unsqueeze(dim=%d)" % d)
            ops.append(["unsqueeze", d])
        else:
            new = [s for s in cur if s != 1]
            note = "인자가 없어 크기 1인 축을 모두 지웁니다"
            lines.append("x = x.squeeze()")
            ops.append(["squeeze", None])
        if not new or len(new) > 5:
            raise Retry()
        notes.append("%s 줄은 %s → %s이고, %s니다." % (ORDINAL[k], shape_text(cur), shape_text(new), note[:-2]))
        cur = new
    stem = ("`x`의 shape이 `%s`입니다. 아래 코드를 차례로 실행한 뒤 `x.shape`은 ____ 입니다.\n\n```python\n%s\n```"
            % (shape_text(start), "\n".join(lines)))
    explain = ("squeeze(dim=d)는 d번 축의 크기가 1일 때만 지우고, unsqueeze(dim=d)는 d번 자리에 크기 1인 축을 넣습니다. "
               + " ".join(notes))
    return blank(stem=stem, blanks=[{"answer": [shape_text(cur)], "mode": "shape"}], explain=explain,
                 params={"start": start, "ops": ops})


@gen("i03-g02", unit="3e", step="3e/3", facts=["F03-33", "F03-35"], level=2, prio=2, family="matmul-values",
     basis="lecture-example", tags=["행렬곱"], ref=["3차시 노트북 02 [37]", "3차시 과제 2번"])
def matmul_2x2(r):
    """2×2 정수 행렬 둘의 행렬곱 a @ b 의 값. 원소 0~6. 원소별 곱과 결과가 같으면 다시 뽑음."""
    a = [[r.int(0, 6) for _ in range(2)] for _ in range(2)]
    b = [[r.int(0, 6) for _ in range(2)] for _ in range(2)]
    c = [[a[i][0] * b[0][j] + a[i][1] * b[1][j] for j in range(2)] for i in range(2)]
    mul = [[a[i][j] * b[i][j] for j in range(2)] for i in range(2)]
    if c == mul:
        raise Retry()
    cells = []
    for i in range(2):
        for j in range(2):
            cells.append("%d번 행과 %d번 열은 %d×%d + %d×%d = %d" % (i, j, a[i][0], b[0][j], a[i][1], b[1][j], c[i][j]))
    stem = ("다음 코드를 실행하면 `c`는 ____ 입니다.\n\n```python\na = torch.tensor(%s)\nb = torch.tensor(%s)\nc = a @ b\n```"
            % (str(a), str(b)))
    explain = ("행렬곱의 (i, j) 칸은 a의 i번 행과 b의 j번 열을 자리끼리 곱해 더한 값입니다. " + ", ".join(cells)
               + "입니다. 같은 자리끼리 곱하는 `a * b`였다면 %s입니다." % str(mul))
    return blank(stem=stem, blanks=[{"answer": [str(c)], "mode": "values"}], explain=explain,
                 params={"a": a, "b": b})


@gen("i03-g03", unit="3g", step="3g/4", facts=["F03-45", "F03-47", "F03-50"], level=2, prio=3, family="grad-power",
     basis="lecture-example", tags=["backward", "미분"], ref=["3차시 슬 p14", "3차시 과제 3번", "3차시 노트북 01 [85]"])
def grad_quadratic(r):
    """y = a·x² + c 를 x0 에서 backward 한 뒤의 x.grad. a 1~5, c 0~5, x0 −3~4. 셋에 하나는 지우지 않고 두 번 부름."""
    a, c, x0 = r.int(1, 5), r.int(0, 5), r.int(-3, 4)
    if (a, c, x0) in ((3, 2, 4), (2, 2, 1), (2, 2, 3)):  # 과제 3번과 학습 노트에 나온 숫자
        raise Retry()
    twice = r.chance(1 / 3)
    once = 2 * a * x0
    grad = 2 * once if twice else once
    head = "x**2" if a == 1 else "%d * x**2" % a
    expr = head if c == 0 else "%s + %d" % (head, c)
    calc = ["y = %s" % expr, "y.backward()"]
    code = ["x = torch.tensor(%d.0, requires_grad=True)" % x0] + calc + (calc if twice else [])
    stem = "다음 코드를 실행한 뒤 `x.grad`의 값은 ____ 입니다.\n\n```python\n%s\n```" % "\n".join(code)
    slope = "2x" if a == 1 else "%dx" % (2 * a)
    if c:
        explain = "y를 x로 미분하면 %s이고, 더한 상수는 미분하면 0입니다." % slope
    else:
        explain = "y를 x로 미분하면 %s입니다." % slope
    explain += " x = %d일 때 미분값은 %d입니다." % (x0, once)
    if twice:
        explain += " 기울기를 지우지 않고 backward()를 두 번 불러 같은 값이 한 번 더 더해지므로 %d입니다." % grad
    return blank(stem=stem, blanks=[{"answer": [str(grad)], "mode": "number"}], explain=explain.replace("-", "−"),
                 params={"a": a, "c": c, "x0": x0, "twice": twice})


@gen("i03-g04", unit="3c", step="3c/4", facts=["F03-39"], level=2,
     family="sum-axis-values", basis="lecture-example", tags=["sum", "축"],
     ref=["3차시 노트북 02 [51]", "3차시 노트북 02 [52]", "3차시 노트북 02 [54]"])
def sum_axis(r):
    """직사각형 배열의 합과 결과 모양을 축 0·1 조건으로 바꿔 물음."""
    rows, cols = r.pick([(2, 3), (3, 2), (2, 4), (4, 2)])
    values = [[r.int(-4, 9) for _ in range(cols)] for _ in range(rows)]
    dim = r.pick([0, 1])
    groups = list(zip(*values)) if dim == 0 else values
    sums = [sum(group) for group in groups]
    code = f"x = torch.tensor({values})\ny = x.sum(dim={dim})"
    return blank(
        stem=f"다음 코드를 실행한 뒤 y의 값은 ____ 이고, y.shape은 ____ 입니다. 값과 shape은 숫자 목록으로 쓰세요.\n\n```python\n{code}\n```",
        blanks=[{"answer": [str(sums)], "mode": "values"},
                {"answer": [str([len(sums)])], "mode": "shape"}],
        explain=(f"dim={dim}은 {'세로 방향으로 같은 열' if dim == 0 else '가로 방향으로 같은 행'}의 값을 더합니다. "
                 f"합은 {sums}입니다. 더한 축이 사라져 shape은 [{len(sums)}]입니다. "
                 f"dim={1 - dim}을 사용하면 {'행마다' if dim == 0 else '열마다'} 합을 구합니다."),
        params={"values": values, "dim": dim})


sum_axis.gen_spec.meta.update(template_revision="sum-axis-values-1", author_difficulty=2,
                              display_params=["values", "dim"])
