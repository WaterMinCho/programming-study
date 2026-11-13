# kimjs85529-a11y 모델 실습

- **담당 모델:** LSTM + 풀이 간격(Time Gap)
- **담당 이슈:** https://github.com/WaterMinCho/programming-study/issues/121

기본 LSTM 모델에 개념별 풀이 간격 정보를 추가하여 다음 문제의 정답 확률을 예측하는 역할을 담당한다.

이번 실습에서는 모델 구현에 앞서 공통 합성 데이터를 생성하고 입력 예제를 실행하여 데이터 구조를 확인하였다.

## 실행한 명령과 결과

### 실행 환경

- 운영체제: Windows
- Python 버전: 3.13.5
- 프로젝트 경로: `C:\programming-study`
- 데이터 종류: 합성 데이터(Synthetic Data)
- 학습 트랙: `python`
- 데이터 분할: `train` (학습 구간, 입력 예제 명령어의 기본값)

### 실행 명령어

```powershell
cd C:\programming-study

python --version

python -m learning_server.starter --synthetic --out ../learning-demo-v3

python -m learning_server.input_example --dataset ../learning-demo-v3 --track python --batch-size 4 --length 4
```

### 1. Python 버전 확인

`python --version` 실행 결과:

```text
Python 3.13.5
```

### 2. 합성 데이터 생성 결과

`learning_server.starter` 명령어로 합성 데이터를 생성하였다.

출력된 주요 정보는 다음과 같다.

```text
features_version: 4
synthetic: true
tracks: ["ai", "python"]
history_limit: 128
```

합성 데이터는 프로젝트 저장소 외부의 `C:\learning-demo-v3` 폴더에 생성되었다.

`synthetic: true`는 실제 학습자 데이터가 아닌 실습용 합성 데이터임을 나타낸다.

### 3. 공통 입력 예제 실행 결과

`learning_server.input_example` 명령어를 실행하여 `python` 트랙의 `train` 분할에서 입력 예제를 확인하였다.

출력된 주요 정보는 다음과 같다.

```text
batch: 4
history_length: 4
concept_width: 3
```

실제 과거 풀이 기록의 개수와 이번 문제의 정답은 다음과 같았다.

```python
lengths = [0, 1, 2, 3]
targets = [1, 1, 0, 1]
```

4개의 입력 예제가 정상적으로 출력되었으며, 각 예제의 과거 풀이 기록과 이번 문제의 정답이 구분되어 제공되는 것을 확인하였다.

이번 실습에서는 LSTM 모델 학습이나 성능 평가는 진행하지 않았다.

## 입력과 이번 정답을 구분한 방법

공통 입력의 `inputs`에는 과거 문제 풀이 기록과 이번에 예측할 문제에 대한 정보가 포함된다.

- `questions`: 과거에 풀이한 문제의 ID
- `concepts`: 과거 문제에 연결된 개념 정보
- `results`: 과거 문제의 정오답 정보
- `courses`: 과거 문제의 학습 과정 정보
- `mask`: 실제 과거 풀이 기록이 존재하는 위치
- `lengths`: 실제 과거 풀이 기록의 개수
- `query_question`: 이번에 정답 여부를 예측할 문제
- `query_concepts`: 이번 문제에 연결된 개념을 표시하는 벡터
- `query_course`: 이번 문제의 학습 과정 정보
- `query_gap_seconds`: 개념별 마지막 풀이 시점부터 예측 시각(`prediction_at`)까지 경과한 시간을 초 단위로 나타내는 벡터
- `query_gap_known`: 각 개념의 경과 시간을 확인할 수 있는지 나타내는 벡터

`query_gap_seconds`는 이번 문제의 개념에 대한 시간만 저장하는 것이 아니라, 과거 풀이 이력에 있는 개념별 시간 간격을 저장한다.

따라서 이번 문제와 관련 없는 개념의 시간 정보도 포함될 수 있다.

이번 문제에 해당하는 개념의 간격을 사용하려면 `query_concepts`에서 값이 1인 열에 대응하는 `query_gap_seconds`와 `query_gap_known` 값을 확인해야 한다.

공통 입력의 개념 번호표에는 패딩을 위한 `<PAD>`와 알 수 없는 개념을 위한 `<UNK>`가 포함된다. 따라서 `concept_width`는 실제 학습 개념 수와 같다고 단정할 수 없다.

반면 `targets`는 이번 문제에 대한 실제 정답 여부를 나타낸다.

```python
targets = [1, 1, 0, 1]
```

