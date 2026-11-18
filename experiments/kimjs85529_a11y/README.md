# kimjs85529_a11y - LSTM + Time Gap 실험 기록

- **담당 모델:** LSTM + 풀이 간격(Time Gap)
- **담당 이슈:** https://github.com/WaterMinCho/programming-study/issues/121
- **이전 입력 확인 PR:** https://github.com/WaterMinCho/programming-study/pull/158
- **피드백 반영 PR:** https://github.com/WaterMinCho/programming-study/pull/319
- **작업 브랜치:** `model/kimjs85529_a11y_timegap_v8_fix`
- **기록 기준일:** 2026-11-18

이번 작업은 Time Gap **전처리와 테스트** 단계다. LSTM 학습, 모델 예측, 저장과 공식 채점은 수행하지 않았다. 문서는 `LEARNING_EXPERIMENT_TEMPLATE.md`의 항목에 맞췄다.

## 예측할 값과 모델을 고른 이유

이전 문제의 ID, 개념, 정오답을 이용하는 기본 LSTM에, **현재 문제의 개념별 마지막 풀이 후 경과 시간**을 추가하여 정답 확률을 예측하려고 한다.

현재는 시간 정보를 `[gap_log, gap_known]` 숫자 두 개로 만드는 기능만 구현했다. 시간 입력이 성능을 높이는지는 아직 검증하지 않았다.

## 직접 구현한 부분

| 파일 | 역할 |
|---|---|
| `experiments/kimjs85529_a11y/inspect_gaps.py` | `select_query_gaps()`와 `build_time_feature()` 및 v8 입력 확인 |
| `experiments/kimjs85529_a11y/test_gaps.py` | 공개 입력 테스트 1~5, 실제 자료 테스트 6, `<UNK>` 혼합 방지 테스트 7 |
| `experiments/kimjs85529_a11y/README.md` | 실행 조건, 실제 확인 결과, 피드백 기록 |

`select_query_gaps(concepts, seconds, known, names)`는 이번 문제에 포함된 개념 중 PAD(인덱스 0)와 UNK(인덱스 1)를 제외하고, **등록 개념의 확인된 시간 중 최단 간격 하나**를 선택한다.

UNK는 서로 다른 미등록 개념의 시간이 한 인덱스로 합쳐질 수 있어 정확한 개념 대응이 보장되지 않기 때문이다.

시간이 확인된 등록 개념이 없으면 시간 미확인 상태를 반환한다.

`build_time_feature()`는 이 함수를 내부에서 호출하여 `[gap_log, gap_known]`를 반환하며, 해당 등록 개념이 하나도 없으면 `[0.0, 0]`을 반환한다.

최단 간격 선택 부분은 다음과 같다.

    confirmed = [item for item in selected if item["known"]]

    if confirmed:
        shortest = min(
            confirmed,
            key=lambda item: (
                item["gap_seconds"],
                item["concept_id"]
            )
        )
        return [shortest]

확인된 초 단위 간격은 `math.log1p(gap_seconds / 86400.0)`로 변환한다.

| 상황 | 모델 입력 |
|---|---|
| 경과 시간 미확인 | `[0.0, 0]` |
| 실제 경과 시간 0초 | `[0.0, 1]` |
| 1일 경과 | `[0.6931471805599453, 1]` |
| 이번 문제의 등록 개념 없음 (`<UNK>`만 포함) | `[0.0, 0]` |
| `<UNK>` 120초 + `demo` 7일 | `demo`의 7일을 변환한 `[2.0794415416798357, 1]` |

팀원 `experiments/michae18/train.py`의 공통 `load()`와 `batch()` 사용 방식 및 이력 길이 32를 참고했다.

데이터 경로 설정은 기존 `pathlib.Path` 방식으로 유지했다.

팀원 `input_check.py`의 Seed 42에 맞췄으나, 전처리 계산 자체는 난수를 사용하지 않는다. NumPy와 PyTorch는 설치된 경우에만 시드를 설정하며, 공개 입력 테스트 실행에 필수는 아니다.

