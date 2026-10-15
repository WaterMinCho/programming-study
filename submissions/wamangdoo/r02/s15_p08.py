class Countdown:
    def __init__(self, start):
        self.n = start
    # 여기에 __iter__ 와 __next__ 메서드를 작성하세요
    def __iter__(self):
        return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration

