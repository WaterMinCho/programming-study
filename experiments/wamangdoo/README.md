# wamangdoo - Transformer 실험 기록

- 담당 모델: Transformer
- 담당 이슈: https://github.com/WaterMinCho/programming-study/issues/120
- 이전 입력 확인 PR: https://github.com/WaterMinCho/programming-study/pull/189
- 모델·학습 구현 PR: https://github.com/WaterMinCho/programming-study/pull/320 (머지 완료)
- 개인 모델 저장소 주소: https://github.com/wamangdoo/learning-transformer
- README 고정 주소: https://github.com/wamangdoo/learning-transformer/blob/f601a2541c141995a0f29ff23cbf6b6e51876d41/README.md
- 현재 단계: 경량 Transformer(`model.py`), 학습 전 예측(`run.py`), 모델 단위 테스트(`test_model.py`), 합성 자료 기반 학습·검증 및 저장·불러오기(`train.py`) 구현 및 실행 확인 완료 (새 실행 저장·불러오기 분리, 실제 자료 학습·성능 비교·`learning_server.score` 채점은 미실행)

## 모델 구현, 예측 확인 및 학습·저장·불러오기 (`model.py` / `run.py` / `test_model.py` / `train.py`)

### 1. 파일 구성 및 직접 구현한 부분
- **직접 구현한 코드 (`experiments/wamangdoo/`)**
  - `model.py`: `SmallTransformer` 모델 본체 (과거 풀이 인코딩 + 이번 문제 결합 후 `logits` 반환)
  - `run.py`: 합성 자료(`learning-demo-f8`)에서 핵심 6개 입력을 골라 `set_seed(42)`와 `get_device()`(`cuda` / `mps` / `cpu`) 적용 후 배치 단위로 `.to(device)` 이동해 학습 전 예측 확률 출력
  - `test_model.py`: 일부/전원 빈 이력, 평가 모드 패딩 변경 불변성, 과거 풀이 순서(위치 정보) 반영 검증 (`unittest`)
  - `train.py`: 합성 자료(`learning-demo-f8`)의 `train` / `validation` 구간으로 소량 과적합 확인(`evaluate_one_epoch` 재측정 포함), 학습·검증 루프(`BCEWithLogitsLoss`, `Adam`), CPU·평가 모드 저장·불러오기(`torch.save` / `torch.load`) 최대 오차 확인
- **참고·사용한 공통 코드**
  - 공통 데이터 로딩 및 배치 생성: `learning_server.input_example` (`load`, `batch`)
  - 비교 기준 입력 차원(`embed_num=16`, `hidden_num=16`) 및 핵심 입력 항목 기준: `experiments/michae18/model.py` (`SmallLSTM`)

### 2. 실행 조건 및 환경
| 항목                         | 실제 사용한 값                                                                                                                                                                                |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 자료 묶음 및 구분                 | `..\learning-demo-f8` (합성 자료, `synthetic: true`, `features_version: 8`, `question_min_count: null`, 끼운 변형 행 없음)                                                                         |
| 묶음 `manifest.json` SHA-256 | `b00f5cfd0a1b35f123c4707e813210eddbb9bd286dcf15a7f31608e1bc572d31`                                                                                                                      |
| 과목 / 분할 / 건수 / 이력 길이       | `python` / `train` 8건 (`run.py`, `train.py`), `validation` 2건 (`train.py`) / `length=32`                                                                                                |
| 시드 / 장치 / 모드               | `set_seed(42)` (`random`/`numpy`/`torch`/`cuda`/`mps`), `get_device()`, 학습 `model.train()` / 검증·예측 `model.eval()` + `torch.no_grad()`                                                   |
| 모델 설정 및 파라미터 수             | `embed_num=16`, `hidden_num=16`, `nhead=4`, `num_layers=2`, `dim_feedforward=32`, `max_len=128`, `dropout=0.1` / 총 `6,916`개 (`learning-demo-f8` 기준 `num_questions=3`, `num_concepts=3`) |
| 학습 설정 (`train.py`)         | `nn.BCEWithLogitsLoss()`, `Adam` (1단계 과적합 확인 `lr=3e-3` 200 epoch / 2단계 학습·검증 `lr=1e-3` 20 epoch), `batch_size=4`                                                                        |
| Python / PyTorch 버전        | 로컬: `Python 3.13.15` / `pytorch: 2.15.0+cu132`<br>Colab: `Python 3.13.16` / `torch.__version__: 2.14.1+cu130`                                                                           |
| OS와 장비                     | 로컬: `Windows` / 학습·순전파 `GTX 1660 Ti` (`cuda`), 저장·불러오기 비교 `CPU`<br>Colab: `Linux` / `Tesla T4` (`cuda`)                                                                                 |

