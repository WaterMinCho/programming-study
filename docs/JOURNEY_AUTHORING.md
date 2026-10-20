# 알고리즘 여행 출제 안내

알고리즘 여행의 던전에 문제를 넣는 사람이 보는 문서입니다. 파일 규격, 봉인과 검증 명령, 출제자·재풀이자·검토자가 나눠 맡는 교차 검증 순서를 적었습니다. 파이썬 스터디 문제 은행(`problems/`)의 규격은 [AUTHORING.md](AUTHORING.md) 에 있습니다.

문제는 프로그래머스처럼 `solution(...)` 이 값을 돌려주는 꼴만 씁니다. 학생은 같은 문제를 Python 과 JavaScript 가운데 골라 풀고, 채점은 두 언어 모두 학생 컴퓨터에서 돕니다.

문제마다의 지문 내용, 테스트 목록, 흔한 오답, 시간 제한 수치는 스터디장이 가진 커리큘럼 문서가 정합니다. 이 문서는 그 내용을 담는 파일 꼴과 확인 절차를 다루고, 아래에서 "커리큘럼"은 그 문서를 가리킵니다.

## 1. 폴더와 파일

```
dungeons/
  index.json                 16개 던전의 순서·제목·주제·보스 목표·권장 선행(준비 중 던전 포함)
  d01/
    meta.json                문제 순서와 역할, 익히는 기술
    intro.md                 지도 오른쪽에 보이는 무대 설명
    sealed.json              비밀 파일 묶음(문제마다의 비밀 파일과 던전 검토 기록 review.json)
    assets/1-1a.gif …        해설 그림
    p1/ problem.json         공개
        problem.md           공개 지문
        solution.py …        비밀 파일의 평문 작업본(커밋하지 않음)
    p2/ … boss/
```

- 던전 폴더 이름은 `d01`~`d16`, 문제 폴더 이름은 `p1`~`p9` 와 `boss` 입니다. 화면에 보이는 번호("1-3", "1-B")는 meta.json 의 `no` 에 적습니다.
- 던전 폴더에 `meta.json` 이 있으면 그 던전이 출제된 것으로 봅니다. index.json 은 고치지 않아도 됩니다.
- 비밀 파일(기준 풀이, 테스트, 힌트, 해설 등)은 평문으로 커밋하지 않습니다. `.gitignore` 가 평문 작업본을 막고, 던전마다 `sealed.json` 하나로 묶어 커밋합니다. 묶음은 base64 와 zlib 로 감쌌을 뿐이라 우연히 답을 보지 않게 가리는 용도로 씁니다.
- `dungeons/` 를 `problems/` 아래에 두지 않습니다. 파이썬 스터디가 `problems/<폴더>/meta.json` 을 세트로 읽기 때문입니다.

## 2. 던전 목록과 무대

### index.json

```json
{
  "format": 1,
  "dungeons": [
    {"id": "d01", "no": 1, "title": "향신료 시장", "topic": "해시·투 포인터", "boss_target": "G3 / Lv3", "prereq": []},
    {"id": "d16", "no": 16, "title": "시간의 탑", "topic": "펜윅·세그먼트·오프라인", "boss_target": "P5~P4 / Lv4", "prereq": ["d03", "d08"], "final": true}
  ]
}
```

배열 순서가 지도의 권장 순서입니다. 던전은 16개이고 `id` 와 `no` 가 겹치지 않아야 하며, `prereq` 에는 목록에 있는 던전만 적습니다. 값은 커리큘럼의 던전 표를 옮겨 적습니다.

### meta.json

```json
{
  "format": 1,
  "skills": ["dict/Map 집계", "다중 기준 정렬", "양끝 포인터"],
  "problems": [
    {"id": "p1", "no": "1-1", "role": "basic"},
    {"id": "p3", "no": "1-3", "role": "mid"},
    {"id": "boss", "no": "1-B", "role": "boss"}
  ]
}
```

| role | 화면 | 뜻 |
|---|---|---|
| `basic` | 기초 | 중급의 준비 문제. 건너뛸 수 있고, 난이도가 높아도 중급을 준비시키는 문제면 기초입니다 |
| `mid` | 중급 | 보스의 부품. 그 던전의 중급을 모두 통과하면 보스가 열립니다 |
| `side` | 선택 | 보스에 쓰이지 않지만 따로 연습할 문제. 보스 잠금과 다음 추천에 들어가지 않습니다 |
| `boss` | 보스 | 던전마다 정확히 한 문제를 두고 목록의 마지막에 둡니다 |

`skills` 에는 기초·중급·선택 문제에서 익히는 기술만 적습니다. 보스에서 처음 나오는 기술을 여기에 적으면 보스를 풀기 전에 지도에 보이므로, 그것은 보스의 `extra.json` 의 `boss_new` 에 적습니다.

### intro.md

커리큘럼의 무대 문단과 그 던전을 그 자리에 둔 이유를 학습자에게 읽히는 말투(~니다)로 두세 문단 씁니다.

## 3. 공개 파일

### problem.json

