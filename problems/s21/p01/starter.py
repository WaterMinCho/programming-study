import json

data = {"name": "홍길동", "age": 25, "city": "서울"}

with open("data.json", "w", encoding="utf-8") as file:
    json.____(data, ____, indent=4)

with open("data.json", "r", encoding="utf-8") as file:
    loaded = json.____(file)

print(loaded["name"], loaded["age"], loaded["city"])
print(type(loaded))
print(loaded == data)
