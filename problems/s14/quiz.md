# 14차시 퀴즈: 정규표현식

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s14/quiz.py` 에 적습니다.
> 출력 예측은 여러 줄이면 `"""` 로 감싸서 줄을 나눠 적고, 단답은 문자열로 적습니다(역슬래시가 들어가면 `r"..."` 로).

## Q1 (객관식 · 2점)

정규식 `[xyz]` 로 `search` 했을 때, 매치되는 부분이 **없는** 문자열은?

1. `box`
2. `sky`
3. `lazy`
4. `dog`

## Q2 (객관식 · 2점)

정규식 `go{2,3}d` 를 `re.match` 로 조사했을 때 매치되는 문자열을 **모두 고르세요**.

1. `god`
2. `good`
3. `goood`
4. `gooood`

## Q3 (객관식 · 2점)

정규식 `ca+t` 와 **완전히 같은 의미**인 것은?

1. `ca*t`
2. `ca{1,}t`
3. `ca?t`
4. `ca{0,}t`

## Q4 (객관식 · 2점)

다음 두 패턴에 대한 설명으로 **옳은** 것은?

```python
import re
p1 = re.compile("a.c")
p2 = re.compile("a[.]c")
```

1. `p1.match("abc")` 는 매치되고, `p2.match("abc")` 는 매치되지 않는다.
2. `p1.match("a.c")` 는 매치되지 않는다.
3. `p2.match("a0c")` 는 매치된다.
4. `p1.match("ac")` 는 매치된다.

## Q5 (객관식 · 2점)

컴파일된 패턴 객체의 메서드에 대한 설명으로 옳지 **않은** 것은?

1. `match()` 는 문자열의 처음부터 정규식과 매치되는지 조사한다.
2. `search()` 는 문자열 전체를 검색하여 정규식과 매치되는 부분이 있는지 조사한다.
3. `findall()` 은 정규식과 매치되는 모든 문자열을 리스트로 리턴한다.
4. `match()` 와 `search()` 는 매치되지 않으면 빈 문자열 `''` 을 리턴한다.

## Q6 (객관식 · 2점)

컴파일 옵션에 대한 설명으로 옳지 **않은** 것은?

1. `re.IGNORECASE` 와 `re.I` 는 같은 옵션으로, 대소문자 구별 없이 매치되게 한다.
2. `re.DOTALL` 은 `.` 메타 문자가 줄바꿈 문자 `\n` 과도 매치되게 한다.
3. `re.MULTILINE` 은 `.` 메타 문자가 여러 줄에 걸쳐 매치되게 하는 옵션이다.
4. `re.VERBOSE` 를 쓰면 정규식 안에 줄바꿈과 주석을 넣어 읽기 쉽게 작성할 수 있다.

## Q7 (객관식 · 2점)

어떤 텍스트 안에 들어 있는 글자 그대로의 `\data` (역슬래시 + data) 를 찾으려고 합니다. 정규식 엔진에 역슬래시 2개짜리 `\\data` 가 전달되도록 **올바르게** 컴파일한 것은?

1. `re.compile('\\data')`
2. `re.compile(r'\data')`
3. `re.compile(r'\\data')`
4. `re.compile('data')`

## Q8 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
text = "ab12cd345e6"
print(re.findall(r"\d", text))
print(re.findall(r"\d+", text))
print(re.findall(r"[a-z]+", text))
print(re.findall(r"\w+", text))
```

## Q9 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
p = re.compile("[a-z]+")
m = p.match("42 apples")
print(m)
s = p.search("42 apples")
print(s.group())
print(s.start(), s.end())
print(s.span())
```

## Q10 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
p = re.compile("[a-z]+", re.I)
m = p.match("Hello World")
print(m)
print(m.group())
```

## Q11 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
data = """cat one
dog two
cat three"""
p1 = re.compile(r"^cat \w+")
p2 = re.compile(r"^cat \w+", re.M)
p3 = re.compile(r"\w+$", re.M)
print(p1.findall(data))
print(p2.findall(data))
print(p3.findall(data))
```

## Q12 (단답 · 3점)

정규식에서 `{0,1}` 과 같은 뜻을 가지는 메타 문자 **한 글자**를 적으세요.

## Q13 (단답 · 3점)

`\D` 와 같은 뜻을 대괄호 `[ ]` 문자 클래스로 적으세요. (숫자 범위는 `0-9` 로 표현)

## Q14 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
text = "color colour colr"
print(re.findall(r"colou?r", text))
print(re.findall(r"colo*r", text))
print(re.findall(r"colo+r", text))
```

## Q15 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. (`be` 와 `or` 사이의 공백은 2개입니다)

```python
import re
text = "to be  or"
print(len(re.findall(r"\s", text)))
p = re.compile(r"\S+")
for m in p.finditer(text):
    print(m.start(), m.end(), m.group())
```

## Q16 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
p = re.compile(r"\d{2}")
print(p.match("2024").group())
print(p.findall("2024"))
print(p.findall("12345"))
print(p.match("7"))
print(p.search("a1b22").span())
```

## Q17 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
text = "a1\nb2"
print(re.findall(".", text))
print(len(re.findall(".", text, re.S)))
print(re.match("a1.b2", text))
print(re.match("a1.b2", text, re.S).group())
```

## Q18 (객관식 · 2점)

`text = "A-1 b_2 C3"` 일 때, 실행 결과가 `['b_2', 'C3']` 인 것은?

1. `re.findall(r"\w+", text)`
2. `re.findall(r"\w{2,}", text)`
3. `re.findall(r"[a-z]\w+", text)`
4. `re.findall(r"\w\d", text)`

## Q19 (객관식 · 2점)

정규식 `[^a-z]+$` 를 `re.match` 로 조사했을 때 매치되는 문자열을 **모두 고르세요**.

1. `ABC`
2. `A1b`
3. `12 3`
4. `x9`

## Q20 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
p1 = re.compile(r"""
    \d{2}   # 시
    :       # 구분자
    \d{2}   # 분
