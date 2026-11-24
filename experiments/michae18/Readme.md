# michae18 모델 실습

## 프로젝트 개요
본 프로젝트는 학습자의 과거 문제 풀이 이력을 이용하여 다음 문제의 정답 확률을 예측하는 SmallLSTM 기반 이진 분류 모델을 구현하고 평가하는 것을 목표로 한다.

학습 및 평가 과정에서는 다음 사항을 검증한다.

- LSTM을 이용한 과거 풀이 이력 인코딩
- 현재 문제 정보를 결합한 정답 확률 예측
- Early Stopping을 이용한 과적합 방지
- model.train()과 model.eval()의 동작 차이
- optimizer.step() 전후 가중치 변화
- Learning Server의 기준선 모델과 성능 비교

## 담당 모델

- GitHub ID: `michae18`
- 담당 모델: 기본 LSTM (`SmallLSTM`)
- 작업 브랜치: `michae18-train-lstm`
- 담당 미션: 기본 LSTM으로 다음 문제 예측하기
- 작업 PR: https://github.com/WaterMinCho/programming-study/pull/337
- 모델 구현 파일: `experiments/michae18/model.py`
- 학습 실행 파일: `experiments/michae18/train.py`
- 입력 확인 파일: `experiments/michae18/input_check.py`
- 테스트 파일: `experiments/michae18/test_data_model.py`

### 현재 진행 상황

기존 합성자료 기반 LSTM 순전파 및 입력 처리 검증을 완료한 후, 실제 기록 기반 F8 데이터로 학습과 Validation 평가를 진행했습니다.

과적합 완화를 위해 Dropout(p=0.2), Adam Optimizer의 Weight Decay(1e-3), Validation Loss 기반 Early Stopping(patience=20)을 적용했습니다.

이번 실험에서는 다음 작업을 추가로 완료했습니다.

- `SmallLSTM` init 함수에 기존 인자 할당 방법과 Modelconfig 전달 방식 호환 가능하도록 보완하였습니다.
    - 호출 가능 방법들 : `SmallLSTM(10, 4, 32, 64)` , `SmallLSTM(10, 4, config=Modelconfig())`
- `optimizer.step()` 전후 가중치 변화를 비교하여 파라미터 업데이트 확인
- `model.train()`과 `model.eval()`의 출력 차이 확인
- Validation 예측 확률 및 `event_id`를 이용한 CSV 생성
- CSV 데이터 개수, 중복, 결측값 및 확률 범위 검증
- Learning Server를 이용한 Validation 평가
- Log Loss, Brier Score, ROC-AUC, Accuracy 및 기준선 모델 비교

**현재 단계:** 실제 기록 기반 데이터 학습, Validation 평가 및 기준선 비교 완료. 최종 Test 평가와 추가 하이퍼파라미터 실험은 미완료입니다.

## 실행 조건

| 항목 | 사용 값 |
|---|---|
| 운영체제 | Windows |
| Python | 3.13.5 |
| 프로젝트 경로 | `C:\Users\user\Documents\model_study\programming-study` |
| 작업 브랜치 | `michae18-train-lstm` |
| 실제 자료 경로 | `C:\Users\user\Documents\model_study\study-data\common-input-f8-20261118\recorded\` |
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
| hidden_size = 16, 임베딩 차원 = 16, 파라미터 수 | Embedding + LSTM + Dropout + Linear = 19,884


## 실행한 명령과 결과

모든 명령은 `programming-study` 저장소 루트에서 실행합니다.

### 1. 데이터 준비
'SEED 값 : 42' 로 고정
```bash
python -m zipfile -e ZIP파일경로 ../study-data/common-input-f8-20261118
```

- 데이터 경로: `../study-data/common-input-f8-20261118/recorded/`
- 데이터 유형: 실제 데이터
- Track: `ai`
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

입력 데이터의 Train(953개), Validation(299개), Test(260개) 샘플 수와 각 입력 Tensor의 Shape, Target Shape 및 Vocabulary 크기를 확인했습니다.

과거 풀이 이력의 최대 길이는 32이며, 실제 Tensor의 개별 값이나 전체 데이터 내용은 출력하지 않았습니다.

### 3. LSTM 학습 및 검증

```bash
python -m experiments.michae18.train
```

학습 로그:

epoch: 0 | train_loss: 0.6851 | val_loss: 0.6797 
                | train_acc: 0.5908 | val_acc: 0.6087 

epoch: 100 | train_loss: 0.2779 | val_loss: 0.3676 
                | train_acc: 0.9224 | val_acc: 0.8763 

epoch: 200 | train_loss: 0.2489 | val_loss: 0.3477 
                | train_acc: 0.9234 | val_acc: 0.8763 

epoch: 300 | train_loss: 0.2290 | val_loss: 0.3057 
                | train_acc: 0.9244 | val_acc: 0.8796 

early stopping at epoch 368


마지막 Epoch 기록:
```text
{
    'epoch': 368, 
    'train_loss': 0.20542867481708527, 
    'train_acc': 0.929695725440979, 
    'val_loss': 0.2964141070842743, 
    'val_acc': 0.8795986771583557
}
```

최적 epoch 선택 기록
```text
    Best Epoch : 348
    Best valid loss : 0.2950547933578491
    예측 확률 shape: (299,)