팀원의 `SmallLSTM`에 시간 특성을 연결하는 작업은 아직 수행하지 않았다.


## 실행 조건

| 항목 | 사용 값 |
|---|---|
| 운영체제 | Windows |
| Python | 3.13.5 |
| 프로젝트 경로 | `C:\programming-study` |
| 작업 브랜치 | `model/kimjs85529_a11y_timegap_v8_fix` |
| 실제 자료 경로 | `C:\study-data\common-input-f8-20261118\recorded` (Git 저장소 외부) |
| 입력 버전 | `features_version: 8` |
| 자료 종류 | Recorded Data (`synthetic: false`) |
| 데이터 형식 | `format: 1` |
| 트랙 및 분할 | `ai`, `train` |
| AI Train 기록 수 | 953 (기존 데이터 점검 결과) |
| 입력 확인용 배치 크기 | 4 |
| 과거 이력 길이 | 32 |
| 원본 manifest의 `history_limit` | 128 |
| 시드 | 42 |
| 본인 Fork | `kimjs85529-a11y/programming-study` |
| 작업 기준 커밋 SHA | `caa18441e69aea2dbc0a410b8f2746cadf4b326c` (이번 수정 커밋 이전) |
| 공통 원격 main SHA | `025dd44bf4a12fcac9783b3a7ef553cad02458a6` (2026-11-18 조회 시점) |
| `manifest.json` SHA-256 | `40141519FA79D1F7050D8F5C65B7B7E38E41D9C86B6A98F01063A70B2A1D5BE5` |
| `question_min_count` | 미확인 |
| 변형 행 제외 여부 | 미확인 |
| PyTorch 버전 | `2.14.1+cpu` |
| CPU | Intel Core i5-10210U @ 1.60GHz |
| GPU | Intel UHD Graphics |
| hidden_size, 임베딩 차원, 파라미터 수 | 모델 통합 및 학습 미실행 |

실제 기록과 개별 학습자 정보는 공개 PR에 포함하지 않는다.

공통 원격 `main`의 SHA는 PowerShell에서 조회한 시점의 값이며, 실험 당시 기준 커밋이나 현재 작업 브랜치의 기반 커밋을 의미하지는 않는다.

`manifest.json`의 `history_limit=128`은 자료에 기록된 설정이고, 이번 입력 확인에서 `batch(length=32)`로 사용한 과거 이력 길이는 32다. 두 값은 서로 다른 설정이다.

`question_min_count`와 변형 행 제외 여부는 제공된 `manifest.json`만으로 확인되지 않아 미확인으로 유지했다.

PyTorch는 설치되어 있지만 이번 전처리 테스트에서 신경망 학습을 수행하지 않았다.



## 다른 사람이 실행할 방법

Windows PowerShell에서 다음 명령어를 실행한다.

    cd C:\programming-study

    python --version

    python -m py_compile .\experiments\kimjs85529_a11y\inspect_gaps.py

    python -m py_compile .\experiments\kimjs85529_a11y\test_gaps.py

    python .\experiments\kimjs85529_a11y\inspect_gaps.py

    python .\experiments\kimjs85529_a11y\test_gaps.py

`inspect_gaps.py`는 실제 v8 recorded 자료가 있는 환경에서 실행한다.

`test_gaps.py`는 실제 자료가 없어도 테스트 1~5와 테스트 7을 실행할 수 있다.

실제 자료가 없으면 테스트 6은 `건너뜀(SKIP)`으로 표시된다. 자료가 존재하면 테스트 6에서 실제 AI Train의 빈 이력 레코드와 `<UNK>` 관련 집계를 진행한다.

데이터가 존재하는데 로딩이나 검증 과정에서 오류가 발생하면 테스트 실패로 처리한다.

NumPy와 PyTorch 없이도 시간 선택 함수를 불러오고 공개 테스트를 실행할 수 있도록 선택적 시드 설정을 사용한다.

