# wamangdoo 입력 확인 기록

- 담당 모델: Transformer
- 담당 이슈: https://github.com/WaterMinCho/programming-study/issues/120
- 개인 모델 저장소 주소: https://github.com/wamangdoo/learning-transformer
- README 고정 주소: https://github.com/wamangdoo/learning-transformer/blob/f601a2541c141995a0f29ff23cbf6b6e51876d41/README.md

## 실제로 실행한 명령을 적습니다

```powershell
python -m learning_server.starter --synthetic --out ..\learning-demo-v3
python -m learning_server.input_example --dataset ..\learning-demo-v3 --track python --batch-size 4 --length 4
```

## 출력에서 이해한 내용이나 오류를 적습니다
첫 번째 명령 실행 시 "..\learning-demo-v3 폴더가 이미 존재하여 오류: [WinError 183] 파일이 이미 있으므로 만들 수 없습니다" 가 출력되었고, 가이드에 따라 기존 폴더를 덮어쓰지 않고 두 번째 명령을 실행하였습니다.
배치 4개, 각 과거 기록 4칸을 꺼낸 결과값이 출력되었습니다.
4개 샘플의 lengths: [0, 1, 2, 3], 정답표는 targets: [1, 1, 0, 1]로 출력되었습니다.
3번 샘플의 results는 [1, 1, 0, 0]으로 0이 두 번 나옵니다.
함께 출력된 mask는 [true, true, true, false]이므로, 세 번째 0은 실제 오답이고 네 번째 0은 기록이 없는 빈 자리(패딩)임을 구분했습니다.

## 입력과 이번 정답을 어떻게 나눴는지 설명합니다
example["inputs"]에는 모델에 들어가는 과거 풀이 이력(questions, concepts, results, courses, mask, lengths)과 이번에 예측할 문제 정보(query_question, query_concepts, query_course)만 들어 있으며, 이번 문제의 정오답은 포함되지 않습니다.
이번 문제의 정오답은 example["targets"] ([1, 1, 0, 1])로 입력과 완전히 분리되어 있어, 모델이 정답을 미리 보지 않고 예측한 뒤 손실을 계산할 수 있습니다.

## 막힌 부분과 질문을 적습니다

'모든 과거 자리가 비어도 숫자가 유효해야 한다'는 조건을 바탕으로 Transformer 입력 구조를 어떤 식으로 잡을지, 어떤 방식으로 사용할 지 고민중입니다.