| 키 | 형식 | 설명 |
|---|---|---|
| `format` | 1 | |
| `title` | 글 | 문제 제목 |
| `tier` | 글 | 커리큘럼의 목표 난이도. 예) `"S3 / Lv2"` |
| `signature.params` | `[{name, type}]` | 두 언어에 같이 쓰는 매개변수 이름과 타입. Python 과 JavaScript 모두의 식별자여야 하고 JavaScript 예약어(`class`, `new`, `arguments` 등)는 쓰지 않습니다 |
| `signature.returns` | 타입 | 반환형 |
| `time_limit_ms` | `{python, javascript}` | 언어별 시간 제한. 모든 정확성·효율성 테스트에 같게 적용합니다 |
| `score` | `{accuracy, efficiency}` | 합이 100. 없으면 역할 기본값(기초 70/30, 중급·선택 60/40, 보스 50/50) |
| `examples` | `[{args, expected}]` | 2~3개. 지문의 입출력 예와 같아야 합니다 |
| `prep` | `[문제 id]` | 지문 위에 보일 준비 문제 |
| `uses` | `[문제 id]` | 보스에만 둡니다. 보스 띠의 "이 보스에 쓰는 문제: 1-2, 1-3 …" 에 쓰고, 어느 문제가 어느 부분을 맡는지는 적지 않습니다 |

타입은 `int`, `str`, `bool`, `list[T]` 만 씁니다(예: `list[list[int]]`). 실수, 딕셔너리, 튜플은 쓰지 않고, 정수는 절댓값이 2^53−1 이하여야 합니다. 시작 코드는 파일로 두지 않고 signature 에서 만들어지며, `answer` 의 처음 값은 반환형을 따릅니다(`int` 는 0, `str` 은 빈 글, `bool` 은 참, 리스트는 빈 리스트). 이 시작 코드가 입출력 예를 모두 통과하면 검증이 실패하므로 예 가운데 하나는 이 값과 다른 답을 갖게 합니다.

### problem.md

제목과 순서는 프로그래머스와 같게 쓰고 문구를 바꾸지 않습니다. 검증 도구가 이 제목으로 절을 찾습니다.

~~~~markdown
## 문제 설명
## 함수
```python
def solution(records: list[str], k: int) -> list[str]:
```
```javascript
function solution(records, k) {}
```
## 제한사항
- 1 ≤ records의 길이 ≤ 200,000
- …
## 입출력 예
| records | k | result |
|---|---|---|
| ["pepper 3", "salt 5"] | 2 | ["pepper", "salt"] |
## 입출력 예 설명
- 예 1: …
~~~~

- 「함수」의 Python 블록과 JavaScript 블록에 적은 매개변수 이름이 signature 와 같아야 합니다. Python 블록은 타입 주석을 붙여도 됩니다.
- 화면은 학생이 고른 언어의 블록만 보여 줍니다. 언어를 적지 않은 코드 블록은 두 언어 모두에 보이고, 힌트와 해설의 코드 블록도 같은 규칙으로 보입니다.
- 입출력 예 표의 머리는 매개변수 이름들 뒤에 `result` 를 붙입니다. 칸에는 JSON 문법으로 값을 적고, 검증 도구가 그 값을 읽어 `examples` 와 대조합니다.
- 「제한사항」의 불릿 번호는 `validate.py` 의 문구가 가리키는 줄 번호가 됩니다(4절).
- 커리큘럼의 정확성·효율성 테스트 목록은 숨은 테스트라서 지문에 넣지 않습니다. 비슷한 실제 문제도 지문에 적지 않습니다.
- 그림이 필요하면 한 줄 전체를 `![캡션](assets/1-1a.gif)` 로 쓰고, 경로는 던전 폴더에서 시작합니다.

## 4. 비밀 파일

문제 폴더마다 아래 파일을 둡니다. 평문 작업본은 커밋하지 않고 봉인합니다.

| 파일 | 내용 |
|---|---|
| `solution.py`, `solution.js` | 기준 풀이. 두 벌 모두 모든 테스트를 통과하고 모든 입력에서 답이 같아야 합니다 |
| `brute.py` | Python 완전 탐색 `solution(...)` 과 `brute_ok(*args)`. brute_ok 가 참인 입력에서만 기준 풀이와 대조합니다. brute_ok 가 없으면 늘 참으로 봅니다 |
| `certify.py` | `certify(args, value)` 가 답이 문제의 정의를 지키는지 직접 확인하고, 어긴 점의 문구나 None 을 돌려줍니다. brute_ok 가 거짓인 입출력 예나 정확성 입력이 있으면 꼭 둡니다. 기준 풀이를 불러 같은 답인지 보는 것은 정의 대조로 치지 않습니다 |
| `alt.py`, `alt.js` | 출제자가 아닌 사람이 지문만 보고 다시 푼 풀이(8절). 출제 중에는 없어도 되고, 서명할 때와 CI 의 서명 확인에서 꼭 있어야 합니다 |
| `gen.py` | 입력 생성기(5절) |
| `validate.py` | 제한사항 검사 |
| `tests.json` | 숨은 정확성·효율성 테스트와 제한사항을 일부러 어긴 입력 |
| `extra.json` | 해설이 열린 뒤나 보스를 통과한 뒤에만 보이는 것 |
| `wrong.json`, `wrong/<이름>.py`, `wrong/<이름>.js` | 알려진 풀이와 그 판정 |
| `hints.md` | `## 1`, `## 2`, `## 3` 절(2~4개). 뒤로 갈수록 더 드러내고, 힌트 1 에서는 풀이 방법의 이름을 말하지 않습니다 |
| `explain.md` | 해설. `## 느린 풀이`, `## 관찰`, `## 풀이`, `## 테스트가 잡는 것`, `## 언어별 차이` 순서로 씁니다 |
| `review.json` | 검토 서명(8절). 던전 폴더 바로 아래에도 하나를 둡니다 |

