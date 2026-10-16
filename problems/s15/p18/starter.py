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
