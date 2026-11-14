# michae18 모델 실습

## 담당 모델

- GitHub ID: `michae18`
- 담당 모델: 기본 LSTM (`SmallLSTM`)
- 작업 브랜치: `model/michae18-lstm-v2`
- 담당 미션: 기본 LSTM으로 다음 문제 예측하기
- 작업 PR: https://github.com/WaterMinCho/programming-study/pull/226
- 모델 구현 파일: `experiments/michae18/model.py`
- 실행 파일: `experiments/michae18/train.py`
- 입력 확인 파일: `experiments/michae18/input_check.py`
- 테스트 파일: `experiments/michae18/test_data_model.py`
- 현재 단계: 제출한 PR 코드 합성자료를 이용한 학습 전 LSTM 순전파 및 빈 이력·패딩 테스트 수정 및 확인
- 모델 학습 및 성능 평가: 미실행

## 실행한 명령과 결과

모든 명령은 `programming-study` 저장소 루트에서 실행합니다.

### 1. 합성자료 준비

```bash
python -m learning_server.starter --synthetic --out ../learning-demo-f4
```

- 데이터 경로: `../learning-demo-f4`
- 데이터 유형: 합성자료
- Track: `python`
- 데이터 버전: f4

실제 기록 기반 자료인 `recorded-python`은 공개 실행 예제에 사용하지 않습니다.

### 2. 입력 구조 확인

```bash
python -m experiments.michae18.input_check
```

실제 실행 결과:

```text
=== DATASET ===
데이터 경로: ../learning-demo-f4
데이터 개수: 8

=== INPUT SHAPES ===
questions: (4, 32)
concepts: (4, 32, 3)
results: (4, 32)
lengths: (4,)
query_question: (4,)
query_concepts: (4, 3)

=== TARGET SHAPE ===
(4,)

=== VOCABULARY SIZES ===
questions: 3
concepts: 3
```

입력 배치 크기는 4이며, 최대 과거 이력 길이는 32입니다. 데이터 내용 전체를 출력하지 않고 배열의 크기만 확인했습니다.

### 3. LSTM 순전파 확인

```bash
python -m experiments.michae18.train
```

실제 실행 결과:

```text
예측 확률: [0.7876594662666321, 0.7926620244979858, 0.7932559847831726, 0.7941094636917114]
예측 개수: 4
```

- 공개 합성자료의 첫 4개 예제를 사용했습니다.
- 모델은 학습하지 않았습니다.
- 초기화된 모델을 평가 모드에서 실행했습니다.
- 출력은 각 예제의 정답 확률을 나타내는 0~1 사이의 값입니다.
- 위 숫자는 실행 당시의 결과이며, 초기 가중치와 난수 시드가 달라지면 달라질 수 있습니다.

### 4. 빈 이력과 패딩 테스트

현재 실행한 명령:

```bash
python -m experiments.michae18.test_data_model
```

실제 실행 결과:

```text
PASS: 일부 빈 이력 처리
PASS: 전체 빈 이력 처리
PASS: 패딩 변경에 대한 예측 불변성
```

테스트 파일명을 `test_model.py`로 변경한 뒤에는 다음 명령으로 다시 확인합니다.

```bash
python -m experiments.michae18.test_data_model
```

테스트는 실제 학습 기록을 사용하지 않고 직접 만든 텐서를 사용합니다.

## 입력과 이번 정답을 구분한 방법

### 모델 입력 6개

과거 풀이 이력:

- `questions`: 과거 문제 ID
- `concepts`: 과거 문제의 개념 정보
- `results`: 과거 문제의 정답 여부
- `lengths`: 실제 과거 풀이 개수

이번에 예측할 문제:

- `query_question`: 이번 문제 ID
- `query_concepts`: 이번 문제의 개념 정보

### 입력과 정답 분리

`results`에는 과거 문제의 정답 여부만 포함합니다.

이번 문제의 실제 정답인 `targets`는 모델의 `forward()`에 전달하지 않습니다.

