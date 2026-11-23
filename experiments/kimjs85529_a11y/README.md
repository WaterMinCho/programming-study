# kimjs85529_a11y - LSTM + Time Gap 실험 기록

- **담당 모델:** LSTM + 풀이 간격(Time Gap)
- **담당 이슈:** https://github.com/WaterMinCho/programming-study/issues/121
- **기본 LSTM 참고 PR:** https://github.com/WaterMinCho/programming-study/pull/226
- **이전 입력 확인 PR:** https://github.com/WaterMinCho/programming-study/pull/158
- **관련 PR:** https://github.com/WaterMinCho/programming-study/pull/319
- **실험 구현 브랜치:** `model/kimjs85529_a11y_timegap_lstm`
- **학습·평가 브랜치:** `model/kimjs85529_a11y_timegap_evaluation`
- **전처리·기능 검증일:** 2026-11-22
- **학습·평가 검증일:** 2026-11-24

## 예측할 값과 모델을 고른 이유

기본 LSTM이 사용하는 과거 문제 ID, 개념, 정오답 및 현재 문제 정보에 풀이 간격(Time Gap)을 추가하여 다음 문제의 정답 확률을 예측하도록 모델을 구현했다.

목적은 동일한 기본 LSTM 구조에서 시간 정보 추가 여부에 따른 예측 성능 차이를 비교하는 것이다.

시간 특성은 `[gap_log, gap_known]`으로 구성한다.

- `gap_log`: 마지막 풀이 후 경과 시간(초)을 일 단위로 변환하고 `log1p()`를 적용한 값
- `gap_known`: 시간 확인 여부를 나타내는 0.0 또는 1.0

시간 미확인 상태 `[0.0, 0.0]`과 실제 0초 간격 `[0.0, 1.0]`을 구분한다.

SmallLSTM을 기반으로 TimeGapLSTM을 구현하고, 실제 Recorded AI 데이터로 두 모델의 학습·Validation·Test 평가, 공식 Validation 채점 및 과적합 분석을 수행했다. 공식 채점에서 표본 수 부족 경고가 출력되었으므로 모델의 우열을 확정하지 않는다.

## 직접 구현한 부분

| 파일 | 역할 |
|---|---|
| `inspect_gaps.py` | Time Gap 개별 전처리, PyTorch 배치 연산, 장치 및 시드 설정 |
| `test_gaps.py` | 시간 전처리 테스트 10개 및 실제 데이터 검증 |
| `model.py` | 기본 LSTM 상속, 시간 특성 연결 및 공통 가중치 복사 |
| `test_data_model.py` | 기본 모델 비교, 시간 특성 적용, 역전파, 실제 데이터 순전파, 저장·복원 검증 |
| `train_compare.py` | SmallLSTM과 TimeGapLSTM 동일 조건 학습, Early Stopping, 학습 기록·최적 가중치 저장 |
| `test_compare.py` | 저장된 모델의 Validation·Test 평가, 공식 채점용 예측 CSV 생성, 과적합 분석 및 그래프 출력 |
| `README.md` | 실행 환경, 검증 방법, 학습·채점 결과 및 제한 사항 |

### 1. 기본 LSTM과의 관계

팀원 `michae18`의 `SmallLSTM` 모델을 상속하여 `TimeGapLSTM`을 구현했다.

- 기본 모델 경로: `experiments/michae18/model.py`
- 기본 모델 원본 전체 커밋 SHA: `1b95b0c6a45627ffde19afb7e60ff564b94c7254`
- **학습에 사용한 기본 모델 참고 커밋 SHA:** `ae1d76a9834b8a43bdcd9632a515275f25d61fc6`
- 기본 모델 참고 PR: https://github.com/WaterMinCho/programming-study/pull/226
- 기본 LSTM의 Embedding, LSTM 및 `encode_history()` 구조 유지
- 최종 Linear 계층에 시간 특성 `[gap_log, gap_known]` 두 개 추가

`copy_baseline_weights()`를 이용하여 기본 LSTM의 공통 가중치를 복사하고 시간 특성 가중치를 0으로 초기화했다.