해설에는 기준 풀이 전체를 넣지 않습니다. 해설 화면이 `solution.py`, `solution.js` 를 붙여 보여 줍니다. 짧은 코드 조각은 넣어도 되고 언어 표시를 붙입니다.

### validate.py

「제한사항」의 불릿마다 검사를 하나씩 둡니다. 어긴 줄이 있으면 `"N번 줄:"` 로 시작하는 문구를, 다 지키면 None 을 돌려줍니다. N 은 불릿의 번호이고, 표준 라이브러리만 쓰며 입력을 바꾸지 않습니다.

```python
"""1-1 장부 정산 제한사항 검사. validate 는 solution 의 인자를 받아 어긴 줄의 문구를, 다 지키면 None 을 돌려줌."""
import re

NAME = re.compile(r"[a-z_]{1,11}\Z")
DESCRIPTIVE = {6: "사전순의 뜻을 설명하는 줄"}  # 검사할 값이 없는 제한사항 줄


def validate(records, k):
    if not 1 <= len(records) <= 200000:
        return "1번 줄: records 의 길이가 %d" % len(records)
    for line in records:
        name, space, qty = line.partition(" ")
        if not NAME.match(name):
            return "3번 줄: 이름 %r" % name
    return None
```

검증 도구는 입출력 예, 리터럴 정확성 인자, 생성한 모든 입력(묶음의 원소 하나하나, 효율성 입력, 스트레스 입력)에 validate 를 돌립니다. 「제한사항」의 불릿마다 `tests.json` 의 `invalid` 가 하나 이상 있거나 그 번호가 `DESCRIPTIVE` 에 있어야 하고, validate 는 각 `invalid` 에 그 번호로 시작하는 문구를 돌려줘야 합니다. 늘 None 을 돌려주는 검사기나 줄 번호가 어긋난 검사는 여기서 걸립니다.

### tests.json

```json
{
  "accuracy": [
    {"id": "one_line", "name": "줄 1개, 품목 1개", "args": [["salt 3"], 1], "expected": ["salt"]},
    {"id": "ties_25", "name": "합이 같은 품목 25개가 섞임", "gen": "ties", "seed": 11, "params": {"m": 25}, "expected": ["…"]},
    {"id": "rand1", "name": "소형 무작위 1", "gen": "small", "seed": 101, "count": 50, "expected_sha": "3f1c…"}
  ],
  "efficiency": [
    {"id": "names_twice", "name": "서로 다른 품목 10만 개가 두 번씩", "gen": "names_twice", "seed": 7, "params": {"n": 200000}, "stress": {"n": 2000}, "expected_sha": "…"}
  ],
  "invalid": [
    {"line": 1, "args": [[], 1]},
    {"line": 3, "args": [["cardamompods 1"], 1]}
  ]
}
```

| 키 | 설명 |
|---|---|
| `id` | 문제 안에서 겹치지 않는 영문 소문자·숫자·밑줄. 입출력 예는 `ex1`, `ex2` … 로 자동으로 붙으므로 그 이름을 쓰지 않습니다 |
| `name` | 커리큘럼의 경계 사례 설명. 해설이 열린 뒤 실패한 정확성 줄에 보입니다 |
| `args` | 리터럴 인자 목록. `gen` 과 같이 쓰지 않습니다 |
| `gen`, `seed`, `params` | 생성기 함수 이름, 시드, 매개변수 |
| `count` | 묶음 테스트. 생성기를 `count` 번 불러 만든 입력으로 solution 을 그만큼 부르고 모두 맞아야 통과합니다. 시간 제한은 호출 하나마다 적용합니다 |
| `expected`, `expected_sha` | 정규 JSON 이 4096자 이하면 리터럴, 넘으면 sha256. 묶음은 결과 목록 전체로 정합니다 |
| `stress` | 효율성 테스트마다 꼭 둡니다. 모양은 그대로 두고 크기만 줄인 생성기 매개변수로, 완전 탐색이 입력 하나를 2초 안에 끝내는 크기(보통 n 이 2,000 안팎)로 정합니다 |
| `depth` | 재귀가 나올 수 있는 문제에서만 씁니다. `limit` 은 재귀 깊이 1,000~1,500, `chain` 은 2×10^5 이상이고, 이 둘이 아닌 테스트는 깊이가 300 이하가 되게 만듭니다 |
| `langs` | 효율성 테스트에만 씁니다. 적은 언어에서만 돌고, 생략하면 두 언어에서 돕니다 |

