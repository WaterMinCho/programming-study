import math
import sys
import random
import numpy as np
import torch
from pathlib import Path

from inspect_gaps import select_query_gaps, build_time_feature

# 팀원 input_check.py와 동일한 시드 설정
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


# 1. 테스트용 개념 번호표
names = ["<PAD>", "<UNK>", "demo", "loop"]


# 2. 시간 정보를 아는 경우
print("===== 테스트 1. 시간 확인 가능 =====")

result = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 86400.0, 0.0],
    known=[False, False, True, False],
    names=names
)

assert len(result) == 1
assert result[0]["concept_name"] == "demo"
assert result[0]["gap_seconds"] == 86400.0
assert math.isclose(result[0]["gap_log"], math.log(2))
assert result[0]["time_feature"][1] == 1

# 숫자 입력 변환 기능 검증
feature = build_time_feature(
    [0, 0, 1, 0],
    [0.0, 0.0, 86400.0, 0.0],
    [False, False, True, False],
    names
)

assert len(feature) == 2
assert math.isclose(feature[0], math.log(2))
assert feature[1] == 1

print("통과:", result[0]["time_feature"])


# 3. 시간 정보를 모르는 경우
print("\n===== 테스트 2. 시간 미확인 =====")

result_unknown = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 0.0, 0.0],
    known=[False, False, False, False],
    names=names
)

assert len(result_unknown) == 1
assert result_unknown[0]["gap_seconds"] is None
assert result_unknown[0]["gap_days"] is None
assert result_unknown[0]["time_feature"] == [0.0, 0]

print("통과:", result_unknown[0]["time_feature"])


# 4. 실제 0초와 시간 미확인 구분
print("\n===== 테스트 3. 실제 0초 =====")

result_zero = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 0.0, 0.0],
    known=[False, False, True, False],
    names=names
)

assert result_zero[0]["gap_seconds"] == 0.0
assert result_zero[0]["gap_days"] == 0.0
assert result_zero[0]["time_feature"] == [0.0, 1]

assert (
    result_unknown[0]["time_feature"]
    != result_zero[0]["time_feature"]
)


print("실제 0초:", result_zero[0]["time_feature"])



# 5. 이번 문제와 다른 개념 제외
print("\n===== 테스트 4. 다른 개념 제외 =====")

result = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 86400.0, 604800.0],
    known=[False, False, True, True],
    names=names
)

assert len(result) == 1
assert result[0]["concept_name"] == "demo"
assert result[0]["gap_seconds"] == 86400.0

print("통과: loop의 7일 간격이 제외됨")


# 6. 한 문제에 여러 개념이 있는 경우
print("\n===== 테스트 5. 다중 개념의 최단 간격 =====")

result = select_query_gaps(
    concepts=[0, 0, 1, 1],
    seconds=[0.0, 0.0, 172800.0, 86400.0],
    known=[False, False, True, True],
    names=names
)

assert len(result) == 1
assert result[0]["concept_name"] == "loop"
assert result[0]["gap_seconds"] == 86400.0
assert math.isclose(result[0]["gap_log"], math.log(2))

# 미확인 개념의 0초를 최단 시간으로 오해하지 않는지 확인
mixed = select_query_gaps(
    concepts=[0, 0, 1, 1],
    seconds=[0.0, 0.0, 0.0, 86400.0],
    known=[False, False, False, True],
    names=names
)

assert len(mixed) == 1
assert mixed[0]["concept_name"] == "loop"
assert mixed[0]["gap_seconds"] == 86400.0

print("통과: 확인된 가장 짧은 시간 하나만 선택")


# 7. 실제 자료에서 과거 풀이가 없는 사람의 기록 사용
print("\n===== 테스트 6. 실제 자료의 빈 이력 =====")

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

DATASET_PATH = (
    PROJECT_ROOT.parent
    / "study-data"
    / "common-input-f8-20261118"
    / "recorded"
)

TRACK = "ai"
SPLIT = "train"

if not (DATASET_PATH / "manifest.json").is_file():
    raise FileNotFoundError(
        f"v8 실제 데이터가 없습니다: {DATASET_PATH}"
    )

from learning_server.input_example import load, batch

rows, vocabulary = load(
    str(DATASET_PATH),
    TRACK,
    SPLIT
)

# 과거 풀이가 0개인 실제 이벤트 검색
empty_row = None

for row in rows:
    history = row.get(
        "features", {}
    ).get("sequence_history", [])

    if history is not None and len(history) == 0:
        empty_row = row
        break

assert empty_row is not None, (
    "과거 이력이 0개인 실제 기록을 찾지 못했습니다."
)

# 실제 기록을 팀원과 동일한 공통 입력 방식으로 변환
example = batch(
    [empty_row],
    vocabulary,
    length=32
)

raw_inputs = example["inputs"]

assert int(raw_inputs["lengths"][0]) == 0

assert not any(
    bool(value)
    for value in raw_inputs["mask"][0]
)

result = select_query_gaps(
    raw_inputs["query_concepts"][0],
    raw_inputs["query_gap_seconds"][0],
    raw_inputs["query_gap_known"][0],
    vocabulary["concepts"]
)

feature = build_time_feature(
    raw_inputs["query_concepts"][0],
    raw_inputs["query_gap_seconds"][0],
    raw_inputs["query_gap_known"][0],
    vocabulary["concepts"]
)

assert len(result) <= 1
assert len(feature) == 2

assert feature == [0.0, 0], (
    "빈 이력에서 시간이 확인된 상태입니다. "
    "공통 입력의 기록 범위와 집계 로직을 점검하세요."
)

print("통과: 실제 v8 레코드에서 이력 0개 확인")
print("통과: 실제 빈 이력의 시간 특성", feature)
print("\n전체 6개 테스트 완료")