동일한 입력에서 기본 LSTM과 TimeGapLSTM의 초기 Logit 일치를 확인했다. 비교 실험은 팀원의 `SmallLSTM` 클래스와 Dropout(p=0.2) 구조를 사용하되, 팀원의 학습된 가중치를 재사용하지 않고 `train_compare.py`로 두 모델을 각각 학습했다.

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
| 전처리·모델 구현 브랜치 | `model/kimjs85529_a11y_timegap_lstm` |
| 학습·평가 브랜치 | `model/kimjs85529_a11y_timegap_evaluation` |
| 최초 구현 작업 전체 커밋 SHA | `187d7ba4a39fbb602a023bcb49623f656f97df1d` |
| 전처리·모델 구현 당시 공통 main 전체 SHA | `6e6327b964778fddfdae5fd19c61bed51d67e742` |
| 2026-11-24 확인한 `main` 및 `origin/main` | `1b896bb4f25899daf07eb9d277c19b9fa3481642` |
| **학습·평가에 사용한 참고 모델 커밋 SHA** | `ae1d76a9834b8a43bdcd9632a515275f25d61fc6` |
| 기본 LSTM 원본 전체 커밋 SHA | `1b95b0c6a45627ffde19afb7e60ff564b94c7254` |
| `manifest.json` SHA-256 | 비공개 관리, 현재 README에 미기재 |
| 데이터 버전 | `features_version: 8` |
| 데이터 묶음 | `common-input-f8-20261118` |
| 자료 종류 | 실제 수집 자료(Recorded) |
| `question_min_count` | 사용 데이터의 `manifest.json`에 항목 없음 (값 확인 불가) |
| 변형 행 제외 여부 | 공식 Validation 채점 출력에서 끼운 변형 0건; 다른 분할의 제외 설정은 미확인 |
| 트랙 / 분할 | `ai` / Train·Validation·Test |
| 데이터 분할 크기 | Train 953건 / Validation 299건 / Test 260건 |
| 학습 방식 | Full Batch(Train 953, Validation 299) |
| Optimizer / 손실함수 | Adam(lr 0.001, weight_decay 0.001) / BCEWithLogitsLoss |
| Dropout / Early Stopping | p=0.2 / 최대 500 Epoch, patience 20 |
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

기본 LSTM과 초기 출력 비교, 시간 특성 적용, 빈 이력 및 패딩, 역전파, 실제 데이터 순전파, 모델 저장·복원 등을 확인한다.

### 5. 실제 데이터 학습 및 비교

`train_compare.py`로 SmallLSTM과 TimeGapLSTM을 동일한 조건에서 학습했다. 아래 명령은 재현용이며, 재실행하면 `comparison_results/`의 기존 체크포인트와 학습 이력을 덮어쓴다.

```powershell
python -m experiments.kimjs85529_a11y.train_compare
```

학습 데이터는 Recorded AI Train 953건, Validation 299건이며 Full Batch와 Seed 42를 사용했다. 최적 Validation Loss 기준의 모델 가중치 및 학습 이력을 `comparison_results/`에 저장하였다.

### 6. 저장된 모델 평가·과적합 분석

```powershell
# 기존 최적 모델로 Test 평가 후 과적합 분석표 및 그래프 출력
python -m experiments.kimjs85529_a11y.test_compare

# Validation 평가 후 그래프 출력
python -m experiments.kimjs85529_a11y.test_compare --split validation

# 저장된 학습 이력으로 과적합 분석 및 그래프만 출력
python -m experiments.kimjs85529_a11y.test_compare --analyze-overfitting
```

`test_compare.py`는 모듈 실행과 파일 직접 실행 모두를 지원하도록 프로젝트 루트를 `sys.path`에 추가한다. 기본 실행 시 평가 종료 후 과적합 분석 결과를 출력하고 `SmallLSTM_overfitting.png`, `TimeGapLSTM_overfitting.png`를 저장한다. 2026-11-24 실행에서는 두 파일의 저장과 분석 완료를 확인했다. GUI 창의 실제 표시 여부는 로그만으로 확인되지 않는다.

### 7. 공식 Validation 채점용 예측 파일 생성

```powershell
python -m experiments.kimjs85529_a11y.test_compare --split validation --export-predictions
```

예측 파일은 저장소 외부 `C:\study-data\model-predictions`에 `small-lstm-validation.csv`, `timegap-lstm-validation.csv` 이름으로 생성한다. CSV 열은 `event_id,probability,model_version`이며 기존 파일이 존재하면 덮어쓰지 않고 `FileExistsError`가 발생한다.

