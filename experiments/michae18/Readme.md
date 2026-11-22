# michae18 모델 실습

## 담당 모델

- GitHub ID: `michae18`
- 담당 모델: 기본 LSTM (`SmallLSTM`)
- 작업 브랜치: `model/michae18-lstm-v2`
- 담당 미션: 기본 LSTM으로 다음 문제 예측하기
- 작업 PR: https://github.com/WaterMinCho/programming-study/pull/226
- 모델 구현 파일: `experiments/michae18/model.py`
- 학습 실행 파일: `experiments/michae18/train.py`
- 입력 확인 파일: `experiments/michae18/input_check.py`
- 테스트 파일: `experiments/michae18/test_data_model.py`

### 현재 진행 상황
기존 합성자료 기반 LSTM 순전파 및 입력 처리 검증을 완료한 후, 실제 기록 기반 F8 데이터로 학습과 검증을 진행했습니다.

이번 실험에서는 과적합 완화를 위해 다음 방법을 적용했습니다.

Dropout (p=0.2)

Adam Optimizer의 Weight Decay (1e-3)

Validation Loss 기반 Early Stopping (patience=20)

학습 및 검증 결과를 Epoch별로 기록하고, Train / Validation Loss와 Accuracy 그래프를 작성했습니다.

- 현재 단계: 실제 기록 기반 데이터 학습 및 Validation 평가 완료. 최종 Test 평가와 추가 성능 지표 분석은 미완료.

## 실행 조건

| 항목 | 사용 값 |
|---|---|
| 운영체제 | Windows |
| Python | 3.13.5 |
| 프로젝트 경로 | `C:\programming-study` |
| 작업 브랜치 | `model/michae18_lstm_v2` |
| 실제 자료 경로 | `C:\Users\user\Documents\model_study\study-data\common-input-f8-20261118` (Git 저장소 외부) |
| 입력 버전 | `features_version: 8` |
| 자료 종류 | Recorded Data (`recorded`) |
| 데이터 형식 | `format: 1` |
| 트랙 및 분할 | `ai` |
| CUDA 사용 가능 | False |
| PyTorch CUDA 버전 | None |
| 학습 장치 | CPU |
| AI Train 기록 수 | 953 |
| AI Validation  기록 수 | 299 |
| AI Test  기록 수 | 260 |
| 입력 확인용 배치 크기 | 각 데이터 수만큼 |
| 과거 이력 길이 | 32 |
| 원본 manifest의 `history_limit` | 128 |
| 시드 | 42 |
| 본인 Fork | `michae18/programming-study` |
| 작업 기준 커밋 SHA | 미확인 |
| 공통 원격 main SHA | 미확인 |
| `manifest.json` SHA-256 | `3c712036a862f11ffeee99a2bbe5cc3d96cbdb6a7e6e2bc6e4ecac0bf4954133` |
| `question_min_count` | 미확인 |
| 변형 행 제외 여부 | 미확인 |
| PyTorch 버전 | `2.15.0` |
| CPU | Intel Core i7-9750H @ 2.60GHz |
| GPU | NVIDIA GeForce GTX 1650 |
| hidden_size = 16, 임베딩 차원 = 16, 파라미터 수 | 모델 통합 및 학습 미실행 |

## 실행한 명령과 결과

모든 명령은 `programming-study` 저장소 루트에서 실행합니다.

### 1. 데이터 준비
'SEED 값 : 42' 로 고정
```bash
python -m zipfile -e ZIP파일경로 ../study-data/common-input-f8-20261118
```

- 데이터 경로: `../study-data/common-input-f8-20261118/recorded/`
- 데이터 유형: 실제 데이터
- Track: `python`
- 데이터 버전: 8

### 2. 입력 구조 확인

```bash
python -m experiments.michae18.input_check
```

실제 실행 결과:

```text
데이터 경로: ../study-data/common-input-f8-20261118/recorded
데이터 개수: 953

=== INPUT SHAPES ===
questions: (953, 32)
concepts: (953, 32, 235)
results: (953, 32)
lengths: (953,)
query_question: (953,)
query_concepts: (953, 235)

=== TARGET SHAPE ===
(953,)

=== VOCABULARY SIZES ===
questions: 146
concepts: 235

 ****************************************

=== VALIDATION DATASET ===
데이터 경로: ../study-data/common-input-f8-20261118/recorded
데이터 개수: 299

=== INPUT SHAPES ===
questions: (299, 32)
concepts: (299, 32, 235)
results: (299, 32)
lengths: (299,)
query_question: (299,)
query_concepts: (299, 235)

=== TARGET SHAPE ===
(299,)

=== VOCABULARY SIZES ===
questions: 146
concepts: 235

 ****************************************

=== TEST DATASET ===
데이터 경로: ../study-data/common-input-f8-20261118/recorded
데이터 개수: 260

=== INPUT SHAPES ===
questions: (260, 32)
concepts: (260, 32, 235)
results: (260, 32)
lengths: (260,)
query_question: (260,)
query_concepts: (260, 235)

=== TARGET SHAPE ===
(260,)

=== VOCABULARY SIZES ===
questions: 146
concepts: 235

```

입력 배치 크기는 train은 953, validation은 299, test는 260이며, 최대 과거 이력 길이는 32입니다. 데이터 내용 전체를 출력하여 입력값과 출력값, vocabulary의 크기를 확인했습니다.

### 3. LSTM 순전파 확인

```bash
python -m experiments.michae18.train
```

학습 로그:

