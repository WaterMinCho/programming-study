def weather(temp):
    if temp >= 28:
        return "hot"
    elif temp <= 5:
        return "cold"
    return "mild"

t = int(input())
result = weather(t)
print(t, "->", result)
