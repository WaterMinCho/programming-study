# kimjs85529-a11y 모델 실습

- **담당 모델:** LSTM + 풀이 간격(Time Gap)
- **담당 이슈:** https://github.com/WaterMinCho/programming-study/issues/121
- **이전 입력 실습 PR:** https://github.com/WaterMinCho/programming-study/pull/158
- **작업 브랜치:** `model/kimjs85529-a11y-gaps`
- **이번 작업:** 이번 문제의 개념에 해당하는 풀이 간격과 시간 확인 여부 선택 및 테스트

### 작업 파일

- `experiments/kimjs85529-a11y/inspect_gaps.py`: 개념별 시간 선택 함수 및 합성 입력 확인
- `experiments/kimjs85529-a11y/test_gaps.py`: 시간 선택 함수의 6개 독립 테스트
- `experiments/kimjs85529-a11y/README.md`: 실행 방법 및 검증 결과 기록

기본 LSTM에 개념별 풀이 간격 정보를 추가하기 전에, 공통 `inputs`에서 **이번 문제에 표시된 개념 인덱스의 시간값을 선택**하는 기능을 구현하였다. 단, `<UNK>`(인덱스 1)는 여러 미등록 개념이 함께 묶인 칸이므로 아래에 해석상의 한계를 기록하였다.

이전 PR #158에서는 공통 입력의 구조를 확인하였고, 이번 작업에서는 시간 선택 함수와 테스트를 작성하여 실제 동작을 확인하였다.

현재 단계는 시간 정보 선택 및 검증 단계이며, LSTM 학습과 성능 비교는 진행하지 않았다.

## 실행한 명령과 결과

### 1. 실행 환경

- 운영체제: Windows
- Python 버전: `3.13.5`
- 프로젝트 경로: `C:\programming-study`
- 합성 데이터 경로: `C:\learning-demo-f5`
- 공통 입력 버전: `features_version: 5`
- 학습 트랙: `python`
- 데이터 분할: `train`
- 배치 크기: `4`
- 과거 이력 길이: `4`

### 2. 합성 데이터 생성 및 입력 확인

프로젝트 저장소 루트에서 아래 명령어를 실행하였다.

```powershell
cd C:\programming-study

python -m learning_server.starter --synthetic --out ../learning-demo-f5

python -m learning_server.input_example --dataset ../learning-demo-f5 --track python --batch-size 4 --length 4
```

기존 데이터 폴더를 덮어쓰지 않고 새로운 `learning-demo-f5` 폴더를 생성하였다.

확인한 주요 정보는 다음과 같다.

```text
features_version: 5
synthetic: true
batch: 4
history_length: 4
concept_width: 3
```

실제 과거 풀이 이력 길이와 이번 문제의 정답표는 다음과 같았다.

```python
lengths = [0, 1, 2, 3]
targets = [1, 1, 0, 1]
```

`synthetic: true`는 실제 학습자의 풀이 기록이 아닌 실습용 합성 데이터임을 의미한다.

이번 문제의 실제 정답인 `targets`는 입력인 `inputs`와 분리되어 있다.

### 3. 시간 선택 코드 실행

`inspect_gaps.py`를 실행하여 합성 데이터 4개의 개념별 시간 정보를 확인하였다.

```powershell
cd C:\programming-study

python .\experiments\kimjs85529-a11y\inspect_gaps.py
```

실제 실행 결과는 다음과 같다.

```text
===== 공통 입력 데이터 확인 =====
데이터 경로: C:\learning-demo-f5

예제 1
이번 문제의 개념: [0, 0, 1]
개념별 시간(초): [0.0, 0.0, 0.0]
시간 확인 여부: [False, False, False]
선택된 개념: demo
경과 시간: None
로그 변환: 0.0
모델 입력 특성: [0.0, 0]

예제 2
이번 문제의 개념: [0, 0, 1]
개념별 시간(초): [0.0, 0.0, 86400.0]
시간 확인 여부: [False, False, True]
선택된 개념: demo
경과 시간: 86400.0
로그 변환: 0.6931471805599453
모델 입력 특성: [0.6931471805599453, 1]

예제 3
이번 문제의 개념: [0, 0, 1]
개념별 시간(초): [0.0, 0.0, 86400.0]
시간 확인 여부: [False, False, True]
선택된 개념: demo
경과 시간: 86400.0
로그 변환: 0.6931471805599453
모델 입력 특성: [0.6931471805599453, 1]

예제 4
이번 문제의 개념: [0, 0, 1]
개념별 시간(초): [0.0, 0.0, 86400.0]
시간 확인 여부: [False, False, True]
선택된 개념: demo
경과 시간: 86400.0
로그 변환: 0.6931471805599453
모델 입력 특성: [0.6931471805599453, 1]
```

