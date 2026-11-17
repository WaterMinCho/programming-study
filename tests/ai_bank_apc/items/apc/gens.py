"""응용 코딩 실습 시험용 수치 문항."""
from aiprep.gen import blank, gen


@gen("apc-g101", unit="a18a", step="a18a/1", facts=["FA18-05"], tags=["묶음 수"],
     ref=["응용 90차시 노트북 01 [2]"], basis="lecture-formula", family="aapc-batches")
def batches(r):
    """남은 표본도 한 묶음에 담을 때 묶음 수를 계산함."""
    n, size = r.int(20, 180), r.int(3, 12)
    return blank(stem=f"표본 {n}개를 한 묶음에 {size}개씩 담습니다. 마지막 남은 표본도 담으면 전체 묶음 수는 ____ 입니다.",
                 blanks=[{"answer": [str((n + size - 1) // size)], "mode": "number"}],
                 explain="남은 표본이 있으면 한 묶음을 더 만듭니다.", params={"n": n, "size": size})