여기서 `1`은 정답, `0`은 오답이다.

모델은 과거 풀이 기록과 이번 문제의 정보를 이용해 정답 확률을 예측하고, 그 결과를 `targets`와 비교하여 학습해야 한다.

이번 문제의 실제 정답인 `targets`를 모델 입력에 포함하면 데이터 누수가 발생하므로 주의해야 한다.

## 빈 이력과 빈 자리를 확인한 내용

공통 입력 예제에서 다음 값이 출력되었다.

```python
lengths = [0, 1, 2, 3]
```

이는 4개의 예제가 각각 0개, 1개, 2개, 3개의 과거 풀이 기록을 가지고 있다는 의미이다.

입력 길이를 4로 설정했으므로 실제 기록이 부족한 부분은 빈 자리로 채워진다.

이때 `mask`를 사용하여 실제 풀이 기록과 빈 자리를 구분한다.

- `True`: 실제 과거 풀이 기록이 존재하는 위치
- `False`: 빈 자리

실제 출력된 `mask`는 다음과 같다.

```python
mask = [
    [False, False, False, False],
    [True,  False, False, False],
    [True,  True,  False, False],
    [True,  True,  True,  False]
]
```

첫 번째 예제는 `lengths=0`이므로 과거 풀이 기록이 없으며, `mask`가 모두 `False`이다.

두 번째 예제는 실제 풀이 기록이 1개이므로 첫 번째 위치만 `True`로 표시된다.

또한 `results`의 `0`은 오답을 의미하지만, 빈 자리에도 0이 사용될 수 있다.

따라서 값이 0이라는 이유만으로 오답이라고 판단하지 않고, `mask`와 `lengths`를 함께 확인해야 한다.

## 막힌 부분과 질문

공통 입력 예제를 실행하는 과정에서 오류는 발생하지 않았다.

담당 모델에서 사용할 시간 간격 정보인 `query_gap_seconds`와 `query_gap_known`이 출력되는 것도 확인하였다.

### 1. 개념별 경과 시간 확인

`learning_server.input_example`의 출력에서 확인한 `query_gap_seconds`는 다음과 같다.

```python
query_gap_seconds = [
    [0.0, 0.0,     0.0],
    [0.0, 0.0, 86400.0],
    [0.0, 0.0, 86400.0],
    [0.0, 0.0, 86400.0]
]
```

이번 합성 데이터의 개념 열은 다음과 같이 대응한다.

- 0번 열: `<PAD>` (패딩)
- 1번 열: `<UNK>` (알 수 없는 개념)
- 2번 열: `demo` (합성 데이터의 학습 개념)

2~4번 예제에서는 `demo`에 해당하는 2번 열의 시간 간격이 `86400.0`초로 출력되었다.

이는 24시간에 해당한다.

다만 이번 출력만으로 합성 데이터 전체가 하루 간격으로 생성된다고 판단할 수는 없다.

### 2. 시간 확인 여부 확인

동일한 공통 입력 예제에서 출력된 `query_gap_known`은 다음과 같다.

```python
query_gap_known = [
    [False, False, False],
    [False, False, True],
    [False, False, True],
    [False, False, True]
]
```

첫 번째 예제에서는 모든 개념 열의 시간 확인 여부가 `False`였다.

2~4번 예제에서는 `demo`에 해당하는 2번 열만 `True`로 나타났다.

따라서 `query_gap_seconds=0.0`이라도 `query_gap_known=False`라면 실제 경과 시간이 0초라는 의미가 아니라, 해당 시간 간격을 확인할 수 없다는 뜻이다.

이 두 입력을 함께 확인해야 실제 0초와 시간 정보가 없는 경우를 구분할 수 있다.

### 3. 향후 모델 개발 시 확인할 사항

이번 실습을 통해 공통 입력의 구조와 개념별 시간 간격 정보의 의미를 확인하였다.

향후 모델 구현 시 추가로 확인할 사항은 다음과 같다.

1. 기본 LSTM 담당 팀원의 모델 구조 및 입력 처리 방식
2. 개념별 시간 간격 중 예측 대상 문제와 관련된 값을 선택하는 방법
3. 시간 정보가 확인되지 않은 데이터의 처리 방법
4. 기본 LSTM과 시간 간격 추가 LSTM의 성능 비교 방법

이번 실습은 공통 입력 예제의 구조를 이해하는 단계이며, 실제 모델 구현과 성능 비교는 후속 작업으로 진행할 예정이다.