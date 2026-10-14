class Cart:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)

    def put_many(self, item, count):
        for _ in range(count):
            self.put(item)
        


def solution(names, counts):
    cart = Cart()
    for i in range(len(names)):
        cart.put_many(names[i], counts[i])
    return cart.items
