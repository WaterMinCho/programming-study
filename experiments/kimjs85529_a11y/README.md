# kimjs85529_a11y - LSTM + Time Gap 실험 기록

- **담당 모델:** LSTM + 풀이 간격(Time Gap)
- **담당 이슈:** https://github.com/WaterMinCho/programming-study/issues/121
- **기본 LSTM 참고 PR:** https://github.com/WaterMinCho/programming-study/pull/226
- **이전 입력 확인 PR:** https://github.com/WaterMinCho/programming-study/pull/158
- **피드백 반영 PR:** https://github.com/WaterMinCho/programming-study/pull/319
- **작업 브랜치:** `model/kimjs85529_a11y_timegap_lstm`
- **최종 확인일:** 2026-11-22

## 예측할 값과 모델을 고른 이유

기본 LSTM이 사용하는 과거 문제 ID, 개념, 정오답 및 현재 문제 정보에 풀이 간격(Time Gap)을 추가하여 다음 문제의 정답 확률을 예측하도록 모델을 구현했다.

목적은 동일한 기본 LSTM 구조에서 시간 정보 추가 여부에 따른 예측 성능 차이를 비교하는 것이다.

시간 특성은 `[gap_log, gap_known]`으로 구성한다.

- `gap_log`: 마지막 풀이 후 경과 시간(초)을 일 단위로 변환하고 `log1p()`를 적용한 값
- `gap_known`: 시간 확인 여부를 나타내는 0.0 또는 1.0

시간 미확인 상태 `[0.0, 0.0]`과 실제 0초 간격 `[0.0, 1.0]`을 구분한다.

현재는 모델 구현과 기능 검증까지 완료했으며, 실제 데이터 기반 학습 및 성능 비교는 진행하지 않았다.

## 직접 구현한 부분

| 파일 | 역할 |
|---|---|
| `inspect_gaps.py` | Time Gap 개별 전처리, PyTorch 배치 연산, 장치 및 시드 설정 |
| `test_gaps.py` | 시간 전처리 테스트 10개 및 실제 데이터 검증 |
| `model.py` | 기본 LSTM 상속, 시간 특성 연결 및 공통 가중치 복사 |
| `test_data_model.py` | 기본 모델 비교, 시간 특성 반영, 역전파, 실제 데이터 순전파, 저장·복원 검증 |
| `README.md` | 실행 환경, 검증 방법, 실행 결과 및 피드백 기록 |

### 1. 기본 LSTM과의 관계

팀원 `michae18`의 `SmallLSTM` 모델을 상속하여 `TimeGapLSTM`을 구현했다.

- 기본 모델 경로: `experiments/michae18/model.py`
- 기본 모델 원본 전체 커밋 SHA: `1b95b0c6a45627ffde19afb7e60ff564b94c7254`
- 기본 LSTM의 Embedding, LSTM 및 `encode_history()` 구조 유지
- 최종 Linear 계층에 시간 특성 `[gap_log, gap_known]` 두 개 추가

`copy_baseline_weights()`를 이용하여 기본 LSTM의 공통 가중치를 복사하고 시간 특성 가중치를 0으로 초기화했다.

동일한 입력에서 기본 LSTM과 TimeGapLSTM의 초기 Logit이 일치하는지 비교하여 기존 모델 구조가 유지되는지 확인했다.

기본 LSTM의 SHA는 다음 명령으로 확인했다.

```powershell
git log -1 --format=%H -- experiments/michae18/model.py
```

확인 결과:

```text
1b95b0c6a45627ffde19afb7e60ff564b94c7254
```

### 2. 풀이 간격 선택 정책 및 UNK 제외 이유

현재 문제에 포함된 개념 중 시간 정보가 확인된 **등록 개념의 최단 풀이 간격 하나**를 Time Gap 특성으로 사용한다.

시간 선택 과정에서 PAD(개념 ID 0)와 UNK(개념 ID 1)는 제외한다.

PAD는 실제 개념이 아닌 패딩이므로 풀이 간격 계산에 사용할 수 없다.

UNK는 Vocabulary에 등록되지 않은 여러 개념이 하나의 ID로 통합되어 표현되는 값이다. 따라서 UNK에 기록된 마지막 풀이 시각이 현재 문제의 특정 개념을 마지막으로 풀이한 시각이라고 보장할 수 없다.

예를 들어 서로 다른 미등록 개념 A와 B가 모두 UNK로 표현된다면, A의 풀이 기록이 B의 마지막 풀이 시각으로 잘못 해석될 가능성이 있다.

