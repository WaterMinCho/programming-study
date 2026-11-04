# -*- coding: utf-8 -*-
"""공용 생성기. 차시마다 register 로 숫자 범위와 근거만 바꿔 붙임."""
from aiprep.gen import Retry, base, choice


@base("batches")
def batches(r, ranges):
    """한 에폭의 배치 수. 자료 수 N 을 배치 크기 B 로 나눈 값을 올림. 나누어떨어지거나 보기가 겹치면 Retry."""
    n = r.int(*ranges["n"])
    b = r.pick(ranges["b"])
    if n % b == 0:
        raise Retry("나누어떨어짐")
    right, floor, rest = -(-n // b), n // b, n % b
    texts = [str(right), str(floor), str(right + 1), str(rest)]
    if len(set(texts)) != 4:
        raise Retry("보기 겹침")
    return choice(
        stem="자료 %d개를 배치 크기 %d로 나누면 한 에폭의 배치는 몇 개일까요? **옳은** 것을 고르세요." % (n, b),
        options=[(texts[0], True, "%d ÷ %d 를 올림하면 %d 입니다. 마지막 배치는 %d개입니다." % (n, b, right, rest)),
                 (texts[1], False, "몫만 세면 남은 %d개가 빠집니다." % rest),
                 (texts[2], False, "올림한 값에 하나를 더 셀 까닭이 없습니다."),
                 (texts[3], False, "나머지는 마지막 배치에 든 자료 수입니다.")],
        pick="right",
        explain="남은 자료도 마지막 배치 하나가 되기 때문입니다. %d ÷ %d 를 올림해 %d 입니다." % (n, b, right),
        params={"n": n, "b": b})
