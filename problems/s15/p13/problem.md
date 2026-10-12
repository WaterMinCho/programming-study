# p13. 리스트 이터레이터 클래스 (빈칸 채우기 · 4점)

리스트를 받아 요소를 앞에서부터 하나씩 돌려주는 이터레이터 클래스 `ListIterator` 와, 이 클래스로 리스트를 출력하는 프로그램입니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

```python
class ListIterator:
    def __init__(self, data):
        if not isinstance(data, list):
            raise TypeError("리스트를 입력해야 합니다.")
        self.data = data
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index < len(self.data):
            value = self.data[self.index]
            self.____ += 1
            return value
        else:
            raise ____


my_list = [1, 2, 3, 4, 5]
iterator = ____(my_list)

for item in iterator:
    print(item)
print("index:", iterator.index)
```

- 첫 번째 빈칸: 값을 하나 돌려줄 때마다 1 씩 늘리는 인스턴스 변수의 이름
- 두 번째 빈칸: 더 돌려줄 요소가 없을 때 일으키는 예외
- 세 번째 빈칸: `my_list` 를 넘겨 이터레이터 객체를 만드는 클래스의 이름
- 마지막 줄은 반복이 끝난 뒤 객체에 남아 있는 `index` 값을 출력합니다.
- **빈칸만** 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

## 출력 예

```
1
2
3
4
5
index: 5
```