이러한 부정확한 시간 정보가 모델에 입력되는 것을 방지하기 위해, 정확한 개념 대응이 가능한 등록 개념의 시간 정보만 사용하도록 구현했다.

다만 UNK를 제외하면 다음과 같은 한계가 발생한다.

- 현재 문제에 UNK만 포함되어 있고 UNK의 시간 정보가 확인되더라도, 등록 개념의 확인 가능한 시간이 없다면 `[gap_log, gap_known] = [0.0, 0.0]`을 반환한다.
- 이 경우 원본 시간 정보가 실제로 없는 기록과 UNK 제외 정책으로 시간 정보를 사용하지 못한 기록이 모델에서 동일한 시간 입력으로 표현된다.
- 실제 v8 Recorded 데이터의 AI 트랙을 확인한 결과, Train 953건에서는 UNK가 포함된 기록이 0건이었으며, Validation 299건에서는 12건, Test 260건에서는 39건으로 확인되었다. 이 중 UNK의 시간은 확인되었지만 등록 개념의 시간은 확인되지 않아 `[gap_log, gap_known] = [0.0, 0.0]`으로 처리된 기록은 Validation 6건, Test 6건이었다. 따라서 Train의 시간 미확인 196건은 UNK 제외 정책의 영향을 받지 않았으며, Validation과 Test에서는 일부 시간 정보가 제외되었음을 확인했다.

UNK 제외 정책은 `test_gaps.py`의 테스트 7에서 인공 입력을 사용하여 확인했다.

UNK의 간격이 등록 개념보다 짧더라도 UNK를 제외하고, 등록 개념 중 확인된 최단 풀이 간격을 선택하는지 검증했다.

### 3. 시간 특성 생성

선택된 풀이 간격은 다음 식으로 변환한다.

```python
gap_days = gap_seconds / 86400.0
gap_log = math.log1p(gap_days)
```

시간이 확인되지 않으면 `[0.0, 0.0]`을 사용한다.

실제 0초 간격이 확인되면 `[0.0, 1.0]`을 사용한다.

개별 전처리에서는 두 값을 Python float로 반환하며, PyTorch 배치 전처리에서는 `(batch_size, 2)` 형태의 `torch.float32` 텐서를 생성한다.

## 실행 조건

| 항목 | 실제 사용한 값 |
|---|---|
| 본인 Fork | `kimjs85529-a11y/programming-study` |
| 작업 브랜치 | `model/kimjs85529_a11y_timegap_lstm` |
| 최초 구현 작업 전체 커밋 SHA | `187d7ba4a39fbb602a023bcb49623f656f97df1d` |
| 작업 기준 공통 main 전체 SHA | `6e6327b964778fddfdae5fd19c61bed51d67e742` |
| 기본 LSTM 원본 전체 커밋 SHA | `1b95b0c6a45627ffde19afb7e60ff564b94c7254` |
| `manifest.json` SHA-256 | 비공개 관리, 현재 README에 미기재 |
| 데이터 버전 | `features_version: 8` |
| 데이터 묶음 | `common-input-f8-20261118` |
| 자료 종류 | 실제 수집 자료(Recorded) |
| `question_min_count` | 미확인 |
| 변형 행 제외 여부 | 미확인 |
| 트랙 / 분할 | `ai` / `train` |
| 실제 데이터 수 | 953건 |
| 입력 확인 표본 | 무작위 4건, Seed 42 |
| 실제 데이터 검증 배치 크기 | 32 |
| 과거 이력 길이 | 32 |
| 모델 초기화 Seed | 42 |
| Embedding 차원 | 16 |
| LSTM Hidden 차원 | 16 |
| 문제 Vocabulary 크기 | 146 |
| 개념 Vocabulary 크기 | 235 |
| 기본 LSTM 파라미터 | 19,884개 |
| TimeGapLSTM 파라미터 | 19,886개 |
| 추가된 파라미터 | 2개 |
| Python | 3.13.5 |
| PyTorch | 2.14.1+cpu |
| 운영체제 | Windows |
| 검증 장치 | CPU |

실제 데이터 경로:

```text
C:\study-data\common-input-f8-20261118\recorded
```

실제 데이터는 Git 저장소 외부에서 관리하며 공개 PR에는 포함하지 않는다.

### 커밋 SHA 확인

작업 당시 다음 명령으로 커밋을 확인했다.

