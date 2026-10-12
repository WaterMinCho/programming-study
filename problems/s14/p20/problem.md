# p20. Python 이 들어 있는 문장 (반환값 · 8점)

문자열 `text` 는 마침표(`.`)로 끝나는 문장이 여러 개 이어진 글입니다. 이 가운데 `Python` 이라는 글자가
들어 있는 문장만 골라, 나온 순서대로 리스트로 **반환(return)** 하는 `solution` 함수를 완성하세요.

- 문장은 끝의 마침표까지 포함하고, 문장 앞뒤의 공백은 뺍니다. 두 번째 문장부터는 앞에 공백이 있으므로 `' Python is great for AI.'` 가 아니라 `'Python is great for AI.'` 로 담습니다.
- 대소문자를 구별합니다. 소문자 `python` 만 있는 문장은 고르지 않습니다.
- `Pythonic`, `MicroPython` 처럼 다른 단어의 일부로 들어 있어도 고릅니다.
- 마침표는 문장의 끝에만 나오고, 모든 문장은 마침표로 끝납니다.
- 해당하는 문장이 없으면 빈 리스트 `[]` 를 반환합니다.
- 함수 이름과 매개변수는 바꾸지 않습니다. `print` 가 아니라 `return` 으로 돌려줍니다.

## 입출력 예

| text | 반환값 |
|---|---|
| `"I love Python. Java is also popular. Python is great for AI."` | `['I love Python.', 'Python is great for AI.']` |
| `"Java only. C too."` | `[]` |
| `"python is lower. Python is upper."` | `['Python is upper.']` |