- 정확성 그룹은 입출력 예 뒤에 `accuracy` 가 이어집니다. 입출력 예는 2~3개, `accuracy` 는 15~25줄로 두고, 그 가운데 `count` 가 없는 이름 붙인 테스트가 9개 이상, `count: 50` 묶음이 6줄이어야 합니다. 커리큘럼의 "소형 무작위 300건"은 `rand1`~`rand6` 여섯 줄로 씁니다.
- 효율성 테스트는 언어마다 3~8줄입니다.
- `depth: "limit"` 테스트가 있으면 `wrong.json` 에 JavaScript `heavy` 항목을 둡니다.
- JavaScript 의 `Math.max(...arr)` 와 `arr.push(...big)` 는 인자가 약 11만 개를 넘으면 멈춥니다. 이런 풀이를 노리는 테스트는 n 을 2×10^5 이상이나 5×10^4 이하로만 만들고 그 사이 크기를 쓰지 않습니다.
- 기대값은 비워 두고 `--fill` 로 채웁니다(7절). 손으로 적은 값은 덮어쓰지 않고, 기준 풀이와 다르면 실패로 알립니다.

### wrong.json

```json
{
  "reverse_sort": {"langs": ["python"], "expect": "wrong", "on": ["ex2"], "why": "동점 이름 순서까지 뒤집힘"},
  "rescan": {"langs": ["python", "javascript"], "expect": "timeout", "on": ["names_twice"], "why": "품목마다 장부를 다시 훑음 O(n·d)"},
  "seen_list": {"langs": ["python", "javascript"], "expect": "timeout", "on": ["all_distinct"], "gray": {"javascript": ["names_twice"]}, "why": "본 이름 목록을 리스트에서 찾음"},
  "locale_compare": {"langs": ["javascript"], "expect": "pass", "why": "localeCompare 로 이름을 비교함"}
}
```

| 키 | 설명 |
|---|---|
| `langs` | 그 풀이가 실제로 실패하는(또는 통과해야 하는) 언어. 적은 언어마다 `wrong/<이름>.py`·`.js` 를 둡니다 |
| `expect` | `wrong`(틀린 답), `timeout`, `runtime`, `fail`(통과만 아니면 됨), `pass`(모든 테스트 통과). 첫 테스트를 불러오다 멈추는 파일(문법 오류, `solution` 없음, 맨 위 코드의 예외)은 채점 화면처럼 실행 전 오류로 보므로 `runtime` 이나 `wrong` 에 맞지 않습니다 |
| `on` | 그 판정이 나와야 할 테스트 id. `pass` 에는 적지 않습니다 |
| `gray` | `timeout` 항목에만 둡니다. `on` 밖의 효율성 테스트 가운데 회색 지대(6절)에 걸리는 것을 언어별로 적습니다 |
| `style` | 재귀 방식. 아래 표의 판정을 따릅니다 |
| `why` | 왜 그 판정인지 한 줄로 적습니다 |

커리큘럼의 흔한 오답과 "알려진 다른 풀이와 판정" 표의 풀이를 모두 넣습니다. 다시 푼 풀이 alt 는 적지 않아도 `pass` 로 보고, 재풀이자가 느린 다른 방법으로 풀었으면 `alt` 라는 이름으로 `timeout` 항목을 적습니다. 그 항목의 파일은 `wrong/` 이 아니라 문제 폴더의 `alt.py`, `alt.js` 입니다.

트리, 그래프, DP 처럼 재귀로 풀기 쉬운 문제에는 재귀 방식 항목을 모두 둡니다. 기대 판정은 테스트의 `depth` 와 `style` 로 정해지고 Python 판이나 Node 판마다 다른 값을 두지 않습니다.

| 재귀 깊이 | `iterative` | `plain`, `cache_default`, `builtin` | `raised`, `raised_small`, `cache` | JS `recursive`, `heavy` |
|---|---|---|---|---|
| 300 이하(depth 없음) | 통과 | 통과 | 통과 | 통과 |
| 1,000~1,500(`limit`) | 통과 | 런타임 에러 | 통과 | 통과 |
| 2×10^5 이상(`chain`) | 통과 | 런타임 에러 | 런타임 에러 | 런타임 에러 |

Python 의 `plain` 은 한도를 그대로 둔 재귀, `raised` 는 `sys.setrecursionlimit(10**6)`, `raised_small` 은 `@cache` 재귀에 깊이의 두 배보다 작은 한도, `cache` 는 `@cache`·`@lru_cache` 재귀에 한도 10^6, `cache_default` 는 한도를 그대로 둔 `@cache` 재귀, `builtin` 은 `max(f(m) for m in …)` 처럼 내장 함수를 거치는 재귀, `iterative` 는 반복문입니다. JavaScript 의 `recursive` 는 보통 재귀, `heavy` 는 인자 7개와 지역 변수 8개, 배열 구조 분해가 있는 무거운 프레임 재귀입니다. 채점기는 1,000 보다 큰 재귀 한도를 모두 10,000 으로 맞춥니다.

### extra.json

```json
{
  "parts": [{"text": "배열을 한 번 훑으며 값을 더함", "from": ["p1"]}],
  "boss_new": "정렬한 뒤 앞에서 k개를 골라 더함",
  "similar": [{"site": "boj", "title": "A+B", "id": 1000, "fit": "easy"}]
}
```

