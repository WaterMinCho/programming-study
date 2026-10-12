class Tank:
    def __init__(self, name):
        self.name = name
        self.amount = 0

    def fill(self, liters):
        self.amount += liters
        print(self.name, "채움", self.amount)

    def fill_all(self, plan):
        for liters in plan:
            self.fill(liters)
        print(self.name, "완료", self.amount)


# 아래에 SafeTank 클래스 작성
