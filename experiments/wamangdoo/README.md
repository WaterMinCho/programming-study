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
4개의 배치 과거 기록 4칸을 꺼낸 결과값 출력되었습니다.


## 입력과 이번 정답을 어떻게 나눴는지 설명합니다



## 막힌 부분과 질문을 적습니다