```text
epoch: 0 | train_loss: 0.6850 |
                val_loss: 0.6797 | train_acc: 0.5950 | val_acc: 0.6087
epoch: 100 | train_loss: 0.2769 |
                val_loss: 0.3686 | train_acc: 0.9213 | val_acc: 0.8763
epoch: 200 | train_loss: 0.2464 |
                val_loss: 0.3490 | train_acc: 0.9234 | val_acc: 0.8763
epoch: 300 | train_loss: 0.2266 |
                val_loss: 0.3095 | train_acc: 0.9234 | val_acc: 0.8796
early stopping at epoch 366
```

마지막 Epoch 기록:
```text
{
    "epoch": 366,
    "train_loss": 0.20130175352096558,
    "train_acc": 0.9286463856697083,
    "val_loss": 0.3001195192337036,
    "val_acc": 0.8795986771583557
}
```
학습은 최대 500 Epoch로 설정했으나 Early Stopping에 의해 366 Epoch에서 종료됐습니다.

위 값은 마지막으로 기록된 Epoch의 성능입니다. 최적 Epoch와 최적 Validation Loss는 별도 출력으로 확인해야 합니다.

#### LSTM 모델 구조
실제 출력된 모델 구조:
```text
SmallLSTM(
  (embedding): Embedding(146, 16, padding_idx=0)
  (lstm): LSTM(252, 16, batch_first=True)
  (dropout): Dropout(p=0.2, inplace=False)
  (fc): Linear(in_features=267, out_features=1, bias=True)
)
```

- 실 데이터의 train, validation, test 데이터를 사용하였으며, 손실 함수는 BCEWithLogitsLoss로 정하였으며, 최적화 함수는 adam으로 구현하였고,
과적합 방지를 위해 early_stopping, weight_decay = 1e-3으로 사용하였으며 추가 검증이 필요합니다.
- 모델은 학습과 검증을 진행하였으며, 추가적인 검증이 필요합니다.
- 위 숫자는 실행 당시의 결과이며, seed 값과 합성 데이터에 따라 값이 달라질 수 있습니다.

### 4. 빈 이력과 패딩 테스트

```bash
python -m experiments.michae18.test_data_model
```

텐서 데이터:
```
[0, 0, 0, 0],
[1, 2, 0, 0],
[0, 0, 0, 0],
[3, 4, 5, 6]
```

실제 실행 결과:

```text
PASS: 일부 빈 이력 처리
PASS: 전체 빈 이력 처리
PASS: 패딩 변경에 대한 예측 불변성
```

테스트는 합성자료를 사용하지 않고 직접 만든 텐서를 사용하여 일부 빈 이력과 전체 빈 이력, 패딩 변경에 대한 예측 불변성에 대한  테스트를 진행하였으며, 정상 동작을 확인하였습니다.

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
6. 과적합 현상이 발견되어 dropout(0.2)를 사용하여 과적합 방지를 시도하였습니다.
7. nn.Linear를 통해 이번 문제의 정답 예측 점수(logit)를 반환합니다.

반환값 : sigmoid -> logit 변경, dropout 사용

Embedding 크기는 첫 배치의 최대 문제 ID가 아니라 전체 `vocabulary`를 기준으로 설정합니다.
### 수정전
super().__init__()
        # 문제 번호를 컴퓨터를 위해 번역한다 nn.Embedding 사용
        self.embedding = nn.Embedding(num_questions, embeding_num,padding_idx=0)
        # 과거 기록을 읽는 기억 장치(문제 푼 순서를 따라가며 학습 상태를 계산), 학습 가능한 내부 벡터 생성한다.
        self.lstm = nn.LSTM(embeding_num + num_concepts + 1, hidden_num,batch_first=True)
        # 점수 계산(분류기 생성한다.)
        self.fc = nn.Linear(hidden_num + embeding_num + num_concepts,1)

        forward() 내부 
        # 과거 상태 + 예측할 문제
        combined = torch.cat(
            [history_state, query_vector],
            dim=-1
        )

        # dropout 추가하기(입력 값으로 combined 사용)
        # 과적합을 막기 위한 수단
        dropout = self.dropout(combined)

        #  logits 값으로 전달
        logits = self.fc(combined).squeeze(-1)

        return logits
```

### 수정 후
```python

        super().__init__()
        # 문제 번호를 컴퓨터를 위해 번역한다 nn.Embedding 사용
        self.embedding = nn.Embedding(num_questions, embeding_num,padding_idx=0)
        # 과거 기록을 읽는 기억 장치(문제 푼 순서를 따라가며 학습 상태를 계산), 학습 가능한 내부 벡터 생성한다.
        self.lstm = nn.LSTM(embeding_num + num_concepts + 1, hidden_num,batch_first=True)

        self. dropout = nn.Dropout(p = 0.2)
        # 점수 계산(분류기 생성한다.)
        self.fc = nn.Linear(hidden_num + embeding_num + num_concepts,1)
        forward() 내부
        # 과거 상태 + 예측할 문제
        combined = torch.cat(
            [history_state, query_vector],
            dim=-1
        )

        # dropout 추가하기(입력 값으로 combined 사용)
        # 과적합을 막기 위한 수단
        dropout = self.dropout(combined)
        
        #  logits 값으로 전달
        logits = self.fc(combined).squeeze(-1)

        return logits
```
이력 상태와 이번 문제의 임베딩 및 개념 정보가 결합된 데이터를 dropout의 입력값으로 넣어 과적합 방지를 하였습니다.
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

### 빈 이력 테스트

추가적인 테스트를 진행해야 합니다.
## 다음 작업

- 서로 다른 배치와 데이터 분할에서도 Embedding ID 범위 확인
- train과 valid loss 값 차이 줄이기, test를 통한 검증 진행
- 실행 환경과 전체 커밋 SHA 기록
- 이슈 121의 담당자와 LSTM 구조 및 실험 결과 공유

현재 구현 범위는 **train과 validation을 통한 학습과 검증**이며, test 데이터를 통한 검증이 필요합니다.