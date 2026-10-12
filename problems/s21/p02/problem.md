# p02. JSON 문자열에서 값 꺼내기 (반환값 · 4점)

JSON 객체가 적힌 문자열 `json_string` 과 키 `key` 가 주어집니다.
`json_string` 을 파이썬 딕셔너리로 바꾼 뒤, `key` 에 해당하는 값을 **반환(return)** 하는 `solution` 함수를 완성하세요.

- `key` 가 딕셔너리에 없으면 `None` 을 반환합니다.
- 값의 자료형은 변환된 그대로 돌려줍니다. JSON 의 숫자 `25` 는 정수 `25`, JSON 의 배열은 리스트입니다.
- 필요한 모듈은 직접 `import` 합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줘야 합니다.

## 제한 사항
- `json_string` 은 올바른 JSON 객체(`{ ... }`)가 적힌 문자열이고, `key` 도 문자열입니다.

## 입출력 예

| json_string | key | 반환값 |
|---|---|---|
| `'{"name": "Alice", "age": 25, "city": "Seoul"}'` | `"name"` | `"Alice"` |
| `'{"name": "Alice", "age": 25, "city": "Seoul"}'` | `"age"` | `25` |
| `'{"name": "Alice", "age": 25, "city": "Seoul"}'` | `"job"` | `None` |
| `'{"skills": ["Python", "Django"], "level": 3}'` | `"skills"` | `["Python", "Django"]` |
