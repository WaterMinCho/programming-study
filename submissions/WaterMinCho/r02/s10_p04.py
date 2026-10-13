class Device:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def info(self):
        print("제품:", self.name)
        print("가격:", self.price)


class Laptop(Device):
    def __init__(self, name, price, ram):
        super().__init__(name, price)
        self.ram = ram
