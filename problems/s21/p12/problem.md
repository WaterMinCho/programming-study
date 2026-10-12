# p12. JSON 파일 읽어 출력하기 (출력 · 6점)

현재 폴더의 `sample.json` 파일에는 사람 한 명의 정보가 JSON 형식으로 저장되어 있습니다. 이 파일을 `json` 모듈로 읽어 아래 네 줄을 출력하는 프로그램을 작성하세요.

- 첫째 줄: `이름: ` 뒤에 `"name"` 의 값
- 둘째 줄: `나이: ` 뒤에 `"age"` 의 값
- 셋째 줄: `도시: ` 뒤에 `"city"` 의 값
- 넷째 줄: `기술 N개: ` 뒤에 `"skills"` 의 값들을 쉼표와 공백(`, `)으로 이어 붙인 것. `N` 은 `"skills"` 에 든 값의 개수입니다.
- `sample.json` 은 UTF-8 로 저장되어 있습니다. 열 때 `encoding="utf-8"` 을 지정합니다.

## 제한 사항
- `sample.json` 에는 `"name"`, `"age"`, `"city"`, `"skills"` 키가 항상 들어 있습니다. 그 밖의 키가 더 들어 있을 수 있고, 키가 적힌 순서는 정해져 있지 않습니다.
- `"age"` 는 정수이고, `"skills"` 는 문자열이 1개 이상 든 배열입니다.
- 파일은 한 줄로 적혀 있을 수도 있고, 여러 줄로 들여 써 있을 수도 있습니다.

## 입출력 예

`sample.json` 의 내용이 다음과 같을 때

```json
{
    "name": "Alice",
    "age": 25,
    "city": "Seoul",
    "skills": ["Python", "Django", "Machine Learning"]
}
```

출력

```
이름: Alice
나이: 25
도시: Seoul
기술 3개: Python, Django, Machine Learning
```

`sample.json` 의 내용이 다음과 같을 때

```json
{"name": "Bob", "age": 30, "city": "Busan", "skills": ["Java"]}
```

출력

```
이름: Bob
나이: 30
도시: Busan
기술 1개: Java
```

- 출력은 글자 하나까지 같아야 합니다(띄어쓰기 포함).
