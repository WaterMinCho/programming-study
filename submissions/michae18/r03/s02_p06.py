# 여기에 코드를 작성하세요
def print_result(num1, num2):
    print(f'{num1} + {num2} = {num1 + num2}')
    print(f'{num1} - {num2} = {num1 - num2}')
    print(f'{num1} * {num2} = {num1 * num2}')
    print(f'{num1} / {num2} = {num1 / num2}')
    
    
    
    
num1 = int(input(f'정수를 입력하시오.:'))
num2 = int(input(f'정수를 입력하시오.(0은 제외):'))
print_result(num1, num2)