모델 학습·저장·불러오기·예측·공식 채점은 아직 미실행이다.

## 결과와 오류 사례

### 1. v8 입력 확인 결과

`<UNK>` 제외 정책을 반영한 `inspect_gaps.py`를 Windows·Python 3.13.5 환경에서 실제 v8 recorded 데이터에 대해 재실행한 결과다.

    ===== 공통 입력 데이터 확인 (v8) =====
    확인한 예제 수: 4
    시간 확인 가능: 0
    시간 미확인: 4
    모델 시간 입력 형식: [gap_log, gap_known]
    시간 선택 및 숫자 변환 확인 완료

첫 4개 예제의 상태만 나타내며 AI Train 전체를 대표하지 않는다.

### 2. 수정 코드의 전체 테스트 실행 결과

`<UNK>` 제외 정책을 적용한 코드를 Windows·Python 3.13.5 환경에서 실제 v8 recorded 데이터를 사용해 실행했다.

Python 문법 검사 2개가 오류 없이 완료됐으며, 테스트 1~7이 모두 통과했다.

테스트 6은 SKIP되지 않고 실제 AI Train 데이터를 대상으로 실행됐다.

    ===== 테스트 1. 시간 확인 가능 =====
    통과: [0.6931471805599453, 1]

    ===== 테스트 2. 시간 미확인 =====
    통과: [0.0, 0]

    ===== 테스트 3. 실제 0초 =====
    실제 0초: [0.0, 1]

    ===== 테스트 4. 다른 개념 제외 및 개념 없음 =====
    통과: 관련 없는 개념 제외 및 개념 없음 [0.0, 0]

    ===== 테스트 5. 다중 개념의 최단 간격 =====
    통과: 확인된 가장 짧은 시간 하나만 선택

    ===== 테스트 6. 실제 자료의 빈 이력 =====
    통과: 실제 빈 이력의 lengths=0, mask=False 및 시간 입력 일치
    실제 AI Train 빈 이력 레코드 수: 3
    빈 이력 중 observed_history의 last_at 보유 레코드 수: 0
    빈 이력 중 이번 문제의 시간 확인 가능 레코드 수: 0
    <UNK> 포함 + 등록 개념 시간 확인 레코드 수: 0
    그중 <UNK>가 등록 개념보다 짧아 선택될 수 있는 레코드 수: 0

    ===== 테스트 7. UNK 시간 혼합 방지 =====
    통과: UNK 시간을 제외하고 등록 개념 중 최단 간격 선택
    통과: UNK만 있거나 등록 개념의 시간이 미확인이면 [0.0, 0]

    전체 7개 테스트 확인 완료

이번 Windows 실행에서는 테스트 1~7이 모두 통과했고, 실제 자료가 존재하여 테스트 6도 실행됐다.

실제 자료가 없는 다른 환경에서는 테스트 6만 SKIP되며, 이 경우 테스트 6을 통과한 것으로 간주하지 않는다.

### 3. 실제 v8 자료 집계 (2026-11-18 수정 후 재실행 결과)

`test_gaps.py`의 테스트 6은 실제 AI Train에서 모든 `sequence_history` 빈 이력 레코드를 찾고, `observed_history`에 `last_at`이 있는 경우와 현재 문제에서 시간 확인 가능한 경우를 구분한다.

또한 `<UNK>`가 현재 문제에 포함되고 다른 등록 개념의 시간이 확인된 행을 집계한다.

| 실제 자료 집계 항목 | 결과 |
|---|---|
| `sequence_history`가 빈 레코드 수 | 3개 |
| 그중 `observed_history`에 `last_at`이 있는 레코드 수 | 0개 |
| 빈 이력 중 이번 문제 시간 특성이 확인된 레코드 수 | 0개 |
| `<UNK>` 포함 + 등록 개념의 시간이 확인된 레코드 수 | 0개 |
| 그중 `<UNK>`가 등록 개념의 확인된 시간보다 짧은 레코드 수 | 0개 |

