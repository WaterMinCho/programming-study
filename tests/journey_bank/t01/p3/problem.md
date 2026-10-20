## 문제 설명

마을 물통에는 알파벳 소문자로 된 이름표가 붙어 있습니다. 관리인은 이름표를 거울에 비춰 읽는 놀이를 합니다.

이름 name이 주어질 때, 글자 순서를 거꾸로 뒤집은 문자열을 return 하도록 solution 함수를 완성해 주세요.

## 함수

```python
def solution(name: str) -> str:
```

```javascript
function solution(name) {}
```

## 제한사항

- name의 길이는 1 이상 100,000 이하입니다.
- name은 알파벳 소문자로만 이루어져 있습니다.

## 입출력 예

| name | result |
|---|---|
| "abc" | "cba" |
| "level" | "level" |
| "ab" | "ba" |

## 입출력 예 설명

- 예 1: a, b, c를 거꾸로 놓으면 "cba"입니다.
- 예 2: "level"은 뒤집어도 같은 이름입니다.
- 예 3: 두 글자를 서로 바꾸면 "ba"입니다.
