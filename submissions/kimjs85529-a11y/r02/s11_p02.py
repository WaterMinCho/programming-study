class CheckBox:
    def __init__(self, text):
        self.text = text
        self.checked = False

    def setChecked(self, value):
        self.checked = value

    def isChecked(self):
        return self.checked
