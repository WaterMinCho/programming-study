# 여기에 코드를 작성하세요
class Drone:
    def __init__(self, model, weight, color):
        self.model = model
        self.weight = weight
        self.color = color
        print("드론 생성")
        
    def info(self):
        print("모델:", self.model)
        print("무게:", self.weight)
        print("색상:", self.color)
        
    def set_info(self, model, weight, color):
        self.model = model
        self.weight = weight
        self.color = color
        