### 8. 공식 `learning_server.score` 실행

```powershell
python -m learning_server.score --dataset C:\study-data\common-input-f8-20261118\recorded --track ai --predictions C:\study-data\model-predictions\small-lstm-validation.csv --out C:\study-data\model-predictions\small-lstm-validation-score.json

python -m learning_server.score --dataset C:\study-data\common-input-f8-20261118\recorded --track ai --predictions C:\study-data\model-predictions\timegap-lstm-validation.csv --out C:\study-data\model-predictions\timegap-lstm-validation-score.json
```

두 명령을 실제로 실행해 Validation 공식 채점을 완료하였다. `--split` 생략 시 Validation 구간이며, 공식 Test 채점은 아직 수행하지 않았다. 생성된 원자료, 체크포인트, 개별 예측 CSV, 점수 JSON은 GitHub에 공개하지 않는다.

## 결과와 오류 사례

### 1. 시간 전처리 테스트 재검증

2026-11-22에 전처리·모델 구현 커밋 `187d7ba4a39fbb602a023bcb49623f656f97df1d`의 코드를 기준으로 시간 전처리 테스트를 실행했다.

검증 시 브랜치:

```text
model/kimjs85529_a11y_timegap_lstm
```

검증 시 HEAD:

```text
187d7ba4a39fbb602a023bcb49623f656f97df1d
```

먼저 다음 명령을 실행했다.

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

전체 테스트 확인 완료 (테스트 1~10 실행)
```

테스트 1~10이 모두 통과했으며, 실제 AI Train 데이터 953건의 개별·배치 전처리 결과가 일치했다.

- 시간 확인 가능: 757건
- 시간 미확인: 196건
- 실제 빈 이력: 3건
- 대량 배치 테스트: 10,000건 처리 통과

마지막 출력 한 줄:

```text
전체 테스트 확인 완료 (테스트 1~10 실행)
```

실제 AI Train 953건의 개별·배치 처리 결과가 일치했으며, 시간 확인 가능 757건과 미확인 196건을 확인했다.

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

`test_data_model.py`를 Windows CPU 환경에서 실행하여 다음 항목을 확인했다.

```text
사용 장치: cpu
통과: 기본 LSTM과 초기 출력 일치
통과: 출력 형상·확률·빈 이력·패딩
통과: 시간 미확인/0초 구분
통과: gap_log의 출력 적용
통과: 역전파 및 가중치 갱신
통과: 실제 데이터 전체 순전파 953 건
통과: 모델 저장·복원 후 출력 일치

기능 검증 완료
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
| gap_log 적용 | 0일과 1일 입력의 Logit 차이 비교 | 통과 |
| 역전파 | 시간 가중치 및 LSTM 기울기 생성 확인 | 통과 |
| 가중치 갱신 | SGD 1회 갱신 후 가중치 변경 확인 | 통과 |
| 실제 데이터 | AI Train 953건 전체 순전파 | 통과 |
| 저장·복원 | 복원 전후 Logit 일치 확인 | 통과 |

시간 미확인 `[0.0, 0.0]`과 실제 0초 `[0.0, 1.0]`을 비교할 때 시간 가중치를 1로 설정하면 Logit 차이가 1이 되는지 확인했다.

또한 0일과 1일의 `gap_log` 차이가 `log(2)`에 해당하는지 확인했다.

이는 모델에 시간 특성이 정상적으로 연결됐다는 기능 검증이며, **이 검증 단독으로는** 실제 예측 정확도의 향상을 의미하지 않는다. 별도로 실행한 학습 및 평가 결과는 아래에 추가하였다.

`test_data_model.py`는 기능 검증만 수행한다. 실제 데이터 학습과 평가는 각각 `train_compare.py`, `test_compare.py`에서 수행한다.

### 4. 모델 저장·복원 검증

`torch.save(model.state_dict(), path)`를 사용해 모델 가중치를 임시 파일로 저장했다.

새로운 TimeGapLSTM 객체를 생성하고 `torch.load(..., weights_only=True)`와 `load_state_dict()`로 복원했다.

동일한 입력에 대해 복원 전후 Logit이 일치하는지 확인했다.

임시 파일은 `TemporaryDirectory()`를 사용하여 `with` 블록 종료 시 자동으로 삭제했다.