```powershell
git log -1 --format=%H -- experiments/michae18/model.py
git rev-parse HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
```

확인 결과:

```text
기본 LSTM: 1b95b0c6a45627ffde19afb7e60ff564b94c7254
작업 HEAD: 187d7ba4a39fbb602a023bcb49623f656f97df1d
origin/main: 6e6327b964778fddfdae5fd19c61bed51d67e742
merge-base: 6e6327b964778fddfdae5fd19c61bed51d67e742
```

README 수정 후 새 커밋을 생성하면 HEAD의 SHA는 변경되므로, 위 작업 SHA는 최초 모델 구현 커밋으로 기록한다.

### 모델 파라미터 수 확인

실제 AI Train 데이터의 Vocabulary를 이용하여 두 모델의 파라미터 수를 비교했다.

```python
rows, vocabulary = load(
    str(DATASET_PATH),
    TRACK,
    SPLIT,
)

num_questions = len(vocabulary["questions"])
num_concepts = len(vocabulary["concepts"])

baseline = SmallLSTM(
    num_questions=num_questions,
    num_concepts=num_concepts,
)

timegap = TimeGapLSTM(
    num_questions=num_questions,
    num_concepts=num_concepts,
)

baseline_params = sum(
    p.numel() for p in baseline.parameters()
)

timegap_params = sum(
    p.numel() for p in timegap.parameters()
)
```

실제 실행 결과:

```text
Track: ai
Split: train
전체 데이터: 953
문제 Vocabulary: 146
개념 Vocabulary: 235
기본 LSTM 파라미터: 19884
TimeGapLSTM 파라미터: 19886
파라미터 증가량: 2
```

동일한 Vocabulary와 기본 모델 설정에서 시간 특성 두 개를 추가한 결과, 파라미터 수가 정확히 2개 증가했다.

참고로 인공 테스트 설정(문제 10개, 개념 4개)에서는 기본 LSTM 2,693개, TimeGapLSTM 2,695개로 확인했다.

## 다른 사람이 실행할 방법

저장소 루트 `C:\programming-study`에서 실행한다.

실제 데이터 검증을 위해서는 공통 v8 Recorded 데이터와 프로젝트 의존성이 준비되어 있어야 한다.

### 1. 실행 환경 확인

```powershell
cd C:\programming-study

python --version
python -c "import torch; print(torch.__version__)"
```

### 2. 시간 전처리 확인

```powershell
python -m experiments.kimjs85529_a11y.inspect_gaps
```

실제 AI Train 전체 데이터 953건 중 Seed 42로 무작위 4건을 선택하여 시간 특성 생성 결과를 확인한다.

이 실행 예제에서는 배치 크기 4를 사용하며, 실제 데이터 전체 검증에서는 배치 크기 32를 사용한다.

### 3. 시간 전처리 테스트

```powershell
python -m experiments.kimjs85529_a11y.test_gaps
```

시간 미확인, 실제 0초, 최단 간격 선택, UNK 제외, 자료형, 개별·배치 연산 및 대량 입력 처리 등을 검증한다.

### 4. 모델 기능 테스트

```powershell
python -m experiments.kimjs85529_a11y.test_data_model
```

또는 저장소 루트에서 직접 실행할 수 있다.

```powershell
python experiments\kimjs85529_a11y\test_data_model.py
```

기본 LSTM과 초기 출력 비교, 시간 특성 반영, 빈 이력 및 패딩, 역전파, 실제 데이터 순전파, 모델 저장·복원 등을 확인한다.

### 5. 실제 학습 및 평가