> `nn.TransformerEncoder`의 `enable_nested_tensor=False` 옵션은 PyTorch 버전에 따라 동작이나 패딩 오차 결과가 달라질 수 있어 실제 `torch.__version__` 출력값을 함께 기록했습니다.

### 3. 입력을 9개에서 6개로 변경한 이유
- `#189` README에서는 `courses`, `query_course`, `lengths`까지 포함한 9개 입력을 계획했으나, 이번 구현에서는 아래 두 가지 이유로 **6개(`questions`, `concepts`, `results`, `mask`, `query_question`, `query_concepts`)**만 사용했습니다.
  1. **`courses`, `query_course` 제외**: `michae18`님의 LSTM 모델과 동일한 정보 조건에서 모델 구조 차이(LSTM vs Transformer)만 비교하기 위해 과정 정보 2개를 기본 실험에서 뺐습니다.
  2. **`lengths` 제외**: LSTM은 `pack_padded_sequence`에 `lengths`가 필요하지만, Transformer는 `mask`(`True`/`False`)만으로 빈 이력 판별·패딩 가림·실제 개수 평균을 모두 처리할 수 있어 `lengths`를 제외했습니다.
- 이번 문제의 실제 정오답(`targets`)은 데이터 누수 방지를 위해 모델 입력에 포함하지 않았습니다.

### 4. 하이퍼파라미터 및 구조 선택 이유 (`model.py`)
- `embed_num=16`, `hidden_num=16`: `michae18`님 LSTM과 차원을 동일하게 맞췄습니다.
- `nhead=4`: `hidden_num=16`을 균등하게 나눌 수 있는 약수로 선택했습니다 (`16 ÷ 4 = 4`).
- `dim_feedforward=32` (`hidden_num * 2`), `num_layers=2`, `dropout=0.1`: 소규모 데이터에서 파라미터가 많아져 과적합되는 것을 줄이기 위해 기본 4배 대신 2배로 줄였습니다.
- `max_len=128`: 공통 입력의 최대 이력 보관 개수(`128`)에 맞췄습니다.
- `forward()` 반환값: 추후 학습 단계에서 `nn.BCEWithLogitsLoss`를 바로 연결할 수 있도록 시그모이드 전 로짓(`logits`)을 반환하고, 확률 확인(`run.py`, `test_model.py`, `predict_probabilities`)에서만 `torch.sigmoid()`를 적용했습니다.
- **입력 장치 이동 분리**: `encode_history()`와 `forward()` 안에서 매 호출마다 `torch.as_tensor(..., device=device)`를 실행하지 않고, 호출부(`run.py` 및 `train.py`)에서 모델과 배치를 한 번에 `.to(device)`로 옮기도록 분리해 CPU↔GPU(CUDA/MPS) 반복 복사 병목을 방지했습니다.

### 5. 다른 사람이 실행할 방법과 실제 출력

#### 학습 전 예측 및 모델 단위 테스트 (`run.py` / `test_model.py`)
> 아래 출력은 **학습 전 초기 가중치 상태**의 순전파·구조 검증 결과이며, 학습된 모델 성능이 아닙니다.

```powershell
python -m learning_server.starter --synthetic --out ..\learning-demo-f8
python -m experiments.wamangdoo.run
```
```text
예측 확률: [0.306706, 0.169384, 0.217735, 0.263737]
예측 확률: [0.306706, 0.169384, 0.205219, 0.260501]
```
- 배치 1(`rows[:4]`)과 배치 2(`rows[4:8]`) 모두 `NaN` 없이 `0 ~ 1` 사이 확률 4개씩 출력됨을 확인했습니다.

