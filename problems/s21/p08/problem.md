# p08. 날씨 응답 요약하기 (반환값 · 8점)

날씨 API 가 돌려준 도시별 날씨 정보가 JSON 문자열 `json_string` 으로 주어집니다. 이 문자열은 JSON 배열이고, 원소 하나가 도시 하나의 정보입니다.

```json
[
    {
        "name": "Seoul",
        "weather": [{"description": "clear sky"}],
        "main": {"temp_max": 11, "humidity": 68}
    },
    {
        "name": "Busan",
        "weather": [{"description": "few clouds"}, {"description": "mist"}],
        "main": {"temp_max": 15, "humidity": 80}
    }
]
```

아래 네 가지를 담은 딕셔너리를 만들고, 그 딕셔너리를 `json.dumps()` 로 변환한 **JSON 문자열**을 **반환(return)** 하는 `solution` 함수를 완성하세요. 키는 아래 순서대로 넣습니다.

| 키 | 값 |
|---|---|
| `"count"` | 도시의 수 |
| `"hottest"` | 최고 기온(`temp_max`)이 가장 높은 도시의 이름. 최고 기온이 같은 도시가 여럿이면 먼저 나온 도시 |
| `"weather"` | 그 도시의 `weather` 리스트에서 첫 번째 원소의 `description` |
| `"humid"` | 습도(`humidity`)가 70 이상인 도시 이름의 리스트(입력에 나온 순서) |

- `json.dumps()` 에는 딕셔너리만 넘깁니다(`indent` 를 주지 않습니다).
- 필요한 모듈은 직접 `import` 합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줘야 합니다.

## 제한 사항
- 도시는 1개 이상 10개 이하입니다.
- `temp_max` 와 `humidity` 는 정수이고, `temp_max` 는 음수일 수 있습니다.
- 도시마다 `weather` 리스트에는 원소가 1개 이상 있습니다.
- 도시 이름과 날씨 설명은 영어로만 되어 있습니다.

## 입출력 예

| json_string | 반환값 |
|---|---|
| 위의 예(Seoul, Busan)를 한 줄로 적은 문자열 | `'{"count": 2, "hottest": "Busan", "weather": "few clouds", "humid": ["Busan"]}'` |
| `'[{"name": "Jeju", "weather": [{"description": "rain"}], "main": {"temp_max": 20, "humidity": 70}}]'` | `'{"count": 1, "hottest": "Jeju", "weather": "rain", "humid": ["Jeju"]}'` |

- 반환값은 문자열입니다. 큰따옴표, 쉼표와 콜론 뒤의 공백까지 `json.dumps()` 가 만든 모양과 같아야 합니다.
