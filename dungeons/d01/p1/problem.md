## 문제 설명

향신료 시장 상인회는 하루 동안의 거래를 장부에 한 줄씩 적습니다. 한 줄은 "품목 수량" 꼴의 문자열이고, 같은 품목이 여러 줄에 나뉘어 적힐 수 있습니다. 상인회장은 수량 합이 큰 품목부터 k개를 골라 내일 진열대 앞자리에 두려고 합니다.

장부 records와 정수 k가 주어질 때, 품목별 수량 합이 큰 순서로 품목 이름 k개를 담은 배열을 return 하도록 solution 함수를 완성해 주세요. 수량 합이 같으면 이름이 사전순으로 앞선 품목이 먼저 옵니다. 품목 수가 k보다 적으면 모든 품목을 같은 규칙으로 담습니다.

## 함수

```python
def solution(records: list[str], k: int) -> list[str]:
```

```javascript
function solution(records, k) {}
```

## 제한사항

- 1 ≤ records의 길이 ≤ 200,000
- records의 원소는 "이름 수량" 꼴이며, 이름과 수량 사이에는 공백이 하나 있습니다.
- 이름은 알파벳 소문자와 밑줄(`_`)로만 이루어지고 길이는 1 이상 11 이하입니다.
- 수량은 1 이상 10,000 이하인 정수이며 앞에 0이 붙지 않습니다.
- 1 ≤ k ≤ 200,000
- 사전순은 문자 코드 순서입니다. 밑줄(`_`)은 알파벳 소문자보다 앞섭니다.

## 입출력 예

| records | k | result |
|---|---|---|
| ["pepper 3", "salt 5", "pepper 4", "cumin 2", "salt 1"] | 2 | ["pepper", "salt"] |
| ["mint 10", "basil 4", "anise 6", "basil 6", "clove 10"] | 3 | ["basil", "clove", "mint"] |
| ["constructor 9", "\_\_proto\_\_ 2", "salt 9", "salt 1"] | 5 | ["salt", "constructor", "\_\_proto\_\_"] |

## 입출력 예 설명

- 예 1: pepper는 3 + 4 = 7, salt는 5 + 1 = 6, cumin은 2입니다. 합이 큰 두 품목은 pepper와 salt입니다.
- 예 2: basil(4 + 6), clove, mint의 합이 모두 10이고 anise는 6입니다. 합이 같은 세 품목은 이름순으로 basil, clove, mint가 됩니다.
- 예 3: salt는 9 + 1 = 10, constructor는 9, \_\_proto\_\_는 2입니다. 품목이 3개라 k가 5여도 3개를 담습니다.