```

최대 학습 Epoch는 500으로 설정했으나, Validation Loss가 20회 연속 개선되지 않아 368 Epoch에서 학습을 종료했습니다.

최적 모델은 Validation Loss가 가장 낮았던 348 Epoch의 가중치를 복원하여 사용했습니다.

마지막 Epoch의 Validation Loss는 0.2964였으며, 최적 모델의 Validation Loss는 0.2951이었습니다.

따라서 최종 예측과 Learning Server 평가에는 마지막 Epoch의 가중치가 아닌 복원된 최적 가중치를 사용했습니다.

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
- 위 숫자는 실행 당시의 결과이며, seed 값에 따라 값이 달라질 수 있습니다.

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
```python
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
        logits = self.fc(dropout).squeeze(-1)

        return logits
```
이력 상태와 이번 문제의 임베딩 및 개념 정보가 결합된 데이터를 dropout의 입력값으로 넣어 과적합 방지 하였으며, dropout이 fc에 넘어가게 변경 완료
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

## 추가한 것
### 상수 모듈 생성
constants.py에 상수들을 모듈하였으며, 하이퍼파라미터들은 dataclass로 만들었습니다.
해당 모듈들은 input_check, model, train에서 볼 수 있습니다.

### Train/Eval 및 Optimizer 검증
1. model.train()과 model.eval() 비교

실험 목적

동일한 모델과 Validation 입력을 사용하여 학습 모드와 평가 모드의 출력 차이를 확인했습니다.

실험 방법

1. 학습 완료 후 최적 모델 가중치를 복원했습니다.

2. 동일한 Validation 데이터를 입력했습니다.

3. model.train() 상태에서 Logit을 계산했습니다.

4. model.eval() 상태에서 Logit을 계산했습니다.

5. 두 출력의 절댓값 차이를 비교했습니다.

두 모드 모두 torch.no_grad()를 사용하여 기울기 계산을 비활성화했습니다.

실험 결과
``` text
=== Train vs Eval ===

Train:
tensor([0.5688, 1.6493, 2.1892, 1.8791, 1.7923])

Eval:
tensor([1.2004, 1.9679, 1.9291, 1.7687, 1.6732])

Max Difference: 1.1795722246170044
Mean Difference: 0.26205509901046753
```

결과 분석

현재 모델은 Dropout(p=0.2)을 사용합니다.

model.train()에서는 Dropout이 활성화되며, model.eval()에서는 비활성화됩니다.

이번 실험에서는 동일한 입력에 대해 Train/Eval 출력 차이가 발생하는 것을 확인했습니다.

torch.no_grad()는 기울기 계산을 비활성화하는 기능이며, Dropout의 활성화 여부와는 별개라는 점을 확인했습니다.

따라서 Validation 예측 확률을 생성할 때는 model.eval()을 사용하도록 구현했습니다.

2. optimizer.step() 전후 가중치 비교

실험 목적

Optimizer가 모델 파라미터를 실제로 업데이트하는지 확인했습니다.

실험 방법

첫 번째 Epoch에서 model.fc.weight를 대상으로 optimizer.step() 실행 전후 가중치를 비교했습니다.
```python

weight_before = model.fc.weight.detach().clone()

optimizer.step()

weight_after = model.fc.weight.detach().clone()

weight_change = (
    weight_after - weight_before
).abs()
```

detach()를 사용해 Autograd 계산 그래프에서 분리하고, clone()을 사용해 업데이트 전 가중치를 별도 메모리에 복사했습니다.

실험 결과

```text
=== Optimizer Step Comparison ===

Before:
tensor([ 0.0017, -0.0577, 0.0121, -0.0067, 0.0557])

After:
tensor([ 0.0027, -0.0587, 0.0131, -0.0057, 0.0567])

