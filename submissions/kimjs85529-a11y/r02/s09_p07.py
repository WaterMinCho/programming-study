class Tank:
    def __init__(self):
        self.level = 0

    def fill(self, amount=10):
        self.level = self.level + amount

    def fill_twice(self, amount):
        self.fill(amount)
        self.fill(amount)
