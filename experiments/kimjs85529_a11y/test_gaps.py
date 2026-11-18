import math
from pathlib import Path

from inspect_gaps import select_query_gaps, build_time_feature, set_seed

# 팀원 입력 검사와 동일한 시드 값
set_seed()


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

feature = build_time_feature(
    [0, 0, 1, 0],
    [0.0, 0.0, 86400.0, 0.0],
    [False, False, True, False],
    names
)

assert len(feature) == 2
assert math.isclose(feature[0], math.log(2))
assert feature[1] == 1

print("통과:", feature)


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

feature_unknown = build_time_feature(
    [0, 0, 1, 0],
    [0.0, 0.0, 0.0, 0.0],
    [False, False, False, False],
    names
)

assert feature_unknown == [0.0, 0]

print("통과:", feature_unknown)


# 4. 실제 0초와 시간 미확인 구분
print("\n===== 테스트 3. 실제 0초 =====")

result_zero = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 0.0, 0.0],
    known=[False, False, True, False],
    names=names
)

assert len(result_zero) == 1
assert result_zero[0]["gap_seconds"] == 0.0
assert result_zero[0]["gap_days"] == 0.0
assert result_zero[0]["time_feature"] == [0.0, 1]

feature_zero = build_time_feature(
    [0, 0, 1, 0],
    [0.0, 0.0, 0.0, 0.0],
    [False, False, True, False],
    names
)

assert feature_zero == [0.0, 1]
assert feature_unknown != feature_zero

print("실제 0초:", feature_zero)


# 5. 이번 문제와 다른 개념 제외 및 개념 없음
print("\n===== 테스트 4. 다른 개념 제외 및 개념 없음 =====")

result = select_query_gaps(
    concepts=[0, 0, 1, 0],
    seconds=[0.0, 0.0, 86400.0, 604800.0],
    known=[False, False, True, True],
    names=names
)

assert len(result) == 1
assert result[0]["concept_name"] == "demo"
assert result[0]["gap_seconds"] == 86400.0

# 개념이 없거나 PAD만 있는 경우
for no_concept in (
    [0, 0, 0, 0],
    [1, 0, 0, 0]
):
    assert select_query_gaps(
        no_concept,
        [0.0] * 4,
        [False] * 4,
        names
    ) == []

    assert build_time_feature(
        no_concept,
        [0.0] * 4,
        [False] * 4,
        names
    ) == [0.0, 0]

print("통과: 관련 없는 개념 제외 및 개념 없음 [0.0, 0]")


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

# 미확인 개념의 0초가 선택되지 않는지 확인
mixed = select_query_gaps(
    concepts=[0, 0, 1, 1],
    seconds=[0.0, 0.0, 0.0, 86400.0],
    known=[False, False, False, True],
    names=names
)

assert len(mixed) == 1
assert mixed[0]["concept_name"] == "loop"
assert mixed[0]["gap_seconds"] == 86400.0

assert build_time_feature(
    [0, 0, 1, 1],
    [0.0, 0.0, 0.0, 86400.0],
    [False, False, False, True],
    names
)[1] == 1

print("통과: 확인된 가장 짧은 시간 하나만 선택")


# 7. 실제 자료에서 과거 풀이 이력이 없는 레코드 검사
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
    print(
        "건너뜀(SKIP): 실제 v8 recorded 자료가 없어 "
        "테스트 6은 실행하지 않음"
    )