`parts`(합성표)와 `boss_new` 는 보스에 꼭 둡니다. `similar` 는 해설 끝 "더 풀어 볼 문제"에 보이고, `site` 는 `boj` 나 `programmers` 를 씁니다. BOJ 는 `id` 로 주소를 만들고, 프로그래머스는 주소를 확인했을 때만 `url` 을 적습니다.

## 5. 입력 생성기

`gen.py` 의 함수는 `(rng, **params)` 를 받아 solution 의 인자 목록 하나를 돌려줍니다.

```python
"""1-1 장부 정산 입력 생성기. 함수는 (rng, **params) 를 받아 solution 의 인자 목록 하나를 돌려줌."""
from journey.gen import distinct_words


def small(rng):
    names = distinct_words(rng, rng.between(1, 5), 1, 3, alphabet="ab_")
    records = ["%s %d" % (rng.pick(names), rng.between(1, 10)) for _ in range(rng.between(1, 8))]
    return [records, rng.between(1, 6)]
```

`journey.gen` 에는 splitmix64 난수 `Rng(seed)` 와 `next64`, `below(n)`, `between(lo, hi)`, `chance(num, den)`, `pick`, `shuffle`, `sample`, 그리고 `word`, `distinct_words` 가 있습니다. 묶음 테스트는 `Rng(seed)` 하나로 생성기를 `count` 번 연달아 부릅니다.

같은 명세에서는 어느 컴퓨터, 어느 Python 판(3.10~3.14), 어느 프로세스에서나 같은 입력이 나와야 합니다. 큰 테스트의 기대값은 입력에 묶인 해시라서, 입력이 컴퓨터마다 달라지면 모든 학생에게 그 테스트가 오답으로 보입니다. 그래서 생성기에서는 아래 규칙을 지킵니다.

- import 는 `journey.gen` 만 씁니다. `random` 모듈은 판이 바뀌면 `randint`, `shuffle` 같은 함수의 결과가 달라질 수 있고, `time` 과 `os.urandom` 은 돌릴 때마다 값이 바뀝니다. 필요한 도우미는 `journey.gen` 에 더합니다.
- `set`, `frozenset`, `hash()` 와 집합 표현을 쓰지 않습니다. 문자열 집합의 순회 순서는 프로세스마다 달라질 수 있어서, 겹침을 막을 때는 넣은 순서를 지키는 dict 를 씁니다.
- `__import__`, `eval`, `exec`, `compile`, `open` 을 부르지 않습니다.

검증 도구가 gen.py 를 읽어 위 규칙을 어긴 곳을 찾고, 모든 생성 테스트를 캐시 없이 서로 다른 두 프로세스에서 다시 만들어 같은지 봅니다. 학생 컴퓨터는 만든 입력을 `~/.rokey-study/journey-cache/` 에 모아 두고 다시 씁니다(한도 1GB).

## 6. 시간 제한과 회색 지대

시간 제한은 기준 컴퓨터(스터디장 Mac)의 Python 3.12·3.14 와 Node 20·22 에서 잰 값으로 정합니다.

- 시간 제한은 `max(기본값, 16.5 × 통과시킬 풀이 가운데 가장 느린 시간)` 을 0.5초 단위로 올린 값입니다. 기본값은 Python 2초, JavaScript 1초입니다. 통과시킬 풀이는 기준 풀이, `pass` 항목, alt 이고, 가장 느린 시간은 잰 모든 판에서 가장 큰 값을 씁니다.
- 통과시킬 풀이는 잰 모든 판에서 그 언어의 모든 효율성 테스트를 제한의 1/15 안에 끝내야 합니다. 그러면 4배 느린 노트북에서도 통과합니다.
- `timeout` 항목은 빠른 쪽 판(Python 3.14, Node 22)에서 `on` 의 테스트마다 제한의 10배를 넘겨야 합니다. 그러면 4배 빠른 컴퓨터에서도 실패합니다. `on` 밖의 효율성 테스트는 1/15 안에 끝나거나 10배를 넘어야 하고, 그 사이에 걸리는 테스트는 `gray` 에 적습니다. 그 테스트의 점수만 컴퓨터마다 다를 수 있고, 문제를 통과하는지는 어느 컴퓨터에서나 같습니다.
- 어느 쪽에도 들지 않는 풀이가 있으면 테스트 크기나 시간 제한을 바꾸거나 `langs` 로 한 언어에만 도는 큰 테스트를 더합니다. 시간 제한을 바꿨으면 16.5배 규칙도 다시 봅니다.

`--timing` 은 기준 컴퓨터에서만 판정합니다. CI 러너는 기준 컴퓨터가 아니라서 이 규칙을 잴 수 없습니다.

## 7. 명령

### 봉인

```bash
python tools/journey_seal.py unseal d01          # sealed.json → 평문 작업본
python tools/journey_seal.py seal d01            # 평문 작업본 → sealed.json, 평문 삭제(--keep 이면 남김)
python tools/journey_seal.py check                # 봉인되지 않은 평문이나 풀리지 않는 sealed.json 이 있으면 실패
python tools/journey_seal.py brief d01/p3 --out ~/brief_d01_p3
```

