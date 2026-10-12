class Skip:
    def __init__(self, items, step):
        self.items = items
        self.step = step
        self.index = 0

    def __iter__(self):
        return self

    def ____(self):
        if self.index ____ len(self.items):
            ____
        value = self.items[self.index]
        self.index += self.step
        return value
