# p18. 제너레이터 표현식을 클래스로 옮기기 (빈칸 채우기 · 6점)

제너레이터 표현식 `(i * i for i in range(1, 6))` 과 같은 값을 같은 순서로 돌려주는 이터레이터 클래스 `MyIterator` 를 만들었습니다.
빈칸(`____`) 2곳을 채워 프로그램을 완성하세요.

```python
class MyIterator:
    def __init__(self):
        self.data = ____

    def __iter__(self):
        return self

    def __next__(self):
        result = self.data * self.data
        if self.data >= ____:
            raise StopIteration
        self.data += 1
        return result


gen = (i * i for i in range(1, 6))
print(list(gen))
print(list(MyIterator()))
```

- 첫 번째 빈칸: `self.data` 의 처음 값
- 두 번째 빈칸: 반복을 끝내는 경계 값(정수)
- 두 줄의 출력이 같아야 합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 출력 예

```
[1, 4, 9, 16, 25]
[1, 4, 9, 16, 25]
```
