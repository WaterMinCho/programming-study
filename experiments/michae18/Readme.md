# michae18 모델 실습

## 담당 모델
- GitHub ID: `michae18`
- 담당 모델: 기본 LSTM
- 작업 브랜치: `model/michae18-first-input`
- 담당 이슈: https://github.com/WaterMinCho/programming-study/pull/150
- 모델 구현 파일: experiments/michae18/model.py
- 실행 파일: experiments/michae18/train.py
- 현재 단계: 현재 단계: LSTM 모델 구현 및 임시 입력 4건에 대한 순전파 확인 완료 (실제 데이터 학습은 미실행)
- 모델 학습: 미실행

## 실행한 명령과 결과
저장소 루트에서 train.py를 Python 모듈로 실행했습니다.
```bash
python -m experiments.michae18.train
```

## 실행 결과
```bash
예측 확률: [0.5190075039863586, 0.4140140116214752, 0.5113391280174255, 0.5685640573501587]
예측 개수: 4
```

### 1. 합성 데이터 생성

```bash
python -m learning_server.starter --synthetic --out ../learning-demo-f4
```

- 목적: 모델 입력 구조를 확인하기 위한 합성 데이터 생성
- 데이터 저장 위치: `../learning-demo-f4`
- 실행 결과: 가상 데이터 파일 생성

### 2. Python 입력 예시 확인

```bash
python -m learning_server.input_example --dataset ../learning-demo-f4 --track python --batch-size 4 --length 4
```

- Track: `python`
- Batch size: `4`
- History length: `4`
- 실행 결과: 가상 데이터 생성

## 출력에서 이해한 내용이나 오류를 적습니다

- LSTM은 과거 풀이 이력을 순차적으로 처리하여 학습자의 이력 상태를 나타내는 벡터를 생성합니다.

- 과거 문제의 ID는 Embedding을 통해 벡터로 변환합니다.

- 과거 문제의 개념 정보(concepts)와 정답 여부(results)를 결합하여 LSTM에 입력합니다.

- LSTM에서 생성한 이력 상태와 이번에 예측할 문제 정보(query_question, query_concepts)를 결합합니다.

- 최종 선형 계층(Linear)과 Sigmoid를 통해 이번 문제를 맞힐 확률을 계산합니다.

- 출력 개수가 입력 예시 개수와 동일한 4개임을 확인했습니다.

- 실제 공통 학습 자료를 불러오는 과정에서는 다음 오류가 발생했습니다.

```bash
ValueError: 이전 이력 집계로 만든 자료입니다.
원본을 보존하고 새 폴더에 공통 자료를 다시 준비해 주세요.
``` 

## 입력과 이번 정답을 구분한 방법
현재 SmallLstm에서 사용하는 inputs는 다음과 같습니다.
### 기본 LSTM 모델에 사용할 항목 (6개)
- 과거 풀이 이력 (4개)

 - questions: 과거에 풀이한 문제 ID

 - concepts: 과거 문제의 개념 정보

 - results: 과거 문제의 정답 여부

 - lengths: 실제 과거 풀이 이력 길이

- 이번에 예측할 문제 정보 (2개)

 - query_question: 이번 문제 ID

 - query_concepts: 이번 문제의 개념 정보


현재는 기본적인 LSTM 구조를 먼저 구현하고, 추가 입력 특성의 활용 여부는 추후 검토할 예정입니다.
## 입력과 정답의 분리

- results에는 과거 문제의 정답 여부만 포함합니다.

- 이번 문제의 실제 정답 여부인 targets는 모델 입력에 포함하지 않습니다.

- 모델은 이번 문제를 맞힐 확률을 출력합니다.

- 추후 학습 단계에서는 예측 확률과 targets를 비교하여 손실을 계산할 예정입니다.

이번 문제의 정답을 입력에 포함하면 정답을 미리 알려주는 데이터 누수(Data Leakage)가 발생할 수 있으므로 분리해야 합니다.

## 빈 이력과 빈 자리를 어떻게 처리했는지 설명합니다

1. 빈 이력 (lengths = 0)

과거 풀이 기록이 없는 학습자도 예측할 수 있도록 이력 상태를 0으로 초기화했습니다.

```bash
history_state = history_input.new_zeros(
    batch_size, self.lstm.hidden_size
)
```

lengths > 0인 데이터만 LSTM에 입력하고, 이력이 없는 데이터는 초기화된 상태 벡터와 이번 문제 정보를 결합하여 예측하도록 구현했습니다.

2. 빈 자리 (Padding)

문제 ID 0을 패딩으로 사용하도록 설정했습니다.

```bash
self.embedding = nn.Embedding(
    num_questions, embeding_num, padding_idx=0
)
```

이력이 있는 데이터는 pack_padded_sequence를 사용하여 실제 이력 길이까지만 LSTM에서 처리하도록 구현했습니다.

따라서 패딩으로 채워진 위치가 LSTM의 최종 이력 상태에 영향을 주지 않도록 설계했습니다.

단, 빈 이력과 패딩에 대한 독립적인 테스트는 아직 진행하지 않았습니다.

## 막힌 부분과 질문

- 발생한 오류: [ValueError: 이전 이력 집계로 만든 자료입니다.
원본을 보존하고 새 폴더에 공통 자료를 다시 준비해 주세요.]
실제 데이터 로딩 오류: 공통 학습 자료를 불러오는 과정에서 다음 오류가 발생했습니다.
이에 따라 실제 데이터 연결은 보류하고, 임시 입력 4건을 이용해 LSTM 모델의 순전파 및 예측 확률 출력을 우선 확인했습니다.
- 추가로 확인할 내용: 
실제 공통 학습 자료의 호환성 문제 해결 및 모델 입력 연결

빈 이력과 패딩 처리에 대한 추가 검증

이슈#121 담당자에게 구현한 LSTM 모델을 전달한 후 실행 및 검증 결과 확인

검증 결과에 따른 모델 수정 및 개선 사항 반영

## 다음 작업

- 작은 예측이 확인되면 예측 오차 계산·역전파·가중치 갱신을 연결합니다. 학습 구간에서만 가중치를 바꿉니다.
- 검증과 저장·불러오기를 연결하고 같은 CPU·설정·평가 모드에서 저장 전후 예측 차이를 확인합니다.
- 기본 LSTM의 코드 경로·전체 커밋 SHA·설정·실행 방법을 [스터디] 같은 LSTM에 풀이 간격을 넣어 비교하기.#121 담당자에게 공유합니다. SHA는 같은 코드 버전을 다시 찾는 값입니다.
- 같은 자료의 단순 기준 방법과 비교하고 틀린 예제와 수정 이유를 남깁니다. 점수가 더 높아야만 완료되는 과제는 아닙니다.