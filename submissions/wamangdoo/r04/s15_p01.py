menu = ["bibimbap", "ramen", "gimbap", "sushi"]
it = iter(menu)
print(type(it))
print("first:", next(it))
for food in it:
    print("next:", food)
