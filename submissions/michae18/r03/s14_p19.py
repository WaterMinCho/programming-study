# 여기에 코드를 작성하세요
import re
email = input()
email_pattern = re.compile('^\w+@\w+\.\w+$')
#print(bool(re.findall(email_pattern,email)))
#print(bool(email_pattern.match(email)))
if bool(email_pattern.match(email)) == True:
    print('Valid email')
else:
   print('Invalid email')