- seal 은 기존 sealed.json 의 내용과 평문을 합쳐 다시 묶고, 같은 파일이 둘 다 있으면 평문을 씁니다. 폴더가 사라진 문제의 항목은 버립니다.
- 봉인한 비밀 파일을 지울 때는 unseal 로 모두 꺼낸 뒤 그 파일과 `sealed.json` 을 지우고 seal 합니다. sealed.json 을 남겨 두면 지운 파일이 묶음에 다시 들어갑니다.
- check 는 CI 의 필수 검사(문제 은행 검증)에서도 돕니다. 커밋 전에 한 번 돌려 평문이 남지 않았는지 봅니다.
- brief 는 다시 풀 사람에게 줄 공개본을 만듭니다. `problem.md`, problem.json 의 `title`·`signature`·`time_limit_ms`·`examples`, 두 언어 시작 코드(`alt.py`, `alt.js`)만 들어갑니다. 저장소 안의 폴더에는 만들지 않습니다.

### 검증

```bash
python tools/verify_journey.py d01               # 던전 하나를 모두 검증(대상을 적지 않으면 출제된 던전 전부)
python tools/verify_journey.py d01/p3            # 문제 하나
python tools/verify_journey.py d01/p3 --fill     # 비어 있는 기대값을 solution.py 의 답으로 채움
python tools/verify_journey.py d01 --timing --pythons PY312,PY314 --nodes NODE20,NODE22
```

`PY312` 같은 자리에는 그 판의 실행 파일 경로를 적고, 빠른 판을 마지막에 둡니다. 실패가 하나라도 있으면 1 로 끝납니다. 문제마다 아래 단계를 차례로 봅니다.

| 단계 | 내용 |
|---|---|
| 1 형식 | index.json, meta.json, problem.json 의 키와 타입. 점수 합 100, 두 언어 시간 제한, 매개변수 이름, `prep`·`uses`·`parts` 의 문제 id |
| 2 비밀 파일 | 필요한 파일이 모두 있는지(alt.py, alt.js 는 `--sign` 과 `--require-review` 에서만), hints.md 의 절 수, gen.py 의 함수, wrong.json 의 언어별 파일, 보스의 `parts`·`boss_new`, sealed.json 300KB 이하 |
| 3 지문 | 제목 순서, 「함수」 블록의 매개변수 이름, 입출력 예 표와 examples |
| 4 테스트 구성 | 줄 수(이름 붙인 테스트와 묶음을 따로 셈), id, 인자와 기대값의 타입, `stress`, `depth`, `langs` |
| 5 제한사항 검사 | validate 가 입출력 예와 리터럴 인자를 통과시키는지, `invalid` 와 줄 번호 |
| 6 생성 결정성 | gen.py 의 import 와 금지 호출, 두 프로세스에서 같은 입력, 생성한 입력의 타입과 제한사항 |
| 7 기준 풀이 | solution.py, solution.js 가 모든 테스트를 통과하고 피크 메모리 256MB 미만 |
| 8 완전 탐색 | brute_ok 가 참인 입력은 brute.py 의 답과 대조(입력 하나에 60초), 거짓인 입력은 certify 로 정의 대조 |
| 9 스트레스 대조 | 효율성 테스트마다 `stress` 크기로 20개 입력을 만들어 brute.py, 기준 풀이 두 벌, alt 두 벌(있을 때)의 답이 모두 같은지 봅니다. 어긋나면 가장 짧은 입력과 답들을 보여 줍니다 |
| 10 다시 푼 풀이 | alt.py, alt.js 가 있으면 모든 테스트에서 기대값과 같은 답(시간 제한 60초) |
| 11 시작 코드 | 시작 코드가 입출력 예 가운데 하나 이상에서 실패 |
| 12 알려진 풀이 | wrong.json 항목마다 `on` 의 테스트에서 적은 판정, `pass` 는 모든 테스트 통과 |
| 13 재귀 방식 | `style` 항목의 판정이 4절 wrong.json 의 재귀 표와 같은지 |
| 14 그림 | 지문·힌트·해설이 가리키는 그림이 있는지, 크기·프레임 한도, 아무도 가리키지 않는 그림(경고) |

그림 한도는 GIF 하나 300KB, PNG 하나 200KB, 프레임 12개, 프레임 시간 800~2500ms, 파일 폭 1120px, 던전 assets 합계 2.5MB 입니다.

아래 옵션으로 돌릴 단계나 대상을 바꿉니다.