Max Weight Change: 0.0010000001639127731
Mean Weight Change: 0.000999827403575182
```

결과 분석

첫 번째 Epoch에서 optimizer.step() 실행 후 fc.weight가 변경되는 것을 확인했습니다.

최대 가중치 변화량은 약 0.001로, 설정한 학습률과 유사했습니다.

이는 첫 번째 Adam 업데이트에서 관측한 결과이며, 이후 모든 Epoch에서 동일한 변화량이 발생한다는 의미는 아닙니다.


### evaluate.py에 구현한 것
#### Validation 예측 CSV 생성 및 검증

1. 예측 파일 생성

학습 완료 후 최적 모델을 이용해 Validation 데이터의 정답 확률을 계산했습니다.

모델이 출력한 Logit에 Sigmoid를 적용하여 0~1 범위의 예측 확률로 변환했습니다.

```python
model.eval()

with torch.no_grad():
    logits = model(inputs)
    probabilities = torch.sigmoid(logits)
```
생성된 예측 확률과 원본 event_id를 연결하여 CSV 파일로 저장했습니다.

CSV 형식:

```text
event_id,probability,model_version
```

2. CSV 검증 결과

```text
예측 파일 저장 완료: ../preds/lstm-validation.csv
예측 행 수: 299

CSV 검증 통과
예측 행 수: 299
모델 버전: small-lstm-v1

