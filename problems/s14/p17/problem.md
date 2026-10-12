# p17. 대문자 약어 뽑기 (빈칸 채우기 · 4점)

한 줄을 입력받아, 영문 대문자가 2개 이상 이어진 덩어리(예: `NASA`, `AI`)를 모두 찾아 리스트로 출력하는
프로그램입니다. 빈칸(`____`) 1곳을 채워 프로그램을 완성하세요.

```python
import re

text = input()
words = re.findall(____, text)   # 영문 대문자가 2개 이상 이어진 덩어리
print(words)
```

- 빈칸에는 정규식 패턴 문자열이 들어갑니다.
- 대문자가 1개뿐인 곳(`Google` 의 `G`)은 뽑지 않습니다. 소문자, 숫자, 밑줄은 덩어리에 포함되지 않습니다.
- 대문자가 몇 개 이어지든 한 덩어리로 뽑습니다. `ABCDEF` 는 `['ABCDEF']` 입니다.
- 매치되는 것이 없으면 `[]` 를 출력합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 입출력 예

| 입력 | 출력 |
|---|---|
| `NASA is working on AI projects with IBM and Google.` | `['NASA', 'AI', 'IBM']` |
| `I am a Robot` | `[]` |
| `USA2024 and KOREA_ROK` | `['USA', 'KOREA', 'ROK']` |