`test_data_model.py`에서 초기 모델의 저장·복원을 검사했고, `test_compare.py`에서 저장된 최적 가중치(`.pt`)를 별도의 Python 실행에서 불러와 Validation·Test 평가를 수행했다.

### 5. 기능 및 평가 재실행 검증

```powershell
cd C:\programming-study
python -m experiments.kimjs85529_a11y.test_gaps
python -m experiments.kimjs85529_a11y.test_data_model
python -m experiments.kimjs85529_a11y.test_compare
```

전처리 테스트 **1~10 모두 통과**했고 `test_data_model.py`에서 **Dropout(p=0.2) 호출**, 초기 Logit 일치, 시간 특성 적용, 역전파, AI Train 953건 Full Batch 순전파, 모델 저장·복원 등이 통과했다. 통합 `test_compare.py`는 Test 260건을 평가한 뒤 과적합 분석표를 출력하고 두 그래프를 저장했으며, 최적 모델을 재학습하지 않았다.

| 과적합 분석 | SmallLSTM | TimeGapLSTM |
|---|---:|---:|
| 학습 History Epoch 수 | 380 | 356 |
| 최적 Epoch | 360 | 336 |
| 종료 Epoch | 380 | 356 |
| 최적 Train Loss | 0.207787 | 0.211232 |
| 최적 Validation Loss | 0.295160 | 0.294527 |
| Train-Validation Loss 격차 | 0.087374 | 0.083295 |
| 최적 이후 Validation Loss 증가량 | +0.006673 | +0.001175 |

그래프 파일은 `comparison_results/SmallLSTM_overfitting.png`, `comparison_results/TimeGapLSTM_overfitting.png`에 저장하였다. 콘솔 종료까지 확인하였지만 화면의 그래프 창 표시 자체는 직접 확인한 근거가 아니다.

### 6. 실제 학습 및 Early Stopping 결과

동일한 Recorded AI Train 953건, Validation 299건에 대해 Full Batch 학습을 진행했다. Seed 42, Adam(lr 0.001, weight_decay 0.001), BCEWithLogitsLoss, Dropout 0.2, Epoch 최대 500, patience 20을 적용했다.

| 항목 | SmallLSTM | TimeGapLSTM |
|---|---:|---:|
| 파라미터 수 | 19,884 | 19,886 |
| 최저 Validation Loss Epoch | 360 | 336 |
| Early Stopping 종료 Epoch | 380 | 356 |
| 최적 Epoch Train Loss | 0.207787 | 0.211232 |
| 최적 Epoch Validation Loss | 0.295160 | 0.294527 |
| 최적 Epoch Train Accuracy | 0.928646 | 0.926548 |
| 최적 Epoch Validation Accuracy | 0.879599 | 0.879599 |
| 최적 이후 최종 Validation Loss | 0.301833 | 0.295702 |
| 최적 이후 Validation Loss 증가량 | +0.006673 | +0.001175 |

최적 Epoch 이후 두 모델 모두 Train Loss가 감소하는 동안 Validation Loss는 소폭 증가했다. Early Stopping이 더 큰 성능 저하를 제한하는 역할을 했으나, 단일 실행 기록만으로 Time Gap이 과적합을 억제한다고 확정할 수는 없다.

### 7. Validation/Test 자체 평가

`test_compare.py`로 저장된 최적 체크포인트를 불러와 두 모델을 동일 조건에서 비교하였다. **2026-11-24에 Test(260건) 평가를 재실행하여 아래 Test 수치가 그대로 재현되는 것을 확인했다.** 이 표의 Loss는 `BCEWithLogitsLoss`, Accuracy·Precision·Recall·F1은 확률 0.5 기준의 분류 지표이다.

| 구간 / 지표 | SmallLSTM | TimeGapLSTM |
|---|---:|---:|
| Validation(299) Loss | 0.295160 | 0.294527 |
| Validation Accuracy | 0.879599 | 0.879599 |
| Validation Precision | 0.879195 | 0.879195 |
| Validation Recall | 1.000000 | 1.000000 |
| Validation F1 | 0.935714 | 0.935714 |
| Validation TP / TN / FP / FN | 262 / 1 / 36 / 0 | 262 / 1 / 36 / 0 |
| Test(260) Loss | 0.365200 | 0.362452 |
| Test Accuracy | 0.865385 | 0.865385 |
| Test Precision | 0.865385 | 0.865385 |
| Test Recall | 1.000000 | 1.000000 |
| Test F1 | 0.927835 | 0.927835 |
| Test TP / TN / FP / FN | 225 / 0 / 35 / 0 | 225 / 0 / 35 / 0 |