예측 확률 shape: (299,)
Validation 정답 개수: 299
예측 확률 개수: 299
event_id 개수: 299
```

검증 항목:

- CSV 열 이름 및 순서 확인
- event_id 중복 여부 확인
- Validation 데이터와 event_id 순서 일치 확인
- 예측 확률 개수와 정답 개수 일치 확인
- 결측값 및 NaN/Inf 검사
- 예측 확률의 0~1 범위 확인
- 단일 model_version 사용 여부 확인

검증 결과, Validation 299행에 대해 예측 확률과 event_id가 정상적으로 대응하는 것을 확인했습니다.

예측 CSV는 Git 저장소 외부의 ../preds/ 폴더에 저장했습니다.

#### Learning Server Validation 평가

1. 평가 방법

Learning Server의 로컬 평가기를 사용하여 SmallLSTM과 기준선 모델들의 성능을 비교했습니다.

평가 데이터는 학습에 사용한 실제 기록 기반 F8 자료의 Validation 구간입니다.

평가 명령 예시:

```python
python -m learning_server.score --dataset ../study-data/common-input-f8-20261118/recorded --track ai --split validation --predictions ../preds/lstm-validation.csv
```
2. 평가 데이터
| 항목 | 결과 |
|---|---|
| Track | "ai" |
| Split | validation |
| 전체 행 수 | 299 |
| 오답 행 수 | 37 |
| 학습자 가명 수 | 3 |
| 끼운 변형 행 수 | 0 |
| Features Version | 8 |
| 모델 버전 | small-lstm-v1 |

3. 모델 성능 비교
| 모델 | Log Loss ↓ | Brier ↓ | ROC-AUC ↑ | Accuracy ↑ |
|---|---|---|---|---|
| SmallLSTM | 0.2951 | 0.0867 | 0.8293 | 0.8796 | 
| majority |    -   | 0.1237 |    -   | 0.8763 |
| overall-mean | 0.3871 | 0.1106 | 0.5000 | 0.8763 |
| per-question | 0.4819 | 0.1257 | 0.4849 | 0.8763 | 
| per-concept | 0.4751 | 0.1213 | 0.4745 | 0.8763 | 
| per-participant | 0.3632 | 0.1035 | 0.8014 | 0.8763 | 
| past-concept-ratio-v1 | 0.3174 | 0.0936 | 0.8874 | 0.8796 | 

4. 성능 분석

Log Loss

SmallLSTM은 0.2951로 비교한 기준선 중 가장 낮은 Log Loss를 기록했습니다.

overall-mean의 0.3871보다 약 23.8% 낮았습니다.

Brier Score

SmallLSTM은 0.0867로 비교한 기준선 중 가장 낮은 Brier Score를 기록했습니다.

overall-mean의 0.1106보다 약 21.6% 낮았습니다.

ROC-AUC

SmallLSTM의 ROC-AUC는 0.8293으로, per-participant의 0.8014보다 높았습니다.

반면 past-concept-ratio-v1의 0.8874보다는 낮았습니다.

따라서 이번 Validation 데이터에서 정답과 오답의 순위 구분 능력은 과거 개념 정답 비율 기준선이 더 높게 나타났습니다.

Accuracy

SmallLSTM의 Accuracy는 0.8796으로, majority의 0.8763보다 약 0.33%p 높았습니다.

past-concept-ratio-v1과는 동일한 Accuracy를 기록했습니다.

5. 평가 결과의 한계

이번 Validation 데이터는 오답 37행, 학습자 가명 3개로 구성되어 있습니다.

Learning Server는 오답이 50행 미만이거나 학습자가 5명 미만인 구간에서는 모델 비교 결과를 신중하게 해석하도록 경고합니다.

따라서 이번 결과만으로 SmallLSTM이 기준선보다 일반화 성능이 우수하다고 결론 내리기는 어렵습니다.

이번 실험은 모델 학습, 예측 파일 생성, CSV 검증 및 로컬 평가 파이프라인의 정상 동작을 확인한 결과로 활용합니다.

### SmallLSTM 생성자에서 기존 위치 인자 방식과 Modelconfig 전달 방식 호환성 확인

#### 모델 생성하기

```python
python -c "from experiments.kimjs85529_a11y.model import TimeGapLSTM; TimeGapLSTM(10, 4)" 
```

#### 테스트 실행 (kimjs85529_a11y,michae18)

```python
python -m experiments.kimjs85529_a11y.test_data_model 
```

```text
사용 장치: cpu                      
통과: 기본 LSTM과 초기 출력 일치
통과: 출력 형상·확률·빈 이력·패딩
통과: 시간 미확인/0초 구분
통과: gap_log의 출력 반영
통과: 역전파 및 가중치 갱신
통과: 실제 데이터 전체 순전파 953 건
통과: 모델 저장·복원 후 출력 일치
```

```python
python -m experiments.michae18.test_data_model 
```

```text
PASS: 일부 빈 이력 처리             
PASS: 전체 빈 이력 처리
PASS: 패딩 변경에 대한 예측 불변성
```

#### 인자 추가하여 테스트 진행

```python
python -c "from experiments.kimjs85529_a11y.model import TimeGapLSTM; TimeGapLSTM(10, 4, embeding_num=16, hidden_num = 32)" 
```

```python
python -m experiments.kimjs85529_a11y.test_data_model     
```

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

```python
python -m experiments.michae18.test_data_model   
```

```text
PASS: 일부 빈 이력 처리
PASS: 전체 빈 이력 처리
PASS: 패딩 변경에 대한 예측 불변성
```

SmallLSTM 생성자에서 기존 위치 인자 방식과 Modelconfig 전달 방식 호환성 확인하였습니다.

## 막힌 부분과 해결 내용

1. 기존 예측 파일의 event_id 불일치

```python
python -m learning_server.score --dataset ../learning-demo-f8 --track ai --predictions ../preds/lstm-validation.csv
```
#### 발생 오류

오류: 예측 파일에 빠진 event_id 가 2개 있습니다.

기존 lstm-validation.csv를 이용한 채점에서 오류가 발생했습니다.

#### 결과

lstm-validation.csv의 299개 event_id와 예측 확률이 정상적으로 대응했으며, Learning Server Score 실행에 성공했습니다.

 기존 CSV에서 2개 ID가 누락된 정확한 원인은 확인하지 못했습니다.

#### lstm-validation.csv 생성 시간

`Get-Item ../preds/lstm-validation.csv | Select-Object Name, CreationTime, LastWriteTime`

```text
Name                CreationTime            LastWriteTime          
----                ------------            -------------          
lstm-validation.csv 2026-11-24 오전 3:36:27 2026-11-24 오전 3:36:27
```

#### 실행 커밋 SHA
`git rev-parse HEAD`

```git
git rev-parse HEAD
SHA : 5be591196bff917bdb4c3c34786d5b01da3b3e74 
```

#### train.py의 커밋 현황 파악 
`git log --format="%H | %ai | %s" -- experiments/michae18/train.py`

```git
git log --format="%H | %ai | %s" -- experiments/michae18/train.py
5be591196bff917bdb4c3c34786d5b01da3b3e74 | 2026-11-24 04:35:22 +0900 | feat(model): SmallLSTM 실 데이터 학습 및 Validation 성능 평가 완료 (#337)
```

## 다음 작업

- 추가적인 개선 과제: train과 valid loss 값 차이 줄이기, test를 통한 검증 진행
- 실행 환경과 전체 커밋 SHA 기록
- 이슈 121의 담당자와 LSTM 구조 및 실험 결과 공유

현재 구현 범위는 **실제 기록 기반 데이터 학습, Validation 평가, 기준선 비교 및 학습 동작 검증**까지입니다.
Test 데이터는 최종 모델 설정을 확정한 후 평가할 예정입니다.