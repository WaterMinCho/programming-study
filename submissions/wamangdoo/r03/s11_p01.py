def order():
    print("주문하세요")


class Button:
    def connect(self, func):
        self.slot = func

    def click(self):
        self.slot()


btn = Button()
btn.connect(order)
clicks = int(input())
for i in range(clicks):
    btn.click()
