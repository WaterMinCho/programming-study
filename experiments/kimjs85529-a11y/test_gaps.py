import math

from inspect_gaps import select_query_gaps


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

# 1일 = 86400초, log1p(1) = log(2)
assert len(result) == 1
assert result[0]["concept_name"] == "demo"
assert result[0]["gap_seconds"] == 86400.0
assert math.isclose(result[0]["gap_log"], math.log(2))
assert result[0]["time_feature"][1] == 1

print("통과:", result[0]["time_feature"])


# 3. 시간 정보를 모르는 경우
print("\n===== 테스트 2. 시간 미확인 =====")

result_unknown = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 0.0, 0.0],
    known=[False, False, False, False],
    names=names
)

# 0.0, False는 실제 0초가 아니라 시간 미확인
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

# 0.0, True는 확인된 0초
assert result_zero[0]["gap_seconds"] == 0.0
assert result_zero[0]["gap_days"] == 0.0
assert result_zero[0]["time_feature"] == [0.0, 1]

# 두 상황의 모델 입력이 다른지 확인
assert (
    result_unknown[0]["time_feature"]
    != result_zero[0]["time_feature"]
)

print("미확인:", result_unknown[0]["time_feature"])
print("실제 0초:", result_zero[0]["time_feature"])
print("통과: 두 상황이 구분됨")


# 5. 이번 문제와 다른 개념 제외
print("\n===== 테스트 4. 다른 개념 제외 =====")

result = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 86400.0, 604800.0],
    known=[False, False, True, True],
    names=names
)

# demo의 1일만 선택, loop의 7일은 제외
assert len(result) == 1
assert result[0]["concept_name"] == "demo"
assert result[0]["gap_seconds"] == 86400.0

print("통과: loop의 7일 간격이 제외됨")


# 6. 한 문제에 여러 개념이 있는 경우
print("\n===== 테스트 5. 다중 개념 =====")

result = select_query_gaps(
    concepts=[0, 0, 1, 1],
    seconds=[0.0, 0.0, 86400.0, 172800.0],
    known=[False, False, True, True],
    names=names
)

# demo와 loop의 시간 모두 선택
assert len(result) == 2
assert result[0]["concept_name"] == "demo"
assert result[1]["concept_name"] == "loop"
assert math.isclose(result[1]["gap_log"], math.log(3))

print("통과: 두 개념의 간격 모두 선택")


# 7. 과거 풀이가 없는 경우
print("\n===== 테스트 6. 빈 이력 상황 =====")

# 과거 이력 길이 0, 모든 mask가 False인 모의 입력
empty_history_input = {
    "lengths": 0,
    "mask": [False, False, False, False],
    "query_concepts": [0, 0, 1, 0],
    "query_gap_seconds": [0.0, 0.0, 0.0, 0.0],
    "query_gap_known": [False, False, False, False],
}

# 빈 이력 여부 확인
assert empty_history_input["lengths"] == 0
assert not any(empty_history_input["mask"])

# 시간 선택 함수 실행
result = select_query_gaps(
    concepts=empty_history_input["query_concepts"],
    seconds=empty_history_input["query_gap_seconds"],
    known=empty_history_input["query_gap_known"],
    names=names
)

# 빈 이력에서도 시간 미확인으로 처리
assert len(result) == 1
assert result[0]["gap_seconds"] is None
assert result[0]["gap_days"] is None
assert result[0]["time_feature"] == [0.0, 0]

print("통과: 이력 길이 0에서도 시간 미확인 상태로 처리")
