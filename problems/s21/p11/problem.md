# p11. JSON 프로필 고쳐서 돌려주기 (반환값 · 6점)

사람 한 명의 정보가 JSON 문자열 `json_string` 으로 주어집니다.

```json
{"name": "Alice", "age": 25, "city": "Seoul", "skills": ["Python", "Django"]}
```

이 문자열을 파이썬 딕셔너리로 바꿔 아래 두 가지를 고친 뒤, 그 딕셔너리를 `json.dumps()` 로 변환한 **JSON 문자열**을 **반환(return)** 하는 `solution` 함수를 완성하세요.

1. `"age"` 의 값을 1 늘립니다.
2. `"skills"` 리스트에 `skill` 이 없으면 맨 뒤에 추가합니다. 이미 있으면 추가하지 않습니다.

- 나머지 키와 값, 키의 순서는 바꾸지 않습니다.
- `json.dumps()` 에는 딕셔너리만 넘깁니다(`indent` 를 주지 않습니다).
- 필요한 모듈은 직접 `import` 합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줘야 합니다.

## 제한 사항
- `json_string` 은 올바른 JSON 객체가 적힌 문자열이고, `"age"`(정수)와 `"skills"`(문자열의 배열) 키가 항상 들어 있습니다. `"skills"` 는 빈 배열일 수 있습니다.
- 그 밖의 키는 있을 수도 있고 없을 수도 있으며, 키가 적힌 순서도 정해져 있지 않습니다.
- 문자열은 모두 영어로만 되어 있고, 대문자와 소문자는 다른 글자로 봅니다.

## 입출력 예

| json_string | skill | 반환값 |
|---|---|---|
| `'{"name": "Alice", "age": 25, "city": "Seoul", "skills": ["Python", "Django"]}'` | `"Flask"` | `'{"name": "Alice", "age": 26, "city": "Seoul", "skills": ["Python", "Django", "Flask"]}'` |
| `'{"name": "Alice", "age": 25, "city": "Seoul", "skills": ["Python", "Django"]}'` | `"Python"` | `'{"name": "Alice", "age": 26, "city": "Seoul", "skills": ["Python", "Django"]}'` |
| `'{"name": "Bob", "age": 30, "skills": []}'` | `"Java"` | `'{"name": "Bob", "age": 31, "skills": ["Java"]}'` |

- 반환값은 문자열입니다. 큰따옴표, 쉼표와 콜론 뒤의 공백까지 `json.dumps()` 가 만든 모양과 같아야 합니다.