```powershell
python -m unittest experiments/wamangdoo/test_model.py -v
```
```text
test_all_empty_history (experiments.wamangdoo.test_model.TestSmallTransformer.test_all_empty_history) ... ok
test_mixed_empty_history (experiments.wamangdoo.test_model.TestSmallTransformer.test_mixed_empty_history) ... ok
test_padding_does_not_change_prediction (experiments.wamangdoo.test_model.TestSmallTransformer.test_padding_does_not_change_prediction) ... ok
test_position_order_changes_prediction (experiments.wamangdoo.test_model.TestSmallTransformer.test_position_order_changes_prediction) ... ok

----------------------------------------------------------------------
Ran 4 tests in 1.425s

OK

[2] 모든 과거 자리가 비어도 유효한 확률이 나오는지 확인: [0.46056756377220154, 0.509726345539093, 0.5697569251060486, 0.402774840593338]

[1] 합성 예제 4개에서 확률 4개 확인: [0.46056756377220154, 0.5378527641296387, 0.675672173500061, 0.5214458107948303]

[3] 평가 모드에서 패딩 변경 전: [0.46056756377220154, 0.5378527641296387, 0.675672173500061, 0.5214458107948303]
    평가 모드에서 패딩 변경 후: [0.46056756377220154, 0.5378527641296387, 0.675672173500061, 0.5214458107948303]

[4] 순서 A (1번O -> 2번X): 0.675672173500061
    순서 B (2번X -> 1번O): 0.6690245270729065
```
- `num_questions=5`(허용 번호 `0~4`) 축소 조건에서 4개 테스트 모두 통과했습니다.
  - `[1]` 일부 빈 이력 포함 4명 확률: `[0.460568, 0.537853, 0.675672, 0.521446]`
  - `[2]` 전원 빈 이력(`mask` 전부 `False`) 4명 확률: `[0.460568, 0.509726, 0.569757, 0.402775]` (`NaN` 없음)
  - `[3]` 평가 모드 패딩 변경 전/후 확률: 두 경우 일치 (오차 `<= 1e-6`)
  - `[4]` 위치 정보(과거 풀이 순서) 변경 결과: 순서 A(`1번O -> 2번X`) `0.675672` vs 순서 B(`2번X -> 1번O`) `0.669025` (순서 반영 확인)

#### 학습·검증 및 저장·불러오기 (`train.py`)
> 아래 출력은 **합성 자료(`learning-demo-f8`, `train` 8건 / `validation` 2건)**에서 학습·검증 루프와 저장·불러오기가 정상 동작하는지 확인한 결과이며, 실제 학습자 성능 지표가 아닙니다.

```powershell
python -m experiments.wamangdoo.train
```
```text
[1] 소량(8건) 과적합 확인: epoch 1 손실 1.024027 -> epoch 200 학습 손실 0.210206
    학습 종료 후 평가 모드(eval) 손실: 0.191674

[2] 학습·검증 시작 (device=cuda, train=8건, validation=2건)
  epoch  1 | train_loss: 1.074712 | val_loss: 0.799450
  epoch  5 | train_loss: 0.782603 | val_loss: 0.693849
  epoch 10 | train_loss: 0.713906 | val_loss: 0.728333
  epoch 15 | train_loss: 0.704884 | val_loss: 0.765250
  epoch 20 | train_loss: 0.678125 | val_loss: 0.779956

[3] 저장·불러오기 확인 (CPU, eval 모드)
  저장 전 예측 확률: [0.697924, 0.698886]
  불러온 뒤 예측 확률: [0.697924, 0.698886]
  최대 절대 차이: 0.00000000 (기준 <= 0.000001)
```

- **학습·검증 구현 선택 이유 및 에포크 루프 구조**:
  - `train.py`의 `main()`은 두 개의 독립된 에포크 루프로 구성되어 있습니다. 1단계에서는 임시 모델(`check_model`)로 소량(최대 32건, 여기서는 8건)을 `lr=3e-3`으로 200 epoch 학습한 뒤 `evaluate_one_epoch`로 평가 모드 손실을 재측정해 학습 코드가 정상 수렴하는지 먼저 점검합니다. 그다음 2단계에서는 `set_seed(42)`로 난수를 다시 고정하고 완전히 새로운 `model`을 생성해 `lr=1e-3`으로 20 epoch 동안 매 바퀴 `train_one_epoch` → `evaluate_one_epoch`을 번갈아 실행합니다.
  - `SmallTransformer`가 시그모이드 전 `logits`를 반환하므로 `nn.BCEWithLogitsLoss()`가 sigmoid와 손실 계산을 한 번에 처리해 줍니다. 그래서 실제 확률이 필요한 `predict_probabilities`에서만 시그모이드를 사용했습니다.
  - 이번 정답표(`targets`)는 모델 입력(`inputs`)에 절대 넣지 않고 손실 계산에만 사용했으며, 과거 이력용 `mask`를 `targets`에 곱하지 않았습니다.
  - 학습(`train_one_epoch`) 때는 `model.train()`으로 가중치를 업데이트하고, 검증(`evaluate_one_epoch`) 때는 `model.eval()`과 `torch.no_grad()`를 써서 가중치가 바뀌지 않게 막았습니다. (빈 입력 방어 `if not rows: raise ValueError(...)` 포함)
  - `save_model`은 `model.state_dict()`와 모델 복원에 필요한 `num_questions`, `num_concepts`를 함께 저장하며, 저장소에 `.pt` 파일이 남지 않도록 Git 저장소 밖(`..\temp_small_transformer.pt`)에 임시 저장해 불러오기 확인 후 삭제했습니다.
