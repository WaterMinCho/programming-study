# -*- coding: utf-8 -*-
"""여정 입력 생성기가 쓰는 난수와 도우미. 문제의 gen.py 는 이 모듈만 import 함.

같은 시드면 어느 컴퓨터, 어느 Python 판(3.10~3.14), 어느 프로세스에서나 같은 수열이 나와야 함. 기대값의 sha 가
입력 하나에 묶여 있어서 입력이 달라지면 모든 학생에게 그 테스트가 오답으로 보임. 그래서 random 모듈을 쓰지 않고
splitmix64 를 직접 두며, 겹침을 막을 때는 set 대신 넣은 순서를 지키는 dict 를 씀. 수를 바꾸면 기대값이 모두 바뀜.
"""
MASK = (1 << 64) - 1
GOLDEN = 0x9E3779B97F4A7C15
MIX1 = 0xBF58476D1CE4E5B9
MIX2 = 0x94D049BB133111EB
LOWER = "abcdefghijklmnopqrstuvwxyz_"


class Rng(object):
    """splitmix64 난수. 64비트 상태 하나로 돌고 정수 연산만 씀."""

    def __init__(self, seed):
        self.state = seed & MASK

    def next64(self):
        self.state = (self.state + GOLDEN) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * MIX1) & MASK
        z = ((z ^ (z >> 27)) * MIX2) & MASK
        return z ^ (z >> 31)

    def below(self, n):
        """0 <= x < n."""
        if n <= 0:
            raise ValueError("below 의 n 은 1 이상이어야 합니다: %r" % (n,))
        return (self.next64() * n) >> 64

    def between(self, lo, hi):
        """lo <= x <= hi."""
        if hi < lo:
            raise ValueError("between 의 범위가 비었습니다: %r, %r" % (lo, hi))
        return lo + self.below(hi - lo + 1)

    def chance(self, num, den):
        return self.below(den) < num

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, seq):
        """피셔-예이츠. 자리를 바꾼 같은 리스트를 돌려줌."""
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]
        return seq

    def sample(self, seq, k):
        """서로 다른 자리 k 개를 shuffle 과 같은 방식으로 앞에서부터 고름."""
        items = list(seq)
        if k > len(items):
            raise ValueError("sample 의 k 가 원소 수보다 큽니다: %r > %r" % (k, len(items)))
        for i in range(k):
            j = i + self.below(len(items) - i)
            items[i], items[j] = items[j], items[i]
        return items[:k]


def word(rng, lo, hi, alphabet=LOWER):
    """길이가 lo 이상 hi 이하인 단어 하나."""
    length = rng.between(lo, hi)
    letters = []
    for _ in range(length):
        letters.append(alphabet[rng.below(len(alphabet))])
    return "".join(letters)


def distinct_words(rng, n, lo, hi, alphabet=LOWER):
    """겹치지 않는 단어 n 개를 뽑은 순서대로. 가능한 단어 수가 n 보다 적으면 ValueError."""
    possible = 0
    for length in range(lo, hi + 1):
        possible += len(alphabet) ** length
    if possible < n:
        raise ValueError("길이 %d~%d, 글자 %d개로는 서로 다른 단어를 %d개 만들 수 없습니다" % (lo, hi, len(alphabet), n))
    seen = {}
    while len(seen) < n:
        candidate = word(rng, lo, hi, alphabet)
        if candidate not in seen:
            seen[candidate] = True
    return list(seen)
