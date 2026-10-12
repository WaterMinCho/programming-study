# p01. JSON 파일로 저장하고 불러오기 (빈칸 채우기 · 4점)

딕셔너리 `data` 를 `data.json` 파일로 저장한 다음, 그 파일을 다시 읽어 딕셔너리로 불러오는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- 첫 번째 빈칸: 파이썬 객체를 JSON 형식으로 **파일에** 저장하는 `json` 모듈의 함수
- 두 번째 빈칸: 그 함수에 넘겨 줄, 저장할 파일 객체
- 세 번째 빈칸: JSON **파일을** 읽어 파이썬 객체로 돌려주는 `json` 모듈의 함수
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
import json

data = {"name": "홍길동", "age": 25, "city": "서울"}

with open("data.json", "w", encoding="utf-8") as file:
    json.____(data, ____, indent=4)

with open("data.json", "r", encoding="utf-8") as file:
    loaded = json.____(file)

print(loaded["name"], loaded["age"], loaded["city"])
print(type(loaded))
print(loaded == data)
```

## 출력 예

```
홍길동 25 서울
<class 'dict'>
True
```

`data.json` 에 다른 내용이 이미 적혀 있는 상태에서 실행해도 출력은 위와 같아야 합니다.