위 수치는 Windows 환경에서 `<UNK>` 제외 정책을 반영한 `test_gaps.py`를 실제 AI Train 자료로 재실행해 측정한 결과다.

빈 이력 레코드 3개 모두 `lengths=0`, `mask=False` 조건 및 변환 결과가 통과했다.

마지막 두 항목은 **기존 정책이었다면 `<UNK>`가 등록 개념의 간격을 대신할 수 있는 조건의 발생 건수**를 조사한 것이다.

현재 자료에서는 0건이었지만 다른 자료에서도 0건임을 보장하지는 않는다.

수정된 코드는 `<UNK>`를 최단 간격 후보에서 제외하여 이 위험을 방지한다.

`sequence_history`의 길이가 0이어도 `observed_history`에 시간이 있으면 시간 정보를 확인할 수 있다.

따라서 테스트 6은 `[0.0, 0]`을 정답으로 고정하지 않고, 등록 개념 중 선택 가능한 `query_gap_known`과 변환 함수의 결과가 일치하는지 확인한다.

이는 `<UNK>`를 후보에서 제외한 현재 정책을 반영한다.

### 4. 공식 모델 채점 결과

아직 모델을 학습하거나 공식 채점을 수행하지 않았으므로 GitHub 공식 양식의 채점표는 미측정이다.

| 항목 | 기록 |
|---|---|
| 채점 구간과 명령 | 미실행 |
| 구간의 행 수·오답 수·가명 수 | 미측정 |
| 모델 및 기준선 6개의 로그 손실·Brier·ROC-AUC·정확도 | 미측정 |
| 행 독립 표준오차, 가명 묶음 표준오차 | 미측정 |
| 로그 손실이 가장 낮은 기준선 | 미측정 |
| 모델에서 기준선 로그 손실을 뺀 값 | 미측정 |
| 경고 문구 | 채점 미실행 |

추후 공식 채점 표를 그대로 기록하고 경고 문구를 삭제하지 않는다.

실제 자료의 가명 수가 3개 미만이면 공개 표에는 `3개 미만`으로 표시한다.

## 입력 처리부터 학습·예측까지 코드 설명

공통 입력 생성 흐름은 다음과 같다.

    load()
        |
    batch(length=32)
        |
    example["inputs"]
        |
    build_time_feature()
        |
    select_query_gaps()
        |
    [gap_log, gap_known]

각 입력의 역할은 다음과 같다.

- `query_concepts`: 현재 문제에 포함된 개념
- `query_gap_seconds`: 개념별 마지막 풀이 후 경과 시간
- `query_gap_known`: 해당 시간의 확인 가능 여부
- `lengths`: 실제 과거 풀이 이력의 길이
- `mask`: 실제 풀이와 패딩을 구분하는 값
- `sequence_history`: 과거 풀이 순서 이력
- `observed_history`: 개념별 관측 시각 정보

`batch()`는 `sequence_history`를 기준으로 `lengths`와 `mask`를 만들고, `observed_history`를 기준으로 시간 관련 정보를 생성한다.

이 두 정보는 별도로 생성되므로 과거 풀이 이력이 없다는 사실만으로 시간도 미확인이라고 단정하지 않는다.

이번 문제의 정답인 `example["targets"]`는 시간 선택 함수에 입력하지 않는다.

### `<UNK>` 시간 혼합 방지 정책

`<UNK>`(인덱스 1)는 서로 다른 미등록 개념을 하나의 인덱스로 묶는다.

따라서 현재 문제와 관계없는 미등록 개념의 최근 풀이 시간이 현재 문제의 시간처럼 선택될 수 있다.

이를 방지하기 위해 Time Gap 전처리에서 PAD(0)와 UNK(1)를 최단 시간 선택 대상에서 제외하도록 수정했다.

공통 데이터와 공통 `batch()`는 수정하지 않았다.

예를 들어 다음과 같은 입력이 있다고 가정한다.

    names = ["<PAD>", "<UNK>", "demo", "loop"]

    concepts = [0, 1, 1, 1]

    seconds = [0.0, 120.0, 604800.0, 172800.0]

    known = [False, True, True, True]