현재 실제 데이터 기반 학습, 공식 채점, 예측 성능 비교는 실행하지 않았다. 검증 예측을 계산한 뒤에는 [공통 검증 채점기](../../docs/LEARNING_STARTER.md#공통-검증-채점기)로 점수를 확인할 수 있다.

인공 입력에 대한 SGD 1회 가중치 갱신은 학습 가능성을 확인하기 위한 기능 테스트이며, 실제 데이터 학습 결과가 아니다.

## 결과와 오류 사례

### 1. 시간 전처리 테스트 재검증

2026-11-22에 PR 최초 구현 커밋 `187d7ba4a39fbb602a023bcb49623f656f97df1d` 기준으로 전처리 코드를 다시 검증했다.

재검증에는 `model/kimjs85529_a11y_timegap_lstm` 브랜치의 위 커밋을 사용했다.

브랜치와 커밋을 확인하고 전처리 파일 두 개의 변경 내역을 비교했다.

```powershell
cd C:\programming-study

git branch --show-current
git rev-parse HEAD

git diff 187d7ba4a39fbb602a023bcb49623f656f97df1d -- experiments/kimjs85529_a11y/inspect_gaps.py experiments/kimjs85529_a11y/test_gaps.py
```

`git diff`에서 아무 내용도 출력되지 않았으며, `inspect_gaps.py`와 `test_gaps.py`가 해당 커밋 대비 변경되지 않았음을 확인했다.

이후 다음 명령으로 시간 전처리 테스트를 재실행했다.

```powershell
python -m experiments.kimjs85529_a11y.test_gaps
```

실제 실행 결과:

```text
===== 테스트 1. 시간 확인 가능 =====
통과: [0.6931471805599453, 1.0]

===== 테스트 2. 시간 미확인 =====
통과: [0.0, 0.0]

===== 테스트 3. 실제 0초 =====
실제 0초: [0.0, 1.0]

===== 테스트 4. 다른 개념 제외 및 개념 없음 =====
통과: 관련 없는 개념 제외 및 개념 없음 [0.0, 0.0]

===== 테스트 5. 다중 개념의 최단 간격 =====
통과: 확인된 가장 짧은 시간 하나만 선택

===== 테스트 6. 실제 자료의 빈 이력 =====
실제 AI Train 전체 자료 수: 953
시간 확인 가능: 757
시간 미확인: 196
개별·배치 결과 전체 비교 통과
통과: 실제 빈 이력의 lengths=0, mask=False 및 시간 입력 일치
실제 AI Train 빈 이력 레코드 수: 3
빈 이력 중 observed_history의 last_at 보유 레코드 수: 0
빈 이력 중 이번 문제의 시간 확인 가능 레코드 수: 0
<UNK> 포함 + 등록 개념 시간 확인 레코드 수: 0
그중 <UNK>가 등록 개념보다 짧아 선택될 수 있는 레코드 수: 0

===== 테스트 7. UNK 시간 혼합 방지 =====
통과: UNK 시간을 제외하고 등록 개념 중 최단 간격 선택
통과: UNK만 있거나 등록 개념의 시간이 미확인이면 [0.0, 0.0]

===== 테스트 8. 시간 특성 자료형 =====
통과: 두 값 모두 Python float

===== 테스트 9. 배치 시간 특성 =====
통과: 7건 개별·배치 결과 일치

===== 테스트 10. 대량 배치 및 예외 처리 =====
통과: 10,000건, 빈 배치 및 잘못된 입력 검사

전체 테스트 확인 완료 (PyTorch 미설치 시 테스트 9~10 SKIP)
```

테스트 1~10이 모두 통과했으며, 실제 AI Train 데이터 953건의 개별·배치 전처리 결과가 일치했다.

- 시간 확인 가능: 757건
- 시간 미확인: 196건
- 실제 빈 이력: 3건
- 대량 배치 테스트: 10,000건 처리 통과

마지막 출력 한 줄:

```text
전체 테스트 확인 완료 (PyTorch 미설치 시 테스트 9~10 SKIP)
```

괄호 안의 SKIP은 PyTorch가 설치되지 않은 경우의 안내 문구이다. 이번 실행에서는 PyTorch가 설치되어 있었으므로 테스트 9와 테스트 10도 정상 실행되어 통과했다.

따라서 기존 README에 기록했던 시간 전처리 테스트 10개 통과 및 757건·196건 집계는 이번 PR 최초 구현 커밋의 코드로 재검증된 결과임을 확인했다.

다만 이 검증은 공통 입력으로 제공된 `query_gap_seconds`의 시간 선택 및 전처리 결과를 확인한 것이며, 원본 풀이 타임스탬프에서 경과 시간이 정확하게 생성됐는지를 독립적으로 검증한 결과는 아니다.

### 2. 시간 전처리 입력 확인

`inspect_gaps.py`에서 Seed 42로 무작위 4건을 선택한 실행 결과는 다음과 같다.

```text
===== 공통 입력 데이터 확인 (v8) =====
전체 데이터 수: 953
무작위 선택 데이터 수: 4
무작위 선택 Seed: 42
PyTorch: 설치됨
처리 방법: 개별 처리 + 배치 결과 대조
사용 장치: cpu
시간 특성 Shape: (4, 2)
시간 특성 dtype: torch.float32
시간 확인 가능: 3
시간 미확인: 1
모델 시간 입력 형식: [gap_log, gap_known]
시간 선택 및 숫자 변환 확인 완료
```

이 결과는 무작위 4건에 대한 확인이며 전체 953건의 집계와 구분한다.

### 3. 모델 기능 검증

`test_data_model.py`를 Windows CPU 환경에서 실행한 결과는 다음과 같다.

```text
사용 장치: cpu
통과: 기본 LSTM과 초기 출력 일치
통과: 출력 형상·확률·빈 이력·패딩
통과: 시간 미확인/0초 구분
통과: gap_log의 출력 반영
통과: 역전파 및 가중치 갱신
통과: 실제 데이터 전체 순전파 953 건
통과: 모델 저장·복원 후 출력 일치

기능 검증 완료
실제 학습 및 성능 평가는 미실행
```

검증 항목은 다음과 같다.

| 검증 항목 | 확인 내용 | 결과 |
|---|---|---|
| 기본 LSTM 비교 | 공통 가중치를 복사하고 초기 Logit 비교 | 통과 |
| 출력 형상 | 인공 입력 2건의 Logit Shape 확인 | 통과 |
| 확률 범위 | sigmoid 결과가 0~1 범위인지 확인 | 통과 |
| 빈 이력 | 이력 길이 0에서 상태 벡터 처리 확인 | 통과 |
| 패딩 | 패딩 영역 변경 전후 출력 비교 | 통과 |
| 시간 미확인/0초 | 시간 확인 특성 변경에 따른 Logit 차이 비교 | 통과 |
| gap_log 반영 | 0일과 1일 입력의 Logit 차이 비교 | 통과 |
| 역전파 | 시간 가중치 및 LSTM 기울기 생성 확인 | 통과 |
| 가중치 갱신 | SGD 1회 갱신 후 가중치 변경 확인 | 통과 |
| 실제 데이터 | AI Train 953건 전체 순전파 | 통과 |
| 저장·복원 | 복원 전후 Logit 일치 확인 | 통과 |

시간 미확인 `[0.0, 0.0]`과 실제 0초 `[0.0, 1.0]`을 비교할 때 시간 가중치를 1로 설정하면 Logit 차이가 1이 되는지 확인했다.

또한 0일과 1일의 `gap_log` 차이가 `log(2)`에 해당하는지 확인했다.

이는 모델에 시간 특성이 정상적으로 연결됐다는 기능 검증이며, 실제 예측 정확도의 향상을 의미하지 않는다.

### 4. 모델 저장·복원 검증

`torch.save(model.state_dict(), path)`를 사용해 모델 가중치를 임시 파일로 저장했다.

새로운 TimeGapLSTM 객체를 생성하고 `torch.load(..., weights_only=True)`와 `load_state_dict()`로 복원했다.

동일한 입력에 대해 복원 전후 Logit이 일치하는지 확인했다.

임시 파일은 `TemporaryDirectory()`를 사용하여 `with` 블록 종료 시 자동으로 삭제했다.

현재는 같은 Python 프로세스에서 초기 모델의 가중치 저장·복원을 검증했다. 학습된 모델을 별도 프로세스에서 복원하는 과정은 검증하지 않았다.

### 5. 현재 검증의 한계

현재까지 확인한 내용은 다음과 같다.

- 시간 선택 및 숫자 변환
- 개별·배치 전처리 결과의 일치
- UNK 제외 정책에 대한 인공 입력 검증
- 기본 LSTM과 초기 출력 비교
- 시간 특성의 Logit 반영
- 역전파 및 가중치 갱신 가능 여부
- 실제 데이터 953건 순전파
- 모델 가중치 저장·복원

아직 확인하지 않은 내용은 다음과 같다.

- 원본 타임스탬프와 `query_gap_seconds`의 독립적인 대조
- UNK 제외 정책이 실제 모델 예측 성능에 미치는 영향
- 실제 데이터 기반 모델 학습
- 기본 LSTM과 TimeGapLSTM의 예측 성능 비교
- 별도 Python 프로세스에서 학습된 모델 복원
- 공식 채점 결과

따라서 현재 결과만으로 TimeGapLSTM의 성능이 기본 LSTM보다 높다고 판단할 수 없다.

## 입력 처리부터 학습·예측까지 내 코드 설명

### 1. 공통 데이터 입력

`learning_server.input_example`의 `load()`와 `batch()`를 사용하여 실제 v8 AI Train 데이터를 읽는다.

모델 입력에는 과거 문제 ID, 개념, 정오답, 현재 문제 정보 및 시간 특성을 사용한다.

현재 문제의 정답은 모델 입력과 분리한다.

### 2. 시간 특성 전처리

현재 문제의 `query_concepts`, `query_gap_seconds`, `query_gap_known`을 이용하여 등록 개념의 확인된 최단 풀이 간격을 계산한다.

선택된 시간은 `[gap_log, gap_known]`으로 변환한다.

### 3. 모델 입력 생성

`make_model_inputs()`에서 기존 LSTM 입력과 시간 특성을 PyTorch 텐서로 변환한다.

### 4. TimeGapLSTM 순전파

기본 LSTM의 이력 인코더를 유지하고, 최종 Linear 계층에 시간 특성 두 개를 추가한다.

모델은 Logit을 반환하며, 정답 확률이 필요한 경우 sigmoid를 적용한다.

### 5. 기본 모델과 비교

`copy_baseline_weights()`로 공통 가중치를 복사하고 추가 시간 가중치를 0으로 초기화하여 초기 Logit이 일치하는지 확인한다.

### 6. 역전파 및 가중치 갱신

인공 입력에 대해 `BCEWithLogitsLoss()`를 계산하고 역전파를 수행한다.

SGD 1회 갱신 전후 시간 특성 가중치가 변경되는지 확인한다.

이는 학습 가능성을 확인하는 테스트이며 실제 데이터 학습은 아니다.

### 7. 실제 데이터 순전파

실제 AI Train 데이터 953건을 배치 크기 32로 나누어 순전파를 수행한다.

출력 형상과 유한성을 검사하고 전체 기록 수가 일치하는지 확인한다.

### 8. 모델 저장·복원

`state_dict`를 임시 파일에 저장하고 새 모델 객체에 복원한 뒤 동일한 입력의 Logit이 일치하는지 확인한다.

### 9. 향후 작업

실제 데이터로 기본 LSTM과 TimeGapLSTM을 동일한 조건에서 학습시키고 성능을 비교할 예정이다.

## 질문을 받고 바꾼 부분

| 피드백 및 수정 사항 | 반영 내용 | 확인 결과 |
|---|---|---|
| 기본 모델 기준 불명확 | `SmallLSTM` 원본 커밋 SHA 기록 | 실제 Git 명령으로 확인 |
| 실행 조건 미기재 | 작업 기준 main SHA, Python·PyTorch 버전 기록 | 실제 실행 환경 확인 |
| 모델 파라미터 수 재확인 | AI Train Vocabulary 기준 19,884 / 19,886개 기록 | 파라미터 증가량 2개 확인 |
| 이전 테스트 결과의 재현성 | 커밋 `187d7ba`와 파일 차이 확인 후 테스트 재실행 | 테스트 1~10 통과 |
| 시간 미확인과 실제 0초 구분 | `[gap_log, gap_known]` 두 값 사용 | 전처리 및 모델 검증 통과 |
| 여러 개념의 시간 선택 | 등록 개념의 확인된 최단 간격 사용 | 전처리 테스트 통과 |
| UNK 시간 혼합 문제 | PAD·UNK 제외 정책 적용 | 테스트 7 통과 |
| UNK 제외에 따른 모델 입력 한계 | UNK만 시간이 확인된 경우에도 `[0.0, 0.0]`이 될 수 있음을 명시 | Train 0건, Validation 6건, Test 6건 확인 |
| 시간 특성 자료형 | Python float와 PyTorch float32 사용 | 테스트 통과 |
| 대량 입력 처리 | PyTorch 배치 연산 구현 | 10,000건 처리 테스트 통과 |
| 기존 모델 구조 유지 | `SmallLSTM` 상속 및 공통 가중치 복사 | 초기 Logit 일치 |
| 실제 데이터 처리 | AI Train 953건 순전파 검증 | 통과 |
| 저장·복원 검증 | 초기 모델 가중치 저장 및 복원 | 출력 일치 |
| 모델 테스트 간소화 | 주요 기능 검증 중심으로 정리 | 간소화 코드 실행 통과 |

현재 제출 대상 파일은 다음 5개다.

- `inspect_gaps.py`
- `test_gaps.py`
- `model.py`
- `test_data_model.py`
- `README.md`

현재까지 모델 구현 및 기능 검증을 완료했으며, 실제 데이터 학습과 예측 성능 비교는 향후 진행할 예정이다.
