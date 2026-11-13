# wamangdoo 입력 확인 기록

- 담당 모델: Transformer
- 담당 이슈: https://github.com/WaterMinCho/programming-study/issues/120
- 개인 모델 저장소 주소: https://github.com/wamangdoo/learning-transformer
- README 고정 주소: https://github.com/wamangdoo/learning-transformer/blob/f601a2541c141995a0f29ff23cbf6b6e51876d41/README.md
- 현재 단계: 공통 입력 구조 및 마스킹 조건 확인 (모델 코드 구현 및 학습은 미실행)

## 실제로 실행한 명령을 적습니다

```powershell
python -m learning_server.starter --synthetic --out ..\learning-demo-v5
python -m learning_server.input_example --dataset ..\learning-demo-v5 --track python --batch-size 4 --length 4
```

- 사용한 폴더의 `features_version: 5` (`..\learning-demo-v5\manifest.json` 확인; 최초 실행했던 `..\learning-demo-v3`는 `features_version: 3`이었으며, 브랜치를 최신 `main`과 병합한 뒤 새 폴더로 다시 확인함)
- 선택 이유: 실제 자료 전 입력 구조를 작게 눈으로 확인하기 위해 가상 자료(`--synthetic`)에서 배치 크기 `4`, 과거 이력 길이 `4`로 실행했습니다.

## 출력에서 이해한 내용이나 오류를 적습니다

- 처음 `..\learning-demo-v3` 생성 시 기존 폴더가 이미 존재해 `[WinError 183]`이 발생했으며, 가이드에 따라 덮어쓰지 않고 기존 폴더를 읽었습니다. 이후 최신 `features_version: 5` 확인을 위해 `..\learning-demo-v5`를 새로 생성해 확인했습니다.
- 배치 4개, 각 과거 기록 4칸(`history_length: 4`), 개념 수 3(`concept_width: 3`)으로 출력되었습니다.
- 4개 샘플의 실제 이력 길이는 `lengths: [0, 1, 2, 3]`, 이번 문제 정답표는 `targets: [1, 1, 0, 1]`로 출력되었습니다.
- 0부터 센 인덱스 3(네 번째 샘플, `lengths=3`)의 `results`는 `[1, 1, 0, 0]`으로 `0`이 두 번 나옵니다. 함께 출력된 `mask`가 `[true, true, true, false]`이므로, 세 번째 `0`(인덱스 2)은 실제 오답이고 네 번째 `0`(인덱스 3)은 기록이 없는 빈 자리(패딩)임을 구분했습니다.

## 입력과 이번 정답을 어떻게 나눴는지 설명합니다

`example["inputs"]`에는 총 15개 항목이 들어 있으며, 이번 문제의 정오답은 포함되지 않고 `example["targets"]` (`[1, 1, 0, 1]`)로 분리되어 있습니다. `inputs`의 15개 항목은 다음과 같이 구분해 사용할 예정입니다:

- 기본 Transformer 모델에 사용할 항목 (9개)
  - 과거 풀이 이력: `questions`, `concepts`, `results`, `courses`, `mask`, `lengths`
  - 이번에 예측할 문제 정보: `query_question`, `query_concepts`, `query_course`
- 기본 모델에서 제외할 항목 — 시간 간격 (2개)
  - `query_gap_seconds`, `query_gap_known` (LSTM과 비교를 위해 기본 모델에서 제외)
- 나중에 비교 실험할 항목 — 출제 난이도 (4개)
  - `difficulties`, `difficulty_known`, `query_difficulty`, `query_difficulty_known` (기본 모델 동작 후 넣고 뺀 결과를 비교)

## 막힌 부분과 질문을 적습니다

- 공통 입력의 `mask=True`는 '실제 풀이 자리'를 뜻하지만, PyTorch Transformer의 `src_key_padding_mask=True`는 '가릴(무시할) 자리'를 뜻해 반대이므로 값을 반전(`~mask`)해서 넘겨야 합니다.
- 인덱스 0(첫 번째 샘플, `lengths=0`)처럼 `mask`가 `[false, false, false, false]`이면 반전 시 네 칸 모두 `True`가 되어 모든 자리가 가려집니다. 이 상태로 Attention을 계산하면 참고할 자리가 없어 `NaN`이 발생할 수 있으므로, '모든 과거 자리가 비어도 숫자가 유효해야 한다'는 조건을 만족하기 위해 Query 정보(`query_question` 등)를 항상 보이는 자리로 두거나 `lengths == 0` 행을 별도 처리하는 방식 중 어떤 구조를 잡을지 고민 중입니다.
