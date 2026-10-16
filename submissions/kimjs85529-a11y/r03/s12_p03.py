with open("names.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("인원:", len(lines))
for line in lines:
    print(line, end="")