Validation에서는 실제 오답 37건 중 36건을 정답으로 잘못 예측했고, Test에서는 오답 35건을 모두 정답으로 예측했다. 두 모델의 분류 정확도는 동일하므로 작은 손실 개선만을 근거로 정답·오답 판별 능력이 나아졌다고 할 수 없다. Test 자체 평가는 **공식 Test 채점**과 다르다.

### 8. 공식 Validation 채점 원문: SmallLSTM

채점 명령:

```powershell
python -m learning_server.score --dataset C:\study-data\common-input-f8-20261118\recorded --track ai --predictions C:\study-data\model-predictions\small-lstm-validation.csv --out C:\study-data\model-predictions\small-lstm-validation-score.json
```

```text
ai validation 구간: 299행, 오답 37행, 가명 3개, 끼운 변형 0행 (자료 버전 8, 묶음 40141519fa79)
표의 값: 값 ± 행 독립 표준오차 / 가명 묶음 표준오차
이름 | 로그 손실 | Brier | ROC-AUC | 정확도
small-lstm-v1 | 0.2952 ± 0.0358 / 0.4815 | 0.0873 ± 0.0128 / 0.1969 | 0.8357 ± 0.0277 / 0.0766 | 0.8796 ± 0.0188 / 0.3534
majority | - | 0.1237 ± 0.0191 / 0.3694 | - | 0.8763 ± 0.0190 / 0.3694
overall-mean | 0.3871 ± 0.0472 / 0.9141 | 0.1106 ± 0.0161 / 0.3120 | 0.5000 ± 0.0508 / 0.0000 | 0.8763 ± 0.0190 / 0.3694
per-question | 0.4819 ± 0.0623 / 1.1781 | 0.1257 ± 0.0170 / 0.3196 | 0.4849 ± 0.0511 / 0.1114 | 0.8763 ± 0.0190 / 0.3694
per-concept | 0.4751 ± 0.0624 / 1.1722 | 0.1213 ± 0.0164 / 0.3107 | 0.4745 ± 0.0513 / 0.0819 | 0.8763 ± 0.0190 / 0.3694
per-participant | 0.3632 ± 0.0539 / 0.7901 | 0.1035 ± 0.0156 / 0.2808 | 0.8014 ± 0.0315 / 0.3406 | 0.8763 ± 0.0190 / 0.3694
past-concept-ratio-v1 | 0.3174 ± 0.0179 / 0.2580 | 0.0936 ± 0.0073 / 0.1066 | 0.8874 ± 0.0214 / 0.1903 | 0.8796 ± 0.0188 / 0.3164
이 구간은 오답 37행, 가명 3개라 모델 비교 근거로 쓰기 어렵습니다.

처음 보는 문제(학습 번호표에 없는 문제) 35개: 72행, 오답 13행, 가명 3개 미만, 끼운 변형 0행
이름 | 로그 손실 | Brier | ROC-AUC | 정확도
small-lstm-v1 | 0.4657 ± 0.0940 / 계산할 수 없음 | 0.1454 ± 0.0342 / 계산할 수 없음 | 0.6962 ± 0.0732 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
majority | - | 0.1806 ± 0.0456 / 계산할 수 없음 | - | 0.8194 ± 0.0453 / 계산할 수 없음
overall-mean | 0.5277 ± 0.1130 / 계산할 수 없음 | 0.1585 ± 0.0386 / 계산할 수 없음 | 0.5000 ± 0.0891 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
per-question | 0.5923 ± 0.1189 / 계산할 수 없음 | 0.1754 ± 0.0381 / 계산할 수 없음 | 0.4100 ± 0.0906 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
per-concept | 0.5834 ± 0.1202 / 계산할 수 없음 | 0.1670 ± 0.0356 / 계산할 수 없음 | 0.4804 ± 0.0897 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
per-participant | - | - | - | -
past-concept-ratio-v1 | 0.5348 ± 0.0316 / 계산할 수 없음 | 0.1786 ± 0.0144 / 계산할 수 없음 | 0.7014 ± 0.0726 / 계산할 수 없음 | 0.7778 ± 0.0490 / 계산할 수 없음
처음 보는 문제 행은 오답 13행, 가명 3개 미만이라 모델 비교 근거로 쓰기 어렵습니다.
```

