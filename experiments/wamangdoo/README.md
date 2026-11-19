# wamangdoo - Transformer 실험 기록

- 담당 모델: Transformer
- 담당 이슈: https://github.com/WaterMinCho/programming-study/issues/120
- 이전 입력 확인 PR: https://github.com/WaterMinCho/programming-study/pull/189
- 개인 모델 저장소 주소: https://github.com/wamangdoo/learning-transformer
- README 고정 주소: https://github.com/wamangdoo/learning-transformer/blob/f601a2541c141995a0f29ff23cbf6b6e51876d41/README.md
- 현재 단계: 학습 전 경량 Transformer(`model.py`), 실행 스크립트(`run.py`), 단위 테스트(`test_model.py`) 구현 및 동작 확인 완료 (모델 학습·검증·저장은 미실행)

## 모델 구현 및 학습 전 예측 확인 (`model.py` / `run.py` / `test_model.py`)

### 1. 파일 구성
- `model.py`: `SmallTransformer` 모델 본체 (과거 풀이 인코딩 + 이번 문제 결합 후 `logits` 반환)
- `run.py`: 합성 자료(`learning-demo-f8`)에서 핵심 6개 입력만 골라 학습 전 예측 확률 출력
- `test_model.py`: 일부/전원 빈 이력, 평가 모드 패딩 변경 불변성, 과거 풀이 순서(위치 정보) 반영 검증 (`unittest`)

### 2. 실행 조건 및 환경
| 항목 | 실제 사용한 값                                                                                                       |
|---|---|
| 자료 묶음 | `..\learning-demo-f8` (합성 자료, `features_version: 8`)                                                           |
| 과목 / 분할 / 길이 | `python` / `train` / `length=32`                                                                               |
| 시드 / 모드 | `torch.manual_seed(42)`, `model.eval()`, `torch.no_grad()`                                                     |
| 모델 설정 | `embed_num=16`, `hidden_num=16`, `nhead=4`, `num_layers=2`, `dim_feedforward=32`, `max_len=128`, `dropout=0.1` |
| 실행 환경 | `Python 3.13.15` / `pytorch: 2.15.0+cu132` (Windows)                                                           |

> `nn.TransformerEncoder`의 `enable_nested_tensor=False` 옵션은 PyTorch 버전에 따라 동작이나 패딩 오차 결과가 달라질 수 있어 실행한 PyTorch 버전을 함께 기록했습니다.

### 3. 입력을 9개에서 6개로 변경한 이유
- `#189` README에서는 `courses`, `query_course`, `lengths`까지 포함한 9개 입력을 계획했으나, 이번 구현에서는 아래 두 가지 이유로 ** 6개(`questions`, `concepts`, `results`, `mask`, `query_question`, `query_concepts`)**만 사용했습니다.
  1. **`courses`, `query_course` 제외**: `michae18`님의 LSTM 모델과 동일한 정보 조건에서 모델 구조 차이(LSTM vs Transformer)만 비교하기 위해 과정 정보 2개를 기본 실험에서 뺐습니다.
  2. **`lengths` 제외**: LSTM은 `pack_padded_sequence`에 `lengths`가 필요하지만, Transformer는 `mask`(`True`/`False`)만으로 빈 이력 판별·패딩 가림·실제 개수 평균을 모두 처리할 수 있어 `lengths`를 제외했습니다.
- 이번 문제의 실제 정오답(`targets`)은 데이터 누수 방지를 위해 모델 입력에 포함하지 않았습니다.

### 4. 하이퍼파라미터 및 구조 선택 이유 (`model.py`)
- `embed_num=16`, `hidden_num=16`: `michae18`님 LSTM과 차원을 동일하게 맞췄습니다.
- `nhead=4`: `hidden_num=16`을 균등하게 나눌 수 있는 약수로 선택했습니다 (`16 ÷ 4 = 4`).
- `dim_feedforward=32` (`hidden_num * 2`), `num_layers=2`, `dropout=0.1`: 소규모 데이터에서 파라미터가 많아져 과적합되는 것을 줄이기 위해 기본 4배 대신 2배로 줄였습니다.
- `max_len=128`: 공통 입력의 최대 이력 보관 개수(`128`)에 맞췄습니다.
- `forward()` 반환값: 추후 학습 단계에서 `nn.BCEWithLogitsLoss`를 바로 연결할 수 있도록 시그모이드 전 로짓(`logits`)을 반환하고, 확률 확인(`run.py`, `test_model.py`)에서만 `torch.sigmoid()`를 적용했습니다.

### 5. 직접 실행한 명령과 실제 출력
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
Ran 4 tests in 1.039s

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
  - Transformer 출력에서 그냥 평균을 내면 빈 칸 자리의 값까지 섞이므로, `valid_mask`를 `1.0`/`0.0`으로 바꿔 곱해 빈 칸을 `0`으로 지운 뒤 실제 푼 개수(`mask_float.sum(dim=1)`)로만 나누어 요약 벡터를 만듭니다.
- **PyTorch 기본 개념**:
  - `unsqueeze(-1)` / `squeeze(-1)`: `torch.cat`으로 옆에 이어 붙이기 위해 맨 뒤 차원을 1칸 늘리거나, 최종 출력 `[B, 1]`에서 1칸을 벗겨 `[B]`로 모양을 맞출 때 사용합니다.
  - `model.eval()` vs `torch.no_grad()`: `eval()`은 Dropout을 꺼서 같은 입력에 일정한 예측이 나오게 하고, `no_grad()`는 추론 시 불필요한 기울기(역전파) 계산을 꺼서 메모리를 아낍니다.
  - `torch.as_tensor()`: 파이썬 리스트를 PyTorch 텐서로 바꾸되, 이미 같은 텐서면 불필요한 복사를 줄여 줍니다.

### 7. 현재 미실행 항목 (다음 단계)
- 모델 학습·검증 루프(`train.py`: `BCEWithLogitsLoss`, 역전파·가중치 갱신, 검증 구간 가중치 고정 확인)
- 모델 저장·불러오기(`torch.save` / `torch.load`, 새 실행에서 저장 전후 예측 차이 `<= 1e-6` 확인)
- 같은 조건의 `michae18`님 LSTM 모델과 성능 비교 및 `python -m learning_server.score` 채점
