class Rewinder:
    def __init__(self, data):
        self.data = data
        self.pos = len(data) -1

    def __iter__(self):
        return self

    def __next__(self):
        if self.pos < 0:
            raise StopIteration
        item = self.data[self.pos]
        self.pos = self.pos - 1
        return item
