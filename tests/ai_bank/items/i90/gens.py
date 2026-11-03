# -*- coding: utf-8 -*-
"""시험 차시 생성기. 경사하강 한 걸음과 배치 수."""
from decimal import Decimal

from aiprep.gen import blank, gen, register


@gen("i90-g01", unit="90a", level=2, tags=["경사하강"], ref=["90차시 슬 p2"], facts=["F90-03"], basis="lecture-formula",
     step="90a/2", prio=3, family="one-step")
def one_step(r):
    """W 에서 학습률과 기울기의 곱을 뺀 새 W. W 1~9, 기울기 −20~20(0 빼고), 학습률 0.1·0.01."""
    w = r.int(1, 9)
    g = r.pick([v for v in range(-20, 21) if v])
    lr = r.pick(["0.1", "0.01"])
    new = Decimal(w) - Decimal(lr) * Decimal(g)
    shown = format(new.normalize(), "f")
    return blank(
        stem="W가 %d, 기울기가 %s, 학습률이 %s일 때 한 번 옮긴 W는 ____ 입니다." % (w, str(g).replace("-", "−"), lr),
        blanks=[{"answer": [shown], "mode": "number", "hint": "숫자"}],
        explain="W에서 학습률과 기울기의 곱을 뺍니다. %d − %s × (%s) = %s 입니다." % (w, lr, str(g).replace("-", "−"), shown),
        params={"w": w, "g": g, "lr": lr})


register("i90-g02", base="batches", unit="90b", ranges={"n": [100, 1000], "b": [16, 32, 64]}, level=2, tags=["배치 수"],
         ref=["90차시 노트북 01 [3]"], facts=["F90-08"], basis="lecture-example", step="90b/4", family="batches")
