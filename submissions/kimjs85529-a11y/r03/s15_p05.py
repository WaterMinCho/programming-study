def countdown(start):
    n = start
    while n > 0:
        yield n
        n = n - 1


gen = countdown(3)
print(next(gen))
print(next(gen))
print(next(gen))

squares = (i**2 for i in range(1,5))
print(type(squares))
print(next(squares))
for s in squares:
    print(s)
