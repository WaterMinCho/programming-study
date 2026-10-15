# 여기에 코드를 작성하세요
class Queue:
    def __init__(self):
        self.queue = []
    def enqueue(self, x):
        self.queue.append(x)
    def dequeue(self):
        if self.is_empty():
            return -1
        return self.queue.pop(0)
    def front(self):
        if self.is_empty():
            return -1
        return self.queue[0]
    def is_empty(self):
        return len(self.queue) == 0