### 9. 공식 Validation 채점 원문: TimeGapLSTM

채점 명령:

```powershell
python -m learning_server.score --dataset C:\study-data\common-input-f8-20261118\recorded --track ai --predictions C:\study-data\model-predictions\timegap-lstm-validation.csv --out C:\study-data\model-predictions\timegap-lstm-validation-score.json
```

```text
ai validation 구간: 299행, 오답 37행, 가명 3개, 끼운 변형 0행 (자료 버전 8, 묶음 40141519fa79)
표의 값: 값 ± 행 독립 표준오차 / 가명 묶음 표준오차
이름 | 로그 손실 | Brier | ROC-AUC | 정확도
timegap-lstm-v1 | 0.2945 ± 0.0355 / 0.4798 | 0.0869 ± 0.0127 / 0.1964 | 0.8361 ± 0.0277 / 0.0749 | 0.8796 ± 0.0188 / 0.3534
majority | - | 0.1237 ± 0.0191 / 0.3694 | - | 0.8763 ± 0.0190 / 0.3694
overall-mean | 0.3871 ± 0.0472 / 0.9141 | 0.1106 ± 0.0161 / 0.3120 | 0.5000 ± 0.0508 / 0.0000 | 0.8763 ± 0.0190 / 0.3694
per-question | 0.4819 ± 0.0623 / 1.1781 | 0.1257 ± 0.0170 / 0.3196 | 0.4849 ± 0.0511 / 0.1114 | 0.8763 ± 0.0190 / 0.3694
per-concept | 0.4751 ± 0.0624 / 1.1722 | 0.1213 ± 0.0164 / 0.3107 | 0.4745 ± 0.0513 / 0.0819 | 0.8763 ± 0.0190 / 0.3694
per-participant | 0.3632 ± 0.0539 / 0.7901 | 0.1035 ± 0.0156 / 0.2808 | 0.8014 ± 0.0315 / 0.3406 | 0.8763 ± 0.0190 / 0.3694
past-concept-ratio-v1 | 0.3174 ± 0.0179 / 0.2580 | 0.0936 ± 0.0073 / 0.1066 | 0.8874 ± 0.0214 / 0.1903 | 0.8796 ± 0.0188 / 0.3164
이 구간은 오답 37행, 가명 3개라 모델 비교 근거로 쓰기 어렵습니다.

처음 보는 문제(학습 번호표에 없는 문제) 35개: 72행, 오답 13행, 가명 3개 미만, 끼운 변형 0행
이름 | 로그 손실 | Brier | ROC-AUC | 정확도
timegap-lstm-v1 | 0.4609 ± 0.0918 / 계산할 수 없음 | 0.1445 ± 0.0339 / 계산할 수 없음 | 0.7027 ± 0.0724 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
majority | - | 0.1806 ± 0.0456 / 계산할 수 없음 | - | 0.8194 ± 0.0453 / 계산할 수 없음
overall-mean | 0.5277 ± 0.1130 / 계산할 수 없음 | 0.1585 ± 0.0386 / 계산할 수 없음 | 0.5000 ± 0.0891 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
per-question | 0.5923 ± 0.1189 / 계산할 수 없음 | 0.1754 ± 0.0381 / 계산할 수 없음 | 0.4100 ± 0.0906 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
per-concept | 0.5834 ± 0.1202 / 계산할 수 없음 | 0.1670 ± 0.0356 / 계산할 수 없음 | 0.4804 ± 0.0897 / 계산할 수 없음 | 0.8194 ± 0.0453 / 계산할 수 없음
per-participant | - | - | - | -
past-concept-ratio-v1 | 0.5348 ± 0.0316 / 계산할 수 없음 | 0.1786 ± 0.0144 / 계산할 수 없음 | 0.7014 ± 0.0726 / 계산할 수 없음 | 0.7778 ± 0.0490 / 계산할 수 없음
처음 보는 문제 행은 오답 13행, 가명 3개 미만이라 모델 비교 근거로 쓰기 어렵습니다.
```