- **출력 결과 해석 (관찰과 추정 구분)**:
  - `[1]` 소량 8건 과적합 확인: 기존 `lr=1e-2` 50 epoch에서 평가 모드 손실을 재측정했을 때는 `0.354550`으로 덜 수렴한 상태였습니다. 학습률과 에포크를 `lr=3e-3` 200 epoch로 조정한 뒤 `evaluate_one_epoch`로 Dropout을 끈 평가 모드 손실을 다시 재자 **`0.191674`**까지 내려왔습니다. `learning-demo-f8`의 `python-train.jsonl` 8건 중 2번째·6번째 행은 입력이 완전히 같고 정답(`target`)만 반대(`1` vs `0`)여서, 그 한 쌍을 `0.5`로 예측할 때의 이론 하한(`0.693 × 2 / 8 ≈ 0.173`) 근처까지 정상 수렴함을 확인했습니다.
  - `[2]` **관찰:** 20 epoch 동안 `train_loss`는 `1.074712 → 0.678125`로 감소했고, `val_loss`는 epoch 5(`0.693849`) 이후 `0.779956`으로 상승했습니다. **추정:** 마지막 `train_loss`(`0.678125`)는 모든 행을 `0.5`로 예측할 때의 손실(`ln 2 ≈ 0.693`)과 거의 같아서 아직 학습 자료 8건을 다 외웠다고 단정하기 어렵고, 검증 자료가 2건뿐인 소규모 합성 자료에서의 우연한 변동이나 초기 과적합 가능성으로 추정됩니다.
  - `[3]` 같은 CPU·평가 모드(`model.eval()`)에서 저장 전 확률 `[0.697924, 0.698886]`과 불러온 뒤 확률 `[0.697924, 0.698886]`이 완전히 일치하여 **최대 절대 차이 `0.00000000` (`<= 0.000001`)**을 확인했습니다.

### 6. 이번 작업을 하며 새로 알게 된 것들 (Transformer 기본 개념 정리)
- **Transformer의 기본 원리**:
  - LSTM은 과거 풀이를 앞에서부터 한 칸씩 순서대로 읽으며 기억을 넘기지만, Transformer는 **과거 풀이 전체를 한꺼번에 펼쳐 놓고 서로 관련 있는 문제끼리 Attention(관련도 가중치)으로 연결해, 단독 문제 벡터를 앞뒤 맥락이 담긴 벡터로 변환(Transform)**합니다.
  - 여러 헤드(`nhead=4`)로 서로 다른 관점에서 관계를 동시에 본 뒤 FeedForward 층에서 특징을 한 번 더 정리합니다.
- **Encoder만 사용한 이유**:
  - 과거 풀이 기록은 이미 끝난 데이터라 다음 문장을 순차 생성하는 Decoder가 필요 없고, 전체 이력을 요약한 뒤 이번 문제를 맞힐지 로짓 1개만 예측하면 되므로 `TransformerEncoder`만 사용했습니다.
- **Embedding과 `input_proj`**:
  - 문제 번호(`1, 2, 3...`)는 크고 작음을 비교하는 숫자가 아니라 단순 이름표이므로 `nn.Embedding`으로 특징 벡터(`16`차원)로 바꿔 줍니다. (`padding_idx=0`으로 빈 칸은 `0` 벡터 고정)
  - `[문제 임베딩 + 개념 + 정오답]`을 옆으로 이어 붙이면 차원이 `embed_num + num_concepts + 1`이 되는데, `position_embedding`과 `TransformerEncoder`는 고정 크기(`hidden_num=16`)만 받을 수 있어 `input_proj`(`nn.Linear`)로 크기를 맞춰 줍니다.
- **순서 정보(`position_embedding`)가 필요한 이유**:
  - Transformer는 모든 풀이를 동시에 보느라 원래 순서 개념이 없습니다. 그래서 `0번째, 1번째...` 위치 임베딩을 더해 *"예전에 푼 문제인지, 방금 푼 문제인지"*를 구분하게 해야 합니다.
