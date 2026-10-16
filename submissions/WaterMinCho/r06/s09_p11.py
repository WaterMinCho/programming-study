class Hero:
    def __init__(self, name, hp):
        self.name = name
        self.hp = hp

    def hit(self, damage):
        self.hp = self.hp - damage
        if self.hp < 0:
            self.hp = 0

    def alive(self):
        return self.hp > 0

    def heal(self, amount):
        if self.alive():
            self.hp = self.hp + amount