### 10. 공식 채점 비교·해석

| 지표 | SmallLSTM | TimeGapLSTM |
|---|---:|---:|
| 전체 Validation 로그 손실 (낮을수록 좋음) | 0.2952 | 0.2945 |
| 전체 Brier (낮을수록 좋음) | 0.0873 | 0.0869 |
| 전체 ROC-AUC (높을수록 좋음) | 0.8357 | 0.8361 |
| 전체 정확도 | 0.8796 | 0.8796 |
| 처음 보는 문제 로그 손실 | 0.4657 | 0.4609 |
| 처음 보는 문제 Brier | 0.1454 | 0.1445 |
| 처음 보는 문제 ROC-AUC | 0.6962 | 0.7027 |
| 처음 보는 문제 정확도 | 0.8194 | 0.8194 |

로그 손실을 계산하는 기준선 다섯 개 중 최저값은 **`past-concept-ratio-v1`의 0.3174**다(`majority`는 로그 손실을 표기하지 않음).

- SmallLSTM − 최저 기준선 = `0.2952 − 0.3174 = -0.0222`
- TimeGapLSTM − 최저 기준선 = `0.2945 − 0.3174 = -0.0229`

따라서 두 모델의 로그 손실과 Brier는 해당 기준선보다 낮았다. 그러나 ROC-AUC는 같은 기준선(`0.8874`)이 SmallLSTM(`0.8357`)과 TimeGapLSTM(`0.8361`)보다 높았다.

TimeGapLSTM은 SmallLSTM보다 전체 Validation 손실·Brier가 소폭 낮고 ROC-AUC가 소폭 높지만, **전체 정확도는 같고 두 모델의 혼동행렬도 같다.** 모델별 표준오차는 두 모델 차이에 대한 유의성 검정 결과가 아니며, 공식 채점 경고가 있으므로 우열에 대한 확정 결론을 내리지 않는다.

처음 보는 문제 구간은 오답 13건이고 가명 수가 공개 규칙상 `3개 미만`으로 표시되어 가명 묶음 표준오차를 계산할 수 없다. 공개 README에서도 가명 수를 더 좁혀 추정하지 않는다.

### 11. 오류 사례 및 실험의 한계

- **기능 검증:** `test_gaps.py` 및 `test_data_model.py` 테스트 통과. 원본 타임스탬프와 공통 시간값의 독립적 대조는 수행하지 않았다.
- **VSCode 실행 경로 오류:** 파일 직접 실행 시 `ModuleNotFoundError: No module named 'learning_server'`가 발생하였다. `test_compare.py` 시작 부분에서 프로젝트 루트를 `sys.path`에 추가해 직접 실행 경로를 지원하도록 수정했다. 2026-11-24에는 **PowerShell `python -m` 방식으로 통합 분석이 정상 실행**되었으며, VSCode 실행 버튼으로 직접 재검증했다는 의미는 아니다.
- **공식 채점 CSV 중복 저장:** 이미 만든 예측 파일은 덮어쓰지 않도록 설계했으며 재생성을 시도하면 `FileExistsError`가 예상된다. 이는 예측 결과 보존 장치이며 실제 채점 실패 사례로 기록하지 않는다.
- **공식 채점 자체:** 두 모델 모두 채점 오류 없이 완료. 다만 전체 Validation에 **오답 37행·가명 3개**, 처음 보는 문제에 **오답 13행·가명 3개 미만**으로 공식 경고가 출력되었다. 해당 값은 성능 우열 판정이 아니라 **채점 파이프라인 실행 확인**으로 기록한다.
- **클래스 불균형:** Validation에서 FP 36 / TN 1, Test에서 FP 35 / TN 0이다. 두 모델 모두 오답 판별이 부족하며 정확도만으로 모델이 유용하다고 말할 수 없다.
- **재현성:** Seed 42와 동일 코드·데이터·환경에서는 반복 학습 결과가 같을 것으로 기대되지만, 환경이 달라지면 비결정성이 발생할 수 있다. Test 추론은 동일 가중치와 데이터에서 동일 값이 기대된다.
- **일반화 한계:** 실제 Validation/Test는 소수의 참가자가 남긴 기록이며, 새로운 학습자에 대한 예측 효과를 입증하지 않는다.

### 12. 검증 범위와 한계

