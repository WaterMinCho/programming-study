class Stack:
    def __init__(self):
        self.stack = ['두산', '로키', '부트']

    def push(self, data):
        self.stack.append(data)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return

    def is_empty(self):
        return len(self.stack) == 0

    def peak(self):
        if not self.is_empty():
            return self.stack[-1]
        return

    def status_stack(self):
        return self.stack


word = input()
s = ____
s.____(word)
print(s.status_stack())
s.____()
print(s.status_stack())