네 예제에서 현재 문제의 개념은 모두 `demo`(인덱스 2)이다.

첫 번째 예제는 시간 미확인 상태이며, 두 번째부터 네 번째 예제까지는 86400초(1일)의 경과 시간이 확인되었다.

### 4. 시간 선택 함수 테스트

`test_gaps.py`에서 직접 만든 입력을 이용하여 6개 항목을 테스트하였다.

```powershell
cd C:\programming-study

python .\experiments\kimjs85529-a11y\test_gaps.py
```

실제 실행 결과는 다음과 같다.

```text
===== 테스트 1. 시간 확인 가능 =====
통과: [0.6931471805599453, 1]

===== 테스트 2. 시간 미확인 =====
통과: [0.0, 0]

===== 테스트 3. 실제 0초 =====
미확인: [0.0, 0]
실제 0초: [0.0, 1]
통과: 두 상황이 구분됨

===== 테스트 4. 다른 개념 제외 =====
통과: loop의 7일 간격이 제외됨

===== 테스트 5. 다중 개념 =====
통과: 두 개념의 간격 모두 선택

===== 테스트 6. 빈 이력 상황 =====
통과: 이력 길이 0에서도 시간 미확인 상태로 처리
```

6개 테스트 모두 `assert` 오류 없이 실행되었다.

## 입력과 이번 정답을 구분한 방법

### 1. 공통 입력 구조

공통 데이터는 `example["inputs"]`와 `example["targets"]`로 구분된다.

`features_version: 5`에서 사용하는 `inputs`의 15개 항목은 다음과 같다.

| 구분 | 입력 이름 | 의미 |
|---|---|---|
| 과거 풀이 | `questions` | 과거에 풀이한 문제 ID |
| 과거 풀이 | `concepts` | 과거 문제의 개념 정보 |
| 과거 풀이 | `results` | 과거 문제의 정오답 정보 |
| 과거 풀이 | `courses` | 과거 문제의 과정 정보 |
| 과거 이력 | `mask` | 실제 과거 풀이 기록이 존재하는 위치 |
| 과거 이력 | `lengths` | 실제 과거 풀이 기록의 개수 |
| 현재 문제 | `query_question` | 정답 여부를 예측할 문제 ID |
| 현재 문제 | `query_concepts` | 이번 문제의 개념 정보 |
| 현재 문제 | `query_course` | 이번 문제의 과정 정보 |
| 시간 정보 | `query_gap_seconds` | 개념별 경과 시간(초) |
| 시간 정보 | `query_gap_known` | 개념별 시간 확인 여부 |
| 난이도 | `difficulties` | 과거 문제의 난이도 |
| 난이도 | `difficulty_known` | 과거 난이도 확인 여부 |
| 난이도 | `query_difficulty` | 현재 문제의 난이도 |
| 난이도 | `query_difficulty_known` | 현재 난이도 확인 여부 |

이번 시간 선택 함수에서는 다음 입력을 사용한다.

- `query_concepts`
- `query_gap_seconds`
- `query_gap_known`
- `vocabulary["concepts"]`

세 입력 벡터의 동일한 인덱스를 함께 확인하여 현재 문제에 해당하는 개념의 시간값을 선택한다.

난이도 관련 4개 항목은 이번 단계에서 사용하지 않는다.

### 2. 이번 정답과 입력 분리

과거 문제의 정오답은 `inputs["results"]`에 포함된다.

반면 이번 문제의 정답은 `example["targets"]`에 별도로 저장된다.

```python
inputs = example["inputs"]
```

`select_query_gaps()` 함수는 이번 문제의 정답인 `targets`를 전달받지 않는다.

이번 정답을 미리 입력하면 데이터 누수(Data Leakage)가 발생할 수 있으므로 입력과 정답을 분리하였다.

## 빈 이력과 빈 자리를 확인한 내용

### 1. 과거 이력 길이 확인

합성 데이터 4개의 실제 과거 풀이 개수는 다음과 같다.

```python
lengths = [0, 1, 2, 3]
```

각각 0개, 1개, 2개, 3개의 과거 풀이 기록을 가지고 있다는 의미이다.

과거 이력 길이를 4로 지정하였으므로 기록이 부족한 부분은 빈 자리로 채워진다.

### 2. Mask를 통한 실제 풀이와 빈 자리 구분

```python
mask = [
    [False, False, False, False],
    [True,  False, False, False],
    [True,  True,  False, False],
    [True,  True,  True,  False],
]
```

- `True`: 실제 과거 풀이 기록이 존재하는 위치
- `False`: 과거 풀이 기록이 없는 빈 자리(Padding)

첫 번째 예제는 `lengths=0`이므로 과거 풀이 기록이 없고 모든 `mask`가 `False`이다.

또한 `results`의 `0`은 실제 오답일 수도 있고 빈 자리의 기본값일 수도 있다.