**실제 데이터 학습, 두 모델 성능 비교, 최적 가중치 복원 및 공식 Validation 채점을 완료했다.**

검증 범위에 포함되지 않은 항목은 원본 풀이 타임스탬프와 `query_gap_seconds`의 독립적 대조, UNK 제외 정책의 성능 영향 실험, 공식 Test 채점 및 새로운 학습자에 대한 일반화 검증이다. `question_min_count`는 사용 데이터의 `manifest.json`에서 확인할 수 없으며, 파일 자체의 전체 SHA-256은 기록하지 않았다.

공식 Validation 전체는 **299행·오답 37행·가명 3개**, 처음 보는 문제 구간은 **72행·오답 13행·가명 3개 미만**이어서 공식 채점 도구가 모델 비교 근거로 쓰기 어렵다고 경고했다. 따라서 TimeGapLSTM의 로그 손실이 소폭 낮다는 사실을 통계적으로 입증된 우월성으로 표현하지 않는다.

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

### 9. 실제 데이터 학습·Early Stopping

`train_compare.py`에서 Seed 42, 동일 Full Batch, Adam(lr 0.001, weight_decay 0.001), Dropout 0.2, patience 20 조건으로 두 모델을 학습했다. 손실은 `BCEWithLogitsLoss`를 사용하고 최저 Validation Loss의 가중치를 저장했다.

### 10. 저장 가중치로 Validation·Test 예측

`test_compare.py`에서 최적 가중치를 복원한 뒤 `model.eval()`과 `torch.no_grad()`로 평가했다. 평가 Loss·Accuracy·Precision·Recall·F1·혼동행렬을 출력하고, 필요하면 Sigmoid 확률과 원본 `event_id`를 공식 채점용 CSV로 내보낸다.

### 11. 과적합 분석 및 공식 채점

학습 History CSV를 읽어 최적 Epoch 및 Train/Validation 격차를 비교하고 모델별 Loss·Accuracy 그래프를 생성한다. `learning_server.score`에 Validation 예측 CSV를 전달해 여섯 기준선과 비교하고, 표준오차·처음 보는 문제 평가 및 경고를 기록한다. 이 과정은 재학습하지 않는다.

## 질문을 받고 바꾼 부분

| 확인 항목 | 구현 및 검증 방법 | 확인 결과 |
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
| 기본 모델 설정 | 팀원 참고 SHA `ae1d76a9834b8a43bdcd9632a515275f25d61fc6` 및 Dropout 0.2 사용 | Dropout 호출 테스트 통과 |
| 실제 학습 비교 | `train_compare.py`로 동일 조건에서 모델 2개 학습 | 최적 Epoch 360 / 336 기록 |
| 과적합 분석 파일 통합 | `analyze_overfitting.py` 기능을 `test_compare.py`에 통합 | 분석표·PNG 2개 저장 확인 |
| VSCode 직접 실행 오류 | `test_compare.py`의 `sys.path`에 저장소 루트 추가 | `learning_server` import 문제 대응; 모듈 방식 실행 성공 |
| 공식 Validation 채점 기록 | `learning_server.score` 결과와 기준선 6개, 표준오차·UNK 구간 경고 기록 | 두 모델 공식 Validation 실행 완료 |
| 최신 공통 main 기준 | `main`, `origin/main` SHA를 `1b896bb4f25899daf07eb9d277c19b9fa3481642`로 확인 | 2026-11-24 Git 명령 결과 |
| 실행 재검증 | 전처리·모델 테스트·Test 비교·과적합 통합 실행 | 세 명령 모두 정상 종료 |

공개 저장소의 실험 소스 파일은 다음 7개로 구성된다.

- `inspect_gaps.py`
- `test_gaps.py`
- `model.py`
- `test_data_model.py`
- `train_compare.py`
- `test_compare.py`
- `README.md`

모델 구현 및 기능 검증, 실제 Recorded AI 데이터 학습, Validation·Test 자체 평가, 과적합 분석, 공식 Validation 채점을 완료했다. 공개 PR에는 전처리·모델·학습·평가 코드와 실험 기록 README만 포함했으며, 실제 학습 데이터, 모델 가중치, 학습 이력 CSV, 그래프 이미지, 개별 예측 CSV 및 공식 채점 JSON은 포함하지 않았다.
