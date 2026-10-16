class Stack:
    def __init__(self):
        self.stack = []

    def push(self, x):
        self.stack.append(x)

    def pop(self):
        if self.is_empty():
            return -1
        return self.stack.____

    def top(self):
        if self.is_empty():
            return -1
        return self.stack[____]

    def is_empty(self):
        return ____