""", re.VERBOSE)
p2 = re.compile(r"\d \d", re.X)
p3 = re.compile(r"\d[ ]\d", re.X)
text = "at 09:30, room 4 2, code 77"
print(p1.findall(text))
print(p2.findall(text))
print(p3.findall(text))
```

## Q21 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
text = r"\word lord sword"
print(re.findall("\\word", text))
print(len(re.findall("\\\\word", text)))
print(len(re.findall(r"\\word", text)))
print(re.search(r"\\word", text).span())
```

## Q22 (객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
print(re.findall(r"[a-c.+]+", "a+b.c=d-e"))
```

1. `['a+b.c']`
2. `['a', 'b', 'c']`
3. `['a+b.c=d-e']`
4. `['a+b', 'c']`

## Q23 (단답 · 3점)

파이썬에서 정규표현식을 쓰려고 `import` 하는 표준 라이브러리 모듈의 이름을 적으세요.

## Q24 (객관식 · 2점)

정규식 `^abc` 의 의미로 옳은 것은?

1. 문자열이 `abc` 로 시작해야 매치된다.
2. 문자열이 `abc` 로 끝나야 매치된다.
3. 문자열 어디에든 `abc` 가 들어 있으면 매치된다.
4. `a`, `b`, `c` 가 아닌 글자 하나와 매치된다.

## Q25 (객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
pattern = r"\w+"
text = "Hi, ROKEY_11!"
print(re.findall(pattern, text))
```

1. `['Hi', 'ROKEY_11']`
2. `['Hi', 'ROKEY', '11']`
3. `['Hi,', 'ROKEY_11!']`
4. `['Hi', ',', 'ROKEY_11', '!']`

## Q26 (객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
pattern = r"(ab)+"
text = "ababa"
match = re.match(pattern, text)
print(match.group())
```

1. `ab`
2. `abab`
3. `ababa`
4. 오류가 발생한다

## Q27 (객관식 · 2점)

메타 문자에 대한 설명으로 옳지 **않은** 것은?

1. 원래 그 문자가 가진 뜻이 아니라 특별한 의미로 쓰이는 문자를 말한다.
2. 리스트를 표현하는 `[]`, 튜플을 표현하는 `()` 처럼 자료 구조나 특정 표식을 나타내는 데 쓰는 기호가 그 예이다.
3. 정규식에서는 `. ^ $ * + ? { } [ ] \ | ( )` 를 메타 문자로 쓴다.
4. `@` 도 정규식의 메타 문자라서 `\@` 로 적어야만 `@` 글자와 매치된다.

## Q28 (객관식 · 2점)

정규표현식과 `re` 모듈에 대한 설명으로 옳지 **않은** 것은?

1. 정규표현식은 정해 둔 패턴으로 문자열을 검색하거나 일치 여부를 확인하고, 필요한 부분을 추출·변환하는 데 쓴다.
2. 이메일·전화번호 형식 검증이나 로그 파일 처리에 쓰이며, 문법이 언어 사이에 비슷해 다른 언어에서도 응용할 수 있다.
3. `re.compile(정규식)` 은 정규식을 컴파일한 패턴 객체를 돌려주고, 이 객체의 `match`, `search`, `findall`, `finditer` 로 문자열을 조사한다.
4. 축약형 `re.match(정규식, 문자열)` 은 match 객체가 아니라 매치된 문자열을 바로 돌려준다.

## Q29 (객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
p = re.compile("^python\s\w+")

data = """python one
life is too short
python two
you need python
python three"""

print(p.findall(data))
```

1. `['python one']`
2. `['python one', 'python two', 'python three']`
3. `['python one', 'python two', 'you need python', 'python three']`
4. `[]`

## Q30 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
print(re.match(r"(ab)+", "ababab").group())
print(re.match(r"ab+", "ababab").group())
print(re.match(r"ab+", "abbab").group())
print(re.match(r"(ab)+", "aabab"))
print(re.search(r"(ab)+", "aabab").span())
```

## Q31 (객관식 · 2점)

다음은 강의에서 `re.VERBOSE` 를 설명할 때 나온 정규식입니다. `p.match(문자열)` 로 조사했을 때 매치되는 문자열을 **모두 고르세요**.

```python
import re
p = re.compile(r"&[#](0[0-7]+|[0-9]+|x[0-9a-fA-F]+);")
```

1. `&#123;`
2. `&#x4F;`
3. `&#12`
4. `&#xyz;`

## Q32 (객관식 · 2점)

`re.match()` 와 `re.search()` 의 차이를 바르게 설명한 것은?

1. 둘 다 문자열 전체를 뒤져 처음 매치되는 곳을 찾는다.
2. `re.match()` 는 문자열의 시작 부분부터 정규식과 매치되는지 검사한다.
3. `re.search()` 는 문자열의 시작 부분이 정규식과 맞을 때만 match 객체를 리턴한다.
4. 둘의 동작은 다르지 않다.

## Q33 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import re
text = "id_7, pw-9!"
print(re.findall(r"\w+", text))
print(re.findall(r"\W", text))
print(len(re.findall(r"\D", text)))
```

## Q34 (객관식 · 2점)

대괄호 `[ ]` 문자 클래스에 대한 설명으로 옳지 **않은** 것은?

1. `[a-c]` 는 `[abc]` 와 같다.
2. `[\^]` 는 `^` 글자 하나와 매치된다.
3. `[^0-9]` 는 숫자가 아닌 글자 하나와 매치된다.
4. `[.]` 는 줄바꿈 문자를 뺀 아무 글자 하나와 매치된다.

## Q35 (객관식 · 2점)

`p = re.compile('[a-z]+')` 일 때, 결과가 match 객체가 **아닌** 것은?

1. `p.match("python")`
2. `p.search("3 python")`
3. `p.findall("life is too short")`
4. `for m in p.finditer("life is too short"):` 에서 하나씩 꺼낸 `m`

## Q36 (객관식 · 2점)

역슬래시 문제와 raw string 에 대한 설명으로 옳지 **않은** 것은?

1. 정규식 `\section` 의 `\s` 는 화이트스페이스로 해석되어 `[ \t\n\r\f\v]ection` 과 같은 뜻이 된다.
2. 보통 문자열로 정규식 엔진에 `\\section` 을 전달하려면 `'\\\\section'` 처럼 역슬래시 4개를 쓴다.
3. raw string 을 쓰면 `r'\\section'` 처럼 역슬래시 2개만 써도 엔진에 `\\section` 이 전달된다.
4. 역슬래시가 없는 정규식도 앞에 `r` 을 붙이면 다른 정규식으로 컴파일되어 결과가 달라진다.

## Q37 (객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
text = "Contact us at support@example.com or sales@example.org."
pattern = r"[\w.-]+@[\w.-]+\.\w+"
emails = re.findall(pattern, text)
print(emails)
```

1. `['support@example.com', 'sales@example.org']`
2. `['support@example.com', 'sales@example.org.']`
3. `['support@example', 'sales@example']`
4. `['support', 'sales']`

## Q38 (객관식 · 2점)

다음 코드의 출력 결과는?

```python
import re
text = "상품 코드: A123, B456, C789, 가격: 12000원"
print(re.findall(r"\d+", text))
```

1. `['123', '456', '789', '12000']`
2. `[123, 456, 789, 12000]`
3. `['A123', 'B456', 'C789', '12000원']`
4. `['1', '2', '3', '4', '5', '6', '7', '8', '9', '1', '2', '0', '0', '0']`
