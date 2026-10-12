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
