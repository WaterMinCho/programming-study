# kimjs85529-a11y 모델 실습

- **담당 모델:** LSTM + 풀이 간격(Time Gap)
- **담당 이슈:** https://github.com/WaterMinCho/programming-study/issues/121

기본 LSTM 모델에 같은 개념을 마지막으로 학습한 이후의 경과 시간 정보를 추가하여, 다음 문제의 정답 확률을 예측하는 모델을 구현하는 역할을 담당한다.

이번 실습에서는 본격적인 모델 구현에 앞서 공통 입력 예제를 실행하고 데이터 구조를 확인하였다.

## 실행한 명령과 결과

### 실행 환경

- 운영체제: Windows
- Python 버전: 3.13.5
- 프로젝트 경로: `C:\programming-study`
- 데이터 종류: 합성 데이터(Synthetic Data)

### 실행 명령어

```powershell
cd C:\programming-study

python --version

python -m learning_server.starter --synthetic --out ../learning-demo-v3

python -m learning_server.input_example --dataset ../learning-demo-v3 --track python --batch-size 4 --length 4
```

### 실행 결과

명령어 실행 과정에서 오류가 발생하지 않았으며, 합성 데이터 생성과 공통 입력 예제 출력이 정상적으로 완료되었다.

확인한 주요 출력값은 다음과 같다.

```text
features_version: 4
synthetic: true
tracks: ["ai", "python"]

batch: 4
history_length: 4
concept_width: 3

lengths: [0, 1, 2, 3]
targets: [1, 1, 0, 1]
```

4개의 입력 예제를 확인하였으며, 각 예제에서 과거 풀이 기록과 이번 문제의 정답 정보가 구분되어 제공되는 것을 확인하였다.

현재는 공통 데이터의 입력 구조를 확인한 단계이며, 실제 LSTM 모델의 학습과 성능 평가는 진행하지 않았다.

## 입력과 이번 정답을 구분한 방법

공통 입력 예제의 출력에서 `inputs`와 `targets`를 구분하였다.

`inputs`에는 이전 문제의 풀이 기록과 이번에 예측할 문제의 정보가 포함된다.

- `questions`: 과거에 풀이한 문제 정보
- `concepts`: 과거 문제의 개념 정보
- `results`: 과거 문제의 정오답 정보
- `mask`: 실제 과거 풀이 기록이 존재하는 위치
- `lengths`: 실제 과거 풀이 기록의 개수
- `query_question`: 이번에 정답 여부를 예측할 문제
- `query_concepts`: 이번 문제의 개념 정보
- `query_gap_seconds`: 같은 개념을 마지막으로 채점한 이후 경과한 시간
- `query_gap_known`: 해당 시간 간격을 확인할 수 있는지 여부

반면 `targets`는 이번 문제에 대한 실제 정답 여부를 나타낸다.

이번 실행에서 확인한 값은 다음과 같다.

```python
targets = [1, 1, 0, 1]
```

여기서 `1`은 정답, `0`은 오답을 의미한다.

따라서 모델은 과거 풀이 기록과 이번 문제의 정보를 입력받아 정답 확률을 예측하고, 예측 결과를 `targets`와 비교해야 한다.

이번 문제의 실제 정답인 `targets`를 모델 입력에 포함하면 정답을 미리 알려주는 데이터 누수가 발생하므로 주의해야 한다.

## 빈 이력과 빈 자리를 확인한 내용

이번 공통 입력 예제에서는 다음 값이 출력되었다.

```python
lengths = [0, 1, 2, 3]
```

이는 4개의 예제가 각각 0개, 1개, 2개, 3개의 과거 풀이 기록을 가지고 있다는 의미이다.

실행 명령어에서 `--length 4`로 설정했으므로, 과거 풀이 기록이 4개보다 적은 경우에는 부족한 부분이 빈 자리로 채워진다.

이때 `mask`를 사용하여 실제 풀이 기록과 빈 자리를 구분할 수 있다.

- `true`: 실제 풀이 기록이 존재하는 위치
- `false`: 빈 자리

실제 출력된 `mask`는 다음과 같다.

```python
mask = [
    [False, False, False, False],
    [True,  False, False, False],
    [True,  True,  False, False],
    [True,  True,  True,  False]
]
```

첫 번째 예제는 `lengths=0`이므로 과거 풀이 기록이 존재하지 않으며, `mask`가 모두 `False`로 표시된다.

두 번째 예제는 실제 풀이 기록이 1개이므로 첫 번째 위치만 `True`로 표시된다.

또한 `results`에서 `0`은 오답을 의미하기 때문에, 단순히 값이 0이라는 이유로 빈 자리라고 판단해서는 안 된다.

따라서 향후 LSTM 모델을 구현할 때도 `mask`와 `lengths`를 활용하여 빈 이력과 실제 풀이 기록을 구분해야 한다.

## 막힌 부분과 질문

공통 입력 예제를 실행하는 과정에서 오류는 발생하지 않았다.

담당 모델에 필요한 시간 관련 입력인 `query_gap_seconds`와 `query_gap_known`도 정상적으로 출력되는 것을 확인하였다.

실제 출력 결과에서는 다음과 같이 경과 시간이 표시되었다.

```python
query_gap_seconds = [
    [0.0, 0.0, 0.0],
    [0.0, 0.0, 86400.0],
    [0.0, 0.0, 86400.0],
    [0.0, 0.0, 86400.0]
]
```

`86400.0`은 86400초, 즉 24시간에 해당한다.

또한 `query_gap_known`을 통해 해당 시간 간격을 확인할 수 있는지 구분할 수 있다.

특히 `query_gap_known=False`인 경우에는 `query_gap_seconds=0.0`이어도 실제 경과 시간이 0초라는 의미는 아니다. 시간 간격을 확인할 수 없는 경우이므로 별도로 구분해야 한다.

향후 모델 개발 과정에서 확인할 사항은 다음과 같다.

1. 기본 LSTM 담당 팀원과 모델 구조 및 입력 데이터 처리 방식 공유
2. 시간 간격 정보를 LSTM 모델에 추가하는 방법
3. 시간 간격을 알 수 없는 데이터의 처리 방법
4. 기본 LSTM과 시간 간격을 추가한 LSTM의 성능 비교 방법

이번 실습을 통해 공통 입력 데이터의 구조와 빈 이력 처리 방식, 시간 간격 정보의 의미를 확인하였다. 이후 기본 LSTM 모델을 바탕으로 시간 간격 정보를 추가하고, 동일한 조건에서 성능을 비교할 예정이다.