각 개념의 시간 정보는 다음과 같다.

| 개념 | 경과 시간 | 처리 |
|---|---|---|
| `<UNK>` | 120초 | 후보 제외 |
| `demo` | 7일 | 후보 포함 |
| `loop` | 2일 | 후보 포함 |

최종적으로 등록 개념 중 시간이 가장 짧은 `loop`의 2일을 선택한다.

이는 최초 피드백에서 요청받은 **최단 시간 하나 선택 원칙을 유지하면서 미등록 개념의 시간 혼합을 방지하는 방식**이다.

테스트 7에서는 다음 상황을 직접 검증했다.

- `<UNK>`가 더 짧더라도 등록 개념 중 최단 시간 선택
- 등록 개념이 하나일 경우 해당 개념의 확인된 시간 선택
- `<UNK>`만 존재할 경우 `[0.0, 0]` 반환
- `<UNK>` 시간은 확인되지만 등록 개념 시간은 미확인인 경우 `[0.0, 0]` 반환

다만 이 방식에서는 미등록 개념 자체의 정확한 풀이 간격도 사용하지 못한다.

이는 확인되지 않은 시간을 다른 개념의 시간으로 잘못 사용하는 것을 방지하기 위한 보수적인 처리 정책이다.

미등록 개념의 정확한 시간을 사용하려면 공통 입력에서 원래 개념을 구별할 수 있는 정보가 필요하다.

## 질문을 받고 바꾼 부분

| 받은 피드백 | 수정 내용 | 확인 방법 |
|---|---|---|
| 빈 이력은 무조건 시간 미확인이라는 단정 | 테스트 6에서 `[0.0, 0]` 고정 비교 제거 | 실제 AI Train 빈 이력 3개 검증 통과 |
| 빈 이력의 `observed_history` 시각 확인 | 빈 이력 전체에서 `last_at` 기록 보유 건수 집계 | 재실행 결과 0개 |
| 변환 함수의 미확인·0초·개념 없음 직접 검증 | 테스트 2·3·4에 `build_time_feature()` 검증 추가 | 테스트 통과 |
| 실제 자료가 없을 때 실패 | 테스트 6만 SKIP하고 나머지 테스트 실행 | 조건부 SKIP 처리 구현 |
| PyTorch 없는 환경 지원 | NumPy·PyTorch 선택적 시드 설정, 공통 입력 모듈 지연 불러오기 | 공개 테스트 실행 구조 반영 |
| `<UNK>`에 관계없는 시간 섞임 | `<UNK>`를 후보에서 제외하고 등록 개념 중 최단 시간 선택 | 테스트 7 통과 |
| 실제 자료의 `<UNK>` 위험 조건 확인 | AI Train의 관련 조건을 만족하는 행 집계 | 0개 |
| 팀원 입력 설정과 통일 | 이력 32, 배치 4, Seed 42 유지 | 수정 후 v8 입력 검사 통과 |

- **관련 이슈:** https://github.com/WaterMinCho/programming-study/issues/121
- **관련 PR:** https://github.com/WaterMinCho/programming-study/pull/319
- **이번 추가 수정 커밋 SHA:** PR #319의 Commits 탭에서 확인

### 다음 단계

Windows의 실제 v8 recorded 데이터를 사용하여 `<UNK>` 제외 정책이 적용된 `inspect_gaps.py`와 `test_gaps.py`를 재실행했다.

Python 문법 검사와 공통 입력 확인이 정상적으로 완료됐으며, 테스트 1~7이 모두 통과했다.

현재 단계에서는 Time Gap 전처리와 검증을 완료했다.

다음 단계에서는 팀원의 최신 기본 LSTM과 동일한 데이터 및 학습 조건에서 Time Gap 입력을 연결하고 성능을 비교할 예정이다.

실제 데이터, 개별 학습 기록, 실제 자료로 학습한 가중치는 공개 PR에 포함하지 않는다.
