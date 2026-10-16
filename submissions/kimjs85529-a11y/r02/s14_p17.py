import re

text = input()
words = re.findall(r"[A-Z]{2,}", text)   # 영문 대문자가 2개 이상 이어진 덩어리
print(words)