- `--lang python` 이나 `--lang javascript`: 그 언어의 단계만 봅니다. JavaScript 는 7, 9, 10, 12, 13 단계의 JS 쪽만 돌고, 스트레스 대조의 기준은 solution.py 의 답으로 둡니다. Node.js 20 이상이 없으면 JavaScript 단계가 실패하므로 Node 가 없는 컴퓨터에서는 `--lang python` 을 씁니다.
- `--fill`: 평문 tests.json 의 빈 기대값을 채우고 다른 단계는 돌리지 않습니다.
- `--timing`: 6절의 규칙으로 시간만 잽니다. 효율성 테스트를 하나씩 3번 돌려 가운데 값을 쓰고, 제한의 10배에서 끊습니다. 표는 한 줄에 문제, 언어, 판, 풀이, 테스트, ms, 제한, 배수, 판정을 찍습니다. 판정 칸에는 어디서나 통과, 어디서나 실패, 회색(gray), 회색(적지 않음)이 찍히고, 적지 않은 회색이 있으면 실패합니다. problem.json 의 제한이 16.5배 규칙의 값보다 작으면 경고를 찍습니다.
- `--timing --report`: 판정하지 않고 통과시킬 풀이의 시간 표만 찍습니다. 팀원 노트북처럼 기준 컴퓨터가 아닌 곳에서 기준 풀이가 제한의 몇 분의 일에 끝나는지 볼 때 씁니다.
- `--styles`: 13단계만 돌립니다. CI 가 Python 3.10~3.14 마다 돌립니다.
- `--alt DIR`: 아직 문제 폴더에 넣지 않은 다시 푼 풀이(DIR 의 alt.py, alt.js)로 9·10단계를 돌립니다. 문제 하나에만 씁니다.
- `--changed REF`: REF 와 갈라진 뒤 바뀐 파일이 있는 던전만 봅니다. `journey/`, `study.py`, `tools/verify_journey.py` 가 바뀌었으면 모든 던전을 보고, `index.json` 만 바뀌었으면 index.json 의 형식만 봅니다.
- `--sign`, `--require-review`: 8절의 서명과 서명 확인입니다.
- `--plan REF`: 검증하지 않고 CI 가 쓸 `engine=…`, `styles=…` 두 줄만 찍습니다.
- `--bank DIR`: 다른 은행 폴더를 봅니다(테스트용 고정 은행 등). `--jobs N`: 동시에 돌릴 자식 프로세스 수를 정합니다.

생성 입력은 학생 컴퓨터와 같은 캐시를 씁니다. 6단계의 생성 입력과 9단계의 스트레스 입력은 돌릴 때마다 캐시 없이 새로 만듭니다. 캐시 위치는 환경 변수 `STUDY_JOURNEY_CACHE` 로 바꿀 수 있습니다.

## 8. 교차 검증

자기 글과 답을 쓴 사람이 직접 확인하면 같은 착각이 지문, 기준 풀이, 기대값에 함께 들어갑니다. 그래서 출제, 다시 풀기, 검토를 서로 다른 사람이 맡습니다.

| 역할 | 하는 일 |
|---|---|
| 출제자 | 지문, 기준 풀이 두 벌, 완전 탐색, 생성기, 제한사항 검사, 테스트, 알려진 풀이, 힌트, 해설, 그림을 씁니다 |
| 재풀이자 | 지문만 보고 Python·JS 두 벌을 새로 풉니다 |
| 검토자 | 모든 파일을 읽고 아래 확인 목록을 봅니다 |

출제자는 재풀이자나 검토자를 겸하지 않습니다. 재풀이자와 검토자는 한 사람이 겸해도 되고, 그때는 다시 풀기를 끝낸 뒤에 비밀 파일을 엽니다.

### 순서

1. 출제자가 평문 작업본을 쓰고 `verify_journey.py d01 --fill`, `verify_journey.py d01`, 기준 컴퓨터에서 `--timing` 까지 통과시킵니다. alt.py, alt.js 는 5번에서 들어오므로 이때는 없어도 통과합니다.
2. 출제자가 문제마다 `journey_seal.py brief d01/p3 --out DIR` 로 공개본을 만들어 재풀이자에게 넘깁니다. 재풀이자는 비밀 파일과 커리큘럼의 그 문제 절(기준 풀이, 힌트, 흔한 오답이 적혀 있음)을 보지 않습니다.
3. 재풀이자는 공개본의 입출력 예로 자기 풀이를 돌려 본 뒤 `alt.py`, `alt.js` 를 넘깁니다.
4. `verify_journey.py d01/p3 --alt DIR` 로 모든 테스트와 스트레스 입력에서 기준 풀이와 대조합니다. 답이 다르면 출제자와 재풀이자가 그 입력과 답을 같이 보고 원인을 정합니다. 지문이 두 가지로 읽히면 지문을 고치고 재풀이자가 고친 지문만 보고 다시 판단합니다. 기준 풀이나 기대값이 틀렸으면 기준 풀이를 고치고 `--fill` 로 기대값을 다시 채웁니다. 재풀이가 틀렸으면 재풀이자가 고칩니다. 어느 쪽이었는지 서명할 때 `--finding` 으로 남깁니다.
5. 답이 모두 같으면 alt.py, alt.js 를 문제 폴더에 넣습니다. 이후 검증이 매번 다시 대조하므로, 나중에 테스트를 바꿔도 기준 풀이 두 벌과 다시 푼 풀이가 계속 맞물립니다.
6. 검토자가 아래 확인 목록을 봅니다. 고칠 곳은 검토자가 직접 고치지 않고 출제자에게 돌려보내며, 출제자가 고친 뒤 다시 봅니다.
7. 검토가 끝나면 검토자가 서명합니다.

   ```bash
   python tools/verify_journey.py d01/p3 --sign --writer "출제 1" --resolver "재풀이 2" --reviewer "검토 2" --finding "예 2 의 동점 설명이 두 가지로 읽혀 지문을 고침"
   python tools/verify_journey.py d01 --sign --writer "출제 1" --resolver "재풀이 2" --reviewer "검토 2"
   ```

   문제를 적으면 그 문제의 review.json 을, 던전을 적으면 던전 폴더의 review.json(intro.md, meta.json, assets 의 그림)을 씁니다. 서명 전에 그 대상을 검증하고, 실패가 있으면 서명하지 않습니다. 이름은 스터디장이 정하는 꼬리표(GitHub ID 나 "출제 1" 같은 이름)이고 저장소에 남습니다. 다시 서명하면 전에 남긴 findings 를 이어 씁니다.
