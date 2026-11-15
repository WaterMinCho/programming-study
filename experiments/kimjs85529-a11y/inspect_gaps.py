import sys
import math
from pathlib import Path

# 1. 프로젝트 경로 설정
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from learning_server.input_example import load, batch


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

        # PAD 제외
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

    return selected


# 7. 공통 합성 데이터 확인
if __name__ == "__main__":

    DATASET_PATH = PROJECT_ROOT.parent / "learning-demo-f5"

    TRACK = "python"
    SPLIT = "train"

    print("===== 공통 입력 데이터 확인 =====")
    print("데이터 경로:", DATASET_PATH)

    # 8. 데이터 불러오기
    rows, vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        SPLIT
    )

    # 9. 첫 4개 데이터를 배치로 변환
    example = batch(
        rows[:4],
        vocabulary,
        length=4
    )

    # 이번 정답(targets)은 사용하지 않음
    inputs = example["inputs"]

    # 10. 시간 관련 입력 추출
    concepts = inputs["query_concepts"]
    seconds = inputs["query_gap_seconds"]
    known = inputs["query_gap_known"]

    names = vocabulary["concepts"]

    # 11. 예제별 시간 선택
    for i in range(len(concepts)):

        result = select_query_gaps(
            concepts[i],
            seconds[i],
            known[i],
            names
        )

        # 12. 선택 결과 출력
        print(f"\n예제 {i + 1}")
        print("이번 문제의 개념:", concepts[i])
        print("개념별 시간(초):", seconds[i])
        print("시간 확인 여부:", known[i])

        for item in result:
            print("선택된 개념:", item["concept_name"])
            print("경과 시간:", item["gap_seconds"])
            print("로그 변환:", item["gap_log"])
            print("모델 입력 특성:", item["time_feature"])
