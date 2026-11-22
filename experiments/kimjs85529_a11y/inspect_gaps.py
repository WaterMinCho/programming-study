import sys
import math
import random
from pathlib import Path

# 1. 프로젝트 경로 설정
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# 팀원과 동일한 시드 값
SEED = 42


def get_torch():
    try:
        import torch
    except ModuleNotFoundError as exc:
        if exc.name != "torch":
            raise
        return None
    return torch


def get_device():
    torch = get_torch()
    if torch is None:
        return None
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")



def set_seed(seed=SEED):
    random.seed(seed)

    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        if exc.name != "numpy":
            raise
    else:
        np.random.seed(seed)

    torch = get_torch()

    if torch is not None:
        torch.manual_seed(seed)

        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        if torch.backends.mps.is_available():
            torch.mps.manual_seed(seed)



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

    # 3. 이번 문제에 해당하는 등록 개념 선택
    for j in range(len(concepts)):

        # 관련 없는 개념 제외
        if concepts[j] != 1:
            continue

        # PAD(0)와 UNK(1)는 최단 시간 후보에서 제외한다.
        # UNK는 서로 다른 미등록 개념의 시간이 합쳐질 수 있기 때문이다.
        if j in (0, 1):
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
            "time_feature": [float(gap_log), float(gap_known)]
        })

    # 등록 개념이 없으면 시간 정보를 생성할 수 없음
    if not selected:
        return []

    # 확인된 등록 개념의 시간만 후보에 포함
    confirmed = [
        item for item in selected
        if item["known"]
    ]

    if confirmed:
        # 가장 짧은 시간 하나 선택
        # 시간값이 같으면 concept_id가 작은 개념 선택
        shortest = min(
            confirmed,
            key=lambda item: (
                item["gap_seconds"],
                item["concept_id"]
            )
        )
        return [shortest]

    # 등록 개념은 있지만 시간이 모두 미확인일 때
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
        return [0.0, 0.0]

    return list(result[0]["time_feature"])


# 8. 모델용 배치 시간 특성 생성
# 개별 함수와 동일하게 PAD, UNK를 제외하고 확인된 최단 시간만 사용
def build_time_features_batch(concepts, seconds, known):
    torch = get_torch()
    if torch is None:
        raise RuntimeError("배치 텐서 연산에는 PyTorch가 필요합니다.")

    if not all(isinstance(x, torch.Tensor) for x in (concepts, seconds, known)):
        raise ValueError("세 입력은 모두 PyTorch 텐서여야 합니다.")
    if concepts.ndim != 2 or concepts.shape != seconds.shape or concepts.shape != known.shape:
        raise ValueError("세 입력은 같은 크기의 2차원 텐서여야 합니다.")
    if concepts.device != seconds.device or concepts.device != known.device:
        raise ValueError("세 입력은 같은 장치에 있어야 합니다.")

    seconds = seconds.to(dtype=torch.float32)
    known = known.to(dtype=torch.bool)
    batch_size, num_concepts = concepts.shape

    if batch_size == 0 or num_concepts <= 2:
        return seconds.new_zeros((batch_size, 2))

    # 현재 문제 개념이면서 시간이 확인된 등록 개념만 후보로 선택
    valid = (concepts == 1) & known
    valid[:, :2] = False

    invalid = valid & (~torch.isfinite(seconds) | (seconds < 0))
    if invalid.any().item():
        raise ValueError("유효하지 않은 경과 시간입니다.")

    masked_seconds = seconds.masked_fill(~valid, float("inf"))
    min_seconds = masked_seconds.min(dim=1).values
    gap_known = valid.any(dim=1)
    min_seconds = torch.where(gap_known, min_seconds, torch.zeros_like(min_seconds))
    gap_log = torch.log1p(min_seconds / 86400.0)

    return torch.stack([gap_log, gap_known.float()], dim=1)


# 9. 공통 v8 실제 데이터 확인
if __name__ == "__main__":
    set_seed()

    # 비공개 자료는 Git 저장소 밖에 유지
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

    from learning_server.input_example import load, batch

    rows, vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        SPLIT
    )

    if not rows:
        raise ValueError("해당 분할에 데이터가 없습니다.")

    # 10. 전체 데이터 중 무작위 4개를 배치로 변환
    HISTORY_LENGTH = 32
    BATCH_SIZE = 4

    selected_rows = random.sample(rows, min(BATCH_SIZE, len(rows)))

    example = batch(
        selected_rows,
        vocabulary,
        length=HISTORY_LENGTH
    )

    raw_inputs = example["inputs"]

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

        # 실제 학습자 기록은 출력하지 않음

    # PyTorch가 설치된 경우에는 같은 4건의 배치 연산 결과도 대조
    torch = get_torch()
    if torch is not None:
        device = get_device()
        batch_features = build_time_features_batch(
            torch.as_tensor(concepts, dtype=torch.float32, device=device),
            torch.as_tensor(seconds, dtype=torch.float32, device=device),
            torch.as_tensor(known, dtype=torch.bool, device=device)
        )
        expected = torch.tensor(
            [build_time_feature(concepts[i], seconds[i], known[i], names)
             for i in range(len(concepts))],
            dtype=torch.float32, device=device
        )
        torch.testing.assert_close(batch_features, expected, rtol=1e-5, atol=1e-6)

    print("===== 공통 입력 데이터 확인 (v8) =====")
    print("전체 데이터 수:", len(rows))
    print("무작위 선택 데이터 수:", len(concepts))
    print("무작위 선택 Seed:", SEED)
    print("PyTorch:", "설치됨" if torch is not None else "미설치")
    print("처리 방법:", "개별 처리 + 배치 결과 대조" if torch is not None else "개별 Python 처리")
    if torch is not None:
        print("사용 장치:", device)
        print("시간 특성 Shape:", tuple(batch_features.shape))
        print("시간 특성 dtype:", batch_features.dtype)
    else:
        print("시간 특성 Shape:", (len(concepts), 2))
        print("시간 특성 dtype: Python float")
    print("시간 확인 가능:", confirmed_count)
    print("시간 미확인:", unknown_count)
    print("모델 시간 입력 형식: [gap_log, gap_known]")
    print("시간 선택 및 숫자 변환 확인 완료")