8. 재풀이자가 alt.py, alt.js, review.json 을 출제자에게 넘기고, 출제자가 `journey_seal.py seal d01` 과 `check` 를 돌린 뒤 커밋합니다. 봉인은 파일 내용을 바꾸지 않아 서명의 해시가 맞습니다.

review.json 은 아래 꼴입니다. `files` 는 review.json 을 뺀 그 문제의 공개·비밀 파일 전부의 sha256 입니다.

```json
{
 "format": 1,
 "writer": "출제 1", "resolver": "재풀이 2", "reviewer": "검토 2",
 "files": {"problem.json": "<sha256>", "problem.md": "<sha256>", "solution.py": "<sha256>"},
 "findings": ["예 2 의 동점 설명이 두 가지로 읽혀 지문을 고침"]
}
```

`--require-review` 는 review.json 이 없거나, writer 가 resolver·reviewer 와 같거나, 서명 뒤에 바뀐 파일이 있으면 실패하고 "검토 뒤에 바뀐 파일: p3/explain.md" 처럼 바뀐 파일을 알려 줍니다. 서명 뒤에 한 글자라도 고쳤으면 다시 검토를 받고 서명합니다. CI 의 여정 문제 검증이 이 검사를 하고, 로컬 검증은 하지 않으므로 출제 중에는 막히지 않습니다.

### 검토자 확인 목록

- 지문만 읽어도 답이 하나로 정해집니다(4번에서 고친 모호함 포함).
- 학습자에게 보이는 글(지문, 힌트, 해설, intro.md)이 용어를 처음 쓰기 전에 소개하고, 예시가 바로 앞 문장이 말한 것을 보여 주며, 앞뒤와 상관없는 장면으로 건너뛰지 않습니다.
- 「제한사항」 줄마다 validate 의 검사와 `invalid` 가 있고, 입출력 예가 제한사항을 지킵니다.
- 힌트는 1에서 3으로 갈수록 더 드러내고, 힌트 1 은 풀이 방법의 이름을 말하지 않습니다.
- 해설의 알고리즘과 복잡도가 기준 풀이와 같고, 해설에 적은 시간 수치가 `--timing` 표와 맞습니다.
- 비슷한 실제 문제와 전제가 겹치지 않습니다. 원문의 예시 값, 반환 형식, 동점 규칙을 그대로 쓰지 않았고 커리큘럼이 정한 변형이 지문에 들어 있습니다.
- 커리큘럼의 흔한 오답과 "알려진 다른 풀이와 판정" 표의 풀이가 모두 wrong.json 에 있고, `langs` 가 실제로 실패하는 언어와 맞으며, 표의 "`gray`에 적는 테스트"가 `gray` 에 있습니다.
- 보스에서 처음 나오는 기술이 meta.json 의 `skills` 에 없고 보스 extra.json 의 `boss_new` 에만 있습니다.
- certify.py 가 기준 풀이와 다른 방법으로 정의를 확인합니다.
- `python tools/check_style.py` 가 지문·힌트·해설·intro.md 를 통과시킵니다.

README, docs, 화면 문구처럼 답이 없는 글은 쓴 사람이 아닌 사람이 PR 에서 읽고 확인합니다.

## 9. CI

- 문제 은행 검증(필수 검사)은 `journey_seal.py check` 로 평문 비밀 파일이 올라오지 않았는지 봅니다. 이 작업의 단위 테스트는 `STUDY_LEAN_CI` 를 켜고 돌아서, 자식 프로세스를 띄우고 시간을 기다리는 여정 테스트를 건너뜁니다.
- 알고리즘 여행 검증(`journey.yml`, 필수 검사 아님)은 `dungeons/`, `journey/`, 여정 도구와 테스트가 바뀐 PR 에서만 돕니다. 여정 실행기 작업은 Python 3.10~3.14 마다 단위 테스트와 `--styles` 를 돌리고, 여정 문제 검증 작업은 Node 24 로 `--require-review` 검증을, 여정 JS 검증 작업은 Node 22 로 `--lang javascript` 를 돌립니다. 던전 PR 에서는 `--changed` 로 바뀐 던전만 봅니다.
- 던전 4~16 은 던전마다 `dungeons/d0N/**` 와 그림 스크립트 `tools/journey_art/d0N.py` 만 바꾸는 PR 하나로 올리고, 그 PR 에 검토 서명이 있어야 알고리즘 여행 검증을 통과합니다.