- **빈 이력과 빈 자리(패딩) 처리 원리**:
  - 과거 기록이 없는 학생을 위해 `history_state`를 먼저 `0`으로 초기화하고, `has_history = mask.any(dim=1)`로 실제 풀이가 1개 이상 있는 학생만 Transformer에 통과시켜 전원 빈 이력일 때의 `NaN`을 막습니다.
  - 공통 입력의 `mask=True`('실제 자리')와 PyTorch `src_key_padding_mask=True`('가릴 자리')는 뜻이 반대이므로 `~valid_mask`로 반전해 넘깁니다.
  - `encode_history()`에는 이미 끝난 과거 풀이(`sequence_history`)만 들어가고 이번 문제(`query_question`)는 나중에 따로 합치므로, 시퀀스 내부에 미래 가림(causal mask)을 별도로 두지 않고 빈 자리 가림(`src_key_padding_mask`)만 사용했습니다.
  - Transformer 출력에서 그냥 평균을 내면 빈 칸 자리의 값까지 섞이므로, `valid_mask`를 `1.0`/`0.0`으로 바꿔 곱해 빈 칸을 `0`으로 지운 뒤 실제 푼 개수(`mask_float.sum(dim=1)`)로만 나누어 요약 벡터를 만듭니다.
- **PyTorch 기본 개념**:
  - `unsqueeze(-1)` / `squeeze(-1)`: `torch.cat`으로 옆에 이어 붙이기 위해 맨 뒤 차원을 1칸 늘리거나, 최종 출력 `[B, 1]`에서 1칸을 벗겨 `[B]`로 모양을 맞출 때 사용합니다.
  - `model.eval()` vs `torch.no_grad()`: `eval()`은 Dropout을 꺼서 같은 입력에 일정한 예측이 나오게 하고, `no_grad()`는 검증 시 불필요한 기울기(역전파) 계산을 꺼서 가중치가 바뀌지 않게 하고 메모리를 아낍니다.
  - `torch.as_tensor()`: 파이썬 리스트를 PyTorch 텐서로 바꾸되, 이미 같은 텐서면 불필요한 복사를 줄여 줍니다.
  - 학습 5단계(`zero_grad → forward → BCEWithLogitsLoss → backward → step`): PyTorch는 기울기를 기본 누적하므로 매 배치 시작에 `zero_grad()`로 비운 뒤, `backward()`로 기울기를 계산하고 `step()`으로 가중치를 갱신합니다.

### 7. 질문을 받고 바꾼 부분 (PR `#320` 피드백 반영 기록)
| 출처                       | 받은 질문 / 제안                                                                                      | 반영 내용 및 다시 확인한 결과                                                                                                                |
| ------------------------ | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| PR `#320` 리뷰 (`48bf48f`) | `[1]` 소량 과적합 손실(`0.362748`)은 학습 모드 기준이며 하한 `0.173`의 약 2배이므로 **평가 모드로 재측정**하고 필요 시 `lr`/epoch 조정 | `evaluate_one_epoch`로 재측정해 `0.354550`(덜 수렴)임을 확인한 뒤, `lr=3e-3` 200 epoch로 조정해 평가 모드 손실 **`0.191674`**(이론 하한 `0.173` 근처) 달성 및 기록. |
| PR `#320` 리뷰 (`48bf48f`) | `[2]` `train_loss 0.678`은 `ln 2 ≈ 0.693`과 비슷하므로 과적합 단정 대신 **관찰과 추정 구분**                         | 5절 해석에서 *"epoch 5 이후 `val_loss`가 상승했다"*는 관찰과 *"소규모 검증 2건의 변동이나 초기 과적합 가능성"*이라는 추정을 분리해 기재.                                       |
| 스터디 피드백 | `train.py` 36줄(`/ len(rows)`) 부분을 추후 수정해야 할 것 같다는 안내 | `rows`가 비어 있을 때 `0`으로 나누는 오류(`ZeroDivisionError`)가 날 수 있기 때문이라고 추정하여, `train_one_epoch`·`evaluate_one_epoch`·`predict_probabilities` 시작 부분에 빈 입력 방어(`if not rows: raise ValueError(...)`)를 추가했습니다. 의도하신 수정 방향이 이 부분이 맞는지 확인 부탁드립니다. |

### 8. 현재 미실행 항목 (다음 단계)
- 저장한 모델을 별도 새 실행(새 프로세스)에서 불러와 최대 오차 `<= 0.000001` 확인
- 학습·검증 가중치 갱신/고정 여부 자동 테스트 코드 추가
- 검증 구간 예측 파일(`event_id,probability,model_version`) 저장 및 `python -m learning_server.score` 채점
- 실제 자료 기반 학습·검증, 오류 사례 분석 및 같은 조건의 `michae18`님 LSTM 모델과 성능 비교