따라서 `results=0`이라는 이유만으로 오답이라고 판단하지 않고 `mask`와 `lengths`를 함께 확인해야 한다.

### 3. 빈 이력에 대한 시간 선택 테스트

과거 풀이가 없는 상황을 다음과 같이 설정하였다.

```python
empty_history_input = {
    "lengths": 0,
    "mask": [False, False, False, False],
    "query_concepts": [0, 0, 1, 0],
    "query_gap_seconds": [0.0, 0.0, 0.0, 0.0],
    "query_gap_known": [False, False, False, False],
}
```

이 입력에 대한 시간 선택 결과는 다음과 같다.

```text
통과: 이력 길이 0에서도 시간 미확인 상태로 처리
```

시간 선택 함수는 과거 풀이 이력을 직접 순회하지 않고 현재 문제의 `query_*` 벡터만 읽기 때문에 과거 이력이 없어도 시간 선택 결과를 반환할 수 있다.

단, 이 테스트는 시간 선택 함수의 동작을 확인한 것으로 LSTM 모델의 순전파나 예측 정확도를 검증한 것은 아니다.

## 이번 문제의 개념별 풀이 간격 선택

### 1. 시간 선택 함수

`inspect_gaps.py`에 다음 함수를 작성하였다.

```python
select_query_gaps(concepts, seconds, known, names)
```

함수는 다음 순서로 동작한다.

1. `query_concepts`에서 값이 `1`인 개념을 찾는다.
2. 패딩에 해당하는 인덱스 `0`은 제외한다.
3. 선택한 개념과 같은 인덱스의 `query_gap_seconds`와 `query_gap_known`을 읽는다.
4. 시간이 확인된 경우 초 단위를 일 단위로 변환한다.
5. 시간이 확인되지 않은 경우 실제 경과 시간을 `None`으로 처리한다.
6. 이번 문제에 여러 개념이 포함되면 각 개념의 시간 정보를 모두 반환한다.

선택한 개념의 시간 정보는 다음과 같이 저장한다.

```python
{
    "concept_id": j,
    "concept_name": names[j],
    "known": gap_known,
    "gap_seconds": gap_seconds,
    "gap_days": gap_days,
    "gap_log": gap_log,
    "time_feature": [gap_log, int(gap_known)]
}
```

### 2. 시간 단위 변환

시간 정보가 확인된 경우 경과 시간을 초 단위에서 일 단위로 변환한다.

```python
gap_days = gap_seconds / 86400.0
gap_log = math.log1p(gap_days)
```

86400초는 1일이다.

```text
86400초 = 1일
log1p(1) = 0.6931471805599453
```

경과 시간의 범위가 커질 수 있으므로 로그 변환한 값을 향후 모델 입력 특성으로 사용할 수 있도록 구성하였다.

로그 변환은 시간값의 표현을 바꾸는 것이며, 시간이 길수록 정답 확률이 낮아진다고 미리 가정하는 처리는 아니다.

### 3. 시간 미확인 처리

시간 간격은 반드시 `query_gap_seconds`와 `query_gap_known`을 함께 확인해야 한다.

| 입력값 | 의미 | 모델 입력 특성 |
|---|---|---|
| `0.0`, `False` | 실제 경과 시간을 모름 | `[0.0, 0]` |
| `0.0`, `True` | 실제 경과 시간이 0초 | `[0.0, 1]` |
| `86400.0`, `True` | 실제 경과 시간이 1일 | `[0.6931471805599453, 1]` |

시간을 모르는 경우 다음과 같이 처리한다.

```python
gap_seconds = None
gap_days = None
gap_log = 0.0
```

모델에서 사용할 숫자 표현은 `0.0`으로 두더라도 시간 확인 여부를 `0`으로 함께 저장하여 실제 0초와 구분하였다.

따라서 `0.0·False`를 실제 0초가 지난 것으로 해석하지 않는다.

### 4. 다른 개념의 시간 제외

이번 문제의 개념을 다음과 같이 설정하였다.

```python
query_concepts = [0, 0, 1, 0]
query_gap_seconds = [0.0, 0.0, 86400.0, 604800.0]
query_gap_known = [False, False, True, True]
```

이번 문제에서 선택된 개념은 `demo`(인덱스 2)이다.

따라서 `demo`의 86400초만 선택하며, 관련 없는 `loop`(인덱스 3)의 604800초(7일)는 제외한다.

테스트 결과:

```text
통과: loop의 7일 간격이 제외됨
```

**미등록 개념(`<UNK>`, 인덱스 1)의 한계**

위 테스트처럼 개념 번호표에 등록된 `demo`와 `loop`는 서로 다른 인덱스를 사용하므로, 이번 문제와 관련 없는 `loop`의 시간을 제외할 수 있다. 그러나 번호표에 없는 개념은 모두 `<UNK>`(인덱스 1)로 합쳐지므로 이 경우에는 같은 방식으로 서로 다른 개념을 구분할 수 없다.