학습 단계에서는 예측 확률과 `targets`를 비교해 손실을 계산할 예정입니다.

이번 문제의 정답을 입력에 포함하면 데이터 누수(Data Leakage)가 발생할 수 있으므로 분리했습니다.

## LSTM 모델 구조

1. 과거 문제 ID를 `nn.Embedding`으로 벡터로 변환합니다.
2. 문제 임베딩, 개념 정보, 과거 정오답을 결합합니다.
3. `nn.LSTM`으로 과거 풀이 이력을 처리합니다.
4. 마지막 유효 시점의 hidden state를 학습자의 이력 상태로 사용합니다.
5. 이력 상태와 이번 문제의 임베딩 및 개념 정보를 결합합니다.
6. `nn.Linear`와 `Sigmoid`를 통해 이번 문제를 맞힐 확률을 출력합니다.

Embedding 크기는 첫 배치의 최대 문제 ID가 아니라 전체 `vocabulary`를 기준으로 설정합니다.
### 수정전
```python
num_questions = max(
    inputs["questions"].max().item(),
    inputs["query_question"].max().item()
) + 1
```

### 수정 후
```python
num_questions = len(vocabulary["questions"])
num_concepts = len(vocabulary["concepts"])
```

## 빈 이력과 패딩 처리

### 1. 빈 이력 (`lengths = 0`)

과거 풀이 기록이 없는 학습자도 예측할 수 있도록 이력 상태를 0으로 초기화했습니다.

```python
history_state = history_input.new_zeros(
    batch_size, self.lstm.hidden_size
)
```

`lengths > 0`인 행만 LSTM에 전달합니다.

빈 이력인 행은 초기화된 상태 벡터와 이번 문제 정보를 결합해 예측합니다.

직접 만든 테스트 입력에서 일부 행이 빈 경우와 모든 행이 빈 경우 모두 정상적인 예측을 확인했습니다.

### 2. 빈 자리(Padding)

문제 ID 0을 패딩 인덱스로 설정했습니다.

```python
self.embedding = nn.Embedding(
    num_questions, embeding_num, padding_idx=0
)
```

`pack_padded_sequence`를 사용해 실제 이력 길이까지만 LSTM이 처리하도록 구현했습니다.

테스트에서 실제 이력이 2개인 행의 3~4번째 위치만 변경해도 평가 모드의 예측값이 변하지 않음을 확인했습니다.

## 막힌 부분과 해결 내용

### 실제 자료 로딩 오류

초기 작업에서는 실제 기록 기반 공통 자료를 읽는 과정에서 다음 오류가 발생했습니다.

```text
ValueError: 이전 이력 집계로 만든 자료입니다.
```
#### 해결 방법
Sync fork 한 후, Source Tree main pull 하여 버전 맞춰 오류 해결했습니다.
이후 공개 실행 예제의 데이터 경로를 `../learning-demo-f4` 합성자료로 변경했습니다.

현재 합성자료 로딩과 순전파 실행은 정상적으로 확인했습니다.

### Python 모듈 실행 오류

`train.py`를 파일 경로로 직접 실행할 때 다음 오류가 발생했습니다.

```text
ModuleNotFoundError: No module named 'learning_server'
```

저장소 루트에서 `python -m experiments.michae18.train`으로 실행해 해결했습니다.

### 빈 이력 테스트

독립 테스트를 추가해 일부 빈 이력, 전체 빈 이력, 패딩 변경 불변성을 확인했습니다.

## 다음 작업

- 손실함수와 역전파를 이용한 실제 모델 학습 구현
- 학습·검증·테스트 분할을 이용한 성능 평가
- 모델 가중치 저장 및 불러오기 검증
- 서로 다른 배치와 데이터 분할에서도 Embedding ID 범위 확인
- 실행 환경과 전체 커밋 SHA 기록
- 이슈 121의 담당자와 LSTM 구조 및 실험 결과 공유

현재 구현 범위는 **학습 전 순전파와 입력 처리 검증**이며, 학습 완료 또는 성능 평가 완료로 기록하지 않습니다.