else:
    from learning_server.input_example import load, batch

    rows, vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        SPLIT
    )

    empty_rows = []
    empty_rows_with_last_at = 0

    # 이력 길이 0인 실제 레코드 전체 집계
    for row in rows:
        features = row.get("features", {})
        history = features.get("sequence_history")

        if history is None or len(history) != 0:
            continue

        empty_rows.append(row)

        observed = features.get("observed_history") or {}

        if isinstance(observed, dict) and any(
            isinstance(item, dict)
            and item.get("last_at") is not None
            and item.get("last_at") != ""
            for item in observed.values()
        ):
            empty_rows_with_last_at += 1

    assert empty_rows, (
        "과거 이력이 0개인 실제 기록을 찾지 못했습니다."
    )

    # 모든 빈 이력 레코드 검사
    empty_rows_known = 0

    for row in empty_rows:
        example = batch(
            [row],
            vocabulary,
            length=32
        )

        raw_inputs = example["inputs"]

        assert int(raw_inputs["lengths"][0]) == 0

        assert not any(
            bool(value)
            for value in raw_inputs["mask"][0]
        )

        concepts = raw_inputs["query_concepts"][0]
        seconds = raw_inputs["query_gap_seconds"][0]
        known = raw_inputs["query_gap_known"][0]
        names_real = vocabulary["concepts"]

        result = select_query_gaps(
            concepts,
            seconds,
            known,
            names_real
        )

        feature = build_time_feature(
            concepts,
            seconds,
            known,
            names_real
        )

        assert len(result) <= 1
        assert len(feature) == 2

        # PAD(0)와 UNK(1)를 제외한 등록 개념만 검사
        expected_known = int(any(
            concepts[j] == 1 and bool(known[j])
            for j in range(2, len(names_real))
        ))

        assert feature[1] == expected_known

        if expected_known:
            expected_seconds = min(
                float(seconds[j])
                for j in range(2, len(names_real))
                if concepts[j] == 1 and bool(known[j])
            )

            assert math.isclose(
                feature[0],
                math.log1p(expected_seconds / 86400.0)
            )

            empty_rows_known += 1

        else:
            assert feature == [0.0, 0]

    # UNK와 등록 개념이 함께 있는 자료 집계
    unk_and_registered_known = 0
    unk_wins_shortest = 0

    BATCH_SIZE = 32

    for start in range(0, len(rows), BATCH_SIZE):
        example = batch(
            rows[start:start + BATCH_SIZE],
            vocabulary,
            length=32
        )

        inputs = example["inputs"]

        for i in range(len(inputs["query_concepts"])):
            concepts = inputs["query_concepts"][i]
            seconds = inputs["query_gap_seconds"][i]
            known = inputs["query_gap_known"][i]

            if len(concepts) < 3 or concepts[1] != 1:
                continue

            registered = [
                j
                for j in range(2, len(concepts))
                if concepts[j] == 1 and bool(known[j])
            ]

            if not registered:
                continue

            unk_and_registered_known += 1

            # 이전 정책이라면 UNK가 선택될 수 있는 사례
            if bool(known[1]) and float(seconds[1]) < min(
                float(seconds[j])
                for j in registered
            ):
                unk_wins_shortest += 1

    print(
        "통과: 실제 빈 이력의 lengths=0, mask=False "
        "및 시간 입력 일치"
    )

    print(
        "실제 AI Train 빈 이력 레코드 수:",
        len(empty_rows)
    )

    print(
        "빈 이력 중 observed_history의 "
        "last_at 보유 레코드 수:",
        empty_rows_with_last_at
    )

    print(
        "빈 이력 중 이번 문제의 "
        "시간 확인 가능 레코드 수:",
        empty_rows_known
    )

    print(
        "<UNK> 포함 + 등록 개념 "
        "시간 확인 레코드 수:",
        unk_and_registered_known
    )

    print(
        "그중 <UNK>가 등록 개념보다 짧아 "
        "선택될 수 있는 레코드 수:",
        unk_wins_shortest
    )


# 8. UNK를 제외하고 등록 개념의 최단 시간 선택
print("\n===== 테스트 7. UNK 시간 혼합 방지 =====")

unk_names = ["<PAD>", "<UNK>", "demo", "loop"]

unk_concepts = [0, 1, 1, 1]
unk_seconds = [0.0, 120.0, 604800.0, 172800.0]
unk_known = [False, True, True, True]

unk_result = select_query_gaps(
    unk_concepts,
    unk_seconds,
    unk_known,
    unk_names
)

unk_feature = build_time_feature(
    unk_concepts,
    unk_seconds,
    unk_known,
    unk_names
)

# UNK 120초를 제외하고 loop 2일 선택
assert len(unk_result) == 1
assert unk_result[0]["concept_id"] == 3
assert unk_result[0]["concept_name"] == "loop"
assert unk_result[0]["gap_seconds"] == 172800.0

assert unk_feature[1] == 1

assert math.isclose(
    unk_feature[0],
    math.log1p(172800.0 / 86400.0)
)

# 등록 개념이 하나일 경우
# UNK보다 시간이 길어도 등록 개념의 시간 선택
assert build_time_feature(
    [0, 1, 1, 0],
    [0.0, 120.0, 604800.0, 0.0],
    [False, True, True, False],
    unk_names
) == [math.log1p(7.0), 1]

# UNK만 포함된 경우
only_unk = select_query_gaps(
    [0, 1, 0, 0],
    [0.0, 120.0, 0.0, 0.0],
    [False, True, False, False],
    unk_names
)

assert only_unk == []

assert build_time_feature(
    [0, 1, 0, 0],
    [0.0, 120.0, 0.0, 0.0],
    [False, True, False, False],
    unk_names
) == [0.0, 0]

# UNK의 시간은 확인되지만
# 등록 개념의 시간이 미확인인 경우
assert build_time_feature(
    [0, 1, 1, 0],
    [0.0, 120.0, 0.0, 0.0],
    [False, True, False, False],
    unk_names
) == [0.0, 0]

print(
    "통과: UNK 시간을 제외하고 "
    "등록 개념 중 최단 간격 선택"
)

print(
    "통과: UNK만 있거나 등록 개념의 "
    "시간이 미확인이면 [0.0, 0]"
)

print("\n전체 7개 테스트 확인 완료 ")