공통 입력의 `batch()`에서는 미등록 개념들의 경과 시간이 동일한 인덱스 1에 모이고, 그중 가장 짧은 값이 `query_gap_seconds[1]`에 들어간다. `inspect_gaps.py`는 `<PAD>`(인덱스 0)만 제외하고 `<UNK>`(인덱스 1)는 선택하므로, 선택된 시간이 이번 문제의 미등록 개념 자체에 해당하지 않을 수 있다.

예를 들어 이번 문제의 미등록 개념 X와 다른 미등록 개념 Y가 있고, Y를 2분 전에 풀었다면 다음 입력이 가능하다.

```python
names = ["", "", "demo"]  # 인덱스 0: PAD, 인덱스 1: UNK
concepts = [0, 1, 0]
seconds = [0.0, 120.0, 0.0]
known = [False, True, False]

result = select_query_gaps(concepts, seconds, known, names)
print(result[0]["concept_id"], repr(result[0]["concept_name"]), result[0]["gap_seconds"])
```

확인 결과:

```text
1 '' 120.0
```

이 경우 함수는 인덱스 1의 이름이 빈 문자열(`''`)인 항목과 120초를 선택한다. 하지만 **그 120초는 X의 정확한 마지막 풀이 간격이 아니라 Y 등 다른 미등록 개념의 간격일 수도 있다.** 따라서 `<UNK>` 칸에서 선택된 시간은 개별 개념의 정확한 시간으로 해석하지 않고, 여러 미등록 개념이 합쳐진 값이라는 한계를 가진 정보로 취급한다. 이번 PR에서는 해당 칸을 제외하지 않고 기존 선택 동작을 유지한다.

### 5. 여러 개념이 포함된 경우

이번 문제에 두 개념이 포함된 상황도 확인하였다.

```python
query_concepts = [0, 0, 1, 1]
query_gap_seconds = [0.0, 0.0, 86400.0, 172800.0]
query_gap_known = [False, False, True, True]
```

두 개념의 경과 시간은 다음과 같다.

- `demo`: 86400초(1일)
- `loop`: 172800초(2일)

함수는 첫 번째 개념만 선택하지 않고 두 개념의 시간 정보를 모두 반환한다.

테스트 결과:

```text
통과: 두 개념의 간격 모두 선택
```

### 6. 최종 테스트 결과

`test_gaps.py`에서는 다음 6개 항목을 확인하였다.

| 번호 | 테스트 항목 | 결과 |
|---|---|---|
| 1 | 시간 확인 가능 | 1일의 경과 시간을 로그 변환하여 정상 처리 |
| 2 | 시간 미확인 | 미확인 시간을 `None`으로 처리 |
| 3 | 실제 0초와 미확인 구분 | `[0.0, 0]`과 `[0.0, 1]` 구분 |
| 4 | 다른 개념 제외 | 관련 없는 `loop`의 7일 간격 제외 |
| 5 | 다중 개념 | 두 개념의 시간 정보 모두 선택 |
| 6 | 빈 이력 | 과거 풀이가 없어도 시간 미확인 상태 처리 |

6개 테스트 모두 통과하였다.

## 막힌 부분과 질문

이전 입력 실습에서는 `learning-demo-v3`로 공통 입력을 확인하였으며, 이번 작업에서는 최신 입력 형식인 `features_version: 5`에 맞춰 `learning-demo-f5`를 별도 폴더에 생성하였다.

기존 데이터 폴더는 삭제하거나 덮어쓰지 않았다.

시간 간격이 확인되지 않은 경우 숫자 `0.0`만 사용하면 실제 0초와 구분할 수 없으므로 `query_gap_known`을 함께 사용하도록 구현하였다.

번호표에 등록된 개념은 이번 문제와 관련 없는 개념의 시간을 제외하고, 여러 개념이 포함된 경우에는 각각의 시간 정보를 반환하도록 하였다. 단, `<UNK>`(인덱스 1)에서는 여러 미등록 개념의 간격이 합쳐질 수 있어 개별 개념의 정확한 시간으로 단정할 수 없다.

향후 기본 LSTM 담당자의 모델 코드, 전체 커밋 SHA 및 실행 설정을 공유받은 후 같은 LSTM·공통 자료·설정으로 시간 정보를 넣은 경우와 넣지 않은 경우를 비교할 예정이다.

이번 작업에서는 시간 선택 함수와 테스트만 완료하였다. 모델 학습, 저장·불러오기 및 성능 비교는 진행하지 않았다.

실제 학습 기록, 개별 풀이 결과 및 실제 자료로 학습한 가중치는 공개 PR에 포함하지 않는다.
