import sys
import math
import random
import numpy as np
import torch
from pathlib import Path

# 1. 프로젝트 경로 설정
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from learning_server.input_example import load, batch

# 팀원 input_check.py와 동일한 시드 설정
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


# 2. 이번 문제의 개념별 시간 선택 함수
def select_query_gaps(concepts, seconds, known, names):

    # 입력 벡터 길이 확인
    if not (
        len(concepts)
        == len(seconds)
        == len(known)
        == len(names)
    ):
        raise ValueError("입력 벡터 길이가 서로 다릅니다.")

    selected = []

    # 3. 이번 문제에 해당하는 개념 선택
    for j in range(len(concepts)):

        # 관련 없는 개념 제외
        if concepts[j] != 1:
            continue

        # PAD 제외 (기존과 같이 UNK는 유지)
        if j == 0:
            continue

        gap_known = bool(known[j])

        # 4. 시간을 아는 경우
        if gap_known:
            gap_seconds = float(seconds[j])

            # 시간값 유효성 확인
            if not math.isfinite(gap_seconds):
                raise ValueError("유효하지 않은 시간값입니다.")

            if gap_seconds < 0:
                raise ValueError("경과 시간은 음수일 수 없습니다.")

            # 초 -> 일 변환 및 로그 변환
            gap_days = gap_seconds / 86400.0
            gap_log = math.log1p(gap_days)

        # 5. 시간을 모르는 경우
        else:
            gap_seconds = None
            gap_days = None
            gap_log = 0.0

        # 6. 선택한 개념의 시간 정보 저장
        selected.append({
            "concept_id": j,
            "concept_name": names[j],
            "known": gap_known,
            "gap_seconds": gap_seconds,
            "gap_days": gap_days,
            "gap_log": gap_log,
            "time_feature": [gap_log, int(gap_known)]
        })

    # 여러 개념이면 확인 가능한 경과 시간 중 가장 짧은 하나 선택
    if not selected:
        return []

    confirmed = [item for item in selected if item["known"]]

    if confirmed:
        # 시간값이 같으면 더 작은 concept_id 선택
        shortest = min(
            confirmed,
            key=lambda item: (
                item["gap_seconds"],
                item["concept_id"]
            )
        )
        return [shortest]

    # 관련 개념은 있으나 시간이 모두 미확인일 때
    return [selected[0]]


# 7. 모델에서 사용할 숫자 특성 생성
def build_time_feature(concepts, seconds, known, names):

    result = select_query_gaps(
        concepts,
        seconds,
        known,
        names
    )

    if not result:
        return [0.0, 0]

    return list(result[0]["time_feature"])


# 8. 공통 v8 실제 데이터 확인
if __name__ == "__main__":

    DATASET_PATH = (
        PROJECT_ROOT.parent
        / "study-data"
        / "common-input-f8-20261118"
        / "recorded"
    )

    TRACK = "ai"
    SPLIT = "train"


    # 9. 데이터 불러오기
    if not (DATASET_PATH / "manifest.json").is_file():
        raise FileNotFoundError(
            f"데이터를 찾을 수 없습니다: {DATASET_PATH}"
        )

    rows, vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        SPLIT
    )

    if not rows:
        raise ValueError("해당 분할에 데이터가 없습니다.")

    # 10. 첫 4개 데이터를 배치로 변환
    HISTORY_LENGTH = 32
    BATCH_SIZE = 4  # 입력 확인용 배치 크기

    example = batch(
        rows[:BATCH_SIZE],
        vocabulary,
        length=HISTORY_LENGTH
    )

    # 팀원 input_check.py와 동일한 입력 변수명
    raw_inputs = example["inputs"]

    # 이번 정답(targets)은 시간 특성 검사에 사용하지 않음

    # 11. 시간 관련 입력 추출
    concepts = raw_inputs["query_concepts"]
    seconds = raw_inputs["query_gap_seconds"]
    known = raw_inputs["query_gap_known"]

    names = vocabulary["concepts"]

    # 12. 예제별 시간 선택
    confirmed_count = 0
    unknown_count = 0

    for i in range(len(concepts)):

        result = select_query_gaps(
            concepts[i],
            seconds[i],
            known[i],
            names
        )

        time_feature = build_time_feature(
            concepts[i],
            seconds[i],
            known[i],
            names
        )

        assert len(result) <= 1
        assert len(time_feature) == 2

        if time_feature[1] == 1:
            confirmed_count += 1
        else:
            unknown_count += 1

        # 실제 학습자 기록과 개별 입력값은 출력하지 않음

    print("===== 공통 입력 데이터 확인 (v8) =====")
    print("확인한 예제 수:", len(concepts))
    print("시간 확인 가능:", confirmed_count)
    print("시간 미확인:", unknown_count)
    print("모델 시간 입력 형식: [gap_log, gap_known]")
    print("시간 선택 및 숫자 변환 확인 완료")
