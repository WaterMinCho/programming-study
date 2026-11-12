# wamangdoo 입력 확인 기록

- 담당 모델: Transformer (과거 풀이 사이의 관계 계산)
- 담당 이슈: https://github.com/WaterMinCho/programming-study/issues/120
- 개인 모델 저장소 주소: https://github.com/wamangdoo/learning-transformer
- README 고정 주소: https://github.com/wamangdoo/learning-transformer/blob/f601a2541c141995a0f29ff23cbf6b6e51876d41/README.md

## 실제로 실행한 명령을 적습니다

```powershell
python -m learning_server.starter --synthetic --out ..\learning-demo-v3
python -m learning_server.input_example --dataset ..\learning-demo-v3 --track python --batch-size 4 --length 4
```

## 출력에서 이해한 내용이나 오류를 적습니다
오류: [WinError 183] 파일이 이미 있으므로 만들 수 없습니다: '..\\learning-demo-v3'
{"batch": 4, "history_length": 4, "concept_width": 3, "example": {"inputs": {"questions": [[0, 0, 0, 0], [2, 0, 0, 0], [2, 2, 0, 0], [2, 2, 2, 0]], "concepts": [[[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]], [[0, 0, 1], [0, 0, 0], [0, 0, 0], [0, 0, 0]], [[0, 0, 1], [0, 0, 1], [0, 0, 0], [0, 0, 0]], [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 0]]], "results": [[0, 0, 0, 0], [1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 0, 0]], "mask": [[false, false, false, false], [true, false, false, false], [true, true, false, false], [true, true, true, false]], "lengths": [0, 1, 2, 3], "query_question": [2, 2, 2, 2], "query_concepts": [[0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1]], "query_gap_seconds": [[0.0, 0.0, 0.0], [0.0, 0.0, 86400.0], [0.0, 0.0, 86400.0], [0.0, 0.0, 86400.0]], "query_gap_known": [[false, false, false], [false, false, true], [false, false, true], [false, false, true]], "courses": [[0, 0, 0, 0], [1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 0]], "query_course": [1, 1, 1, 1]}, "targets": [1, 1, 0, 1], "event_ids": ["e67a3d0a-2292-5ec7-8d4d-8909ef4e7d48", "91bb9f4c-d933-56b6-bc63-c9c4afa0fc90", "80a1fddc-c825-55f2-a2d3-5ee3fe99fbfc", "511800b7-314b-53fc-bc99-897b14199b77"]}}


## 입력과 이번 정답을 어떻게 나눴는지 설명합니다



## 막힌 부분과 질문을 적습니다

