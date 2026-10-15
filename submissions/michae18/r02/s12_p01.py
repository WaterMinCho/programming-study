with open("menu.txt", 'w', encoding="utf-8") as f:
    f.write("김밥\n")
    f.write("라면\n")

with open("menu.txt", 'r', encoding="utf-8") as f:
    data = f.read()

print(data, end="")
