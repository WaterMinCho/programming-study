# 21차시 퀴즈: 파이썬 활용 심화(os·pathlib·JSON)

> 코드를 실행하지 말고 눈으로 풀어 보세요. 답은 `submissions/<내 ID>/s21/quiz.py` 에 적습니다.

## Q1 (객관식 · 2점)

`os` 모듈에서 현재 작업 디렉터리를 **변경**하는 함수는?

1. `os.getcwd()`
2. `os.listdir()`
3. `os.chdir()`
4. `os.mkdir()`

## Q2 (객관식 · 2점)

`os` 모듈에 대한 설명으로 옳지 **않은** 것은?

1. 운영 체제와 상호 작용하는 기능을 제공하는 내장 모듈이라 따로 설치하지 않고 `import os` 로 불러온다.
2. `os.path.exists("file.txt")` 는 `file.txt` 가 없으면 빈 파일을 새로 만든다.
3. `os.listdir(".")` 는 현재 디렉터리에 있는 파일과 폴더의 목록을 돌려준다.
4. `os.mkdir("test_dir")` 는 디렉터리를 만들고, `os.rmdir("test_dir")` 는 디렉터리를 삭제한다.

## Q3 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import os

path = "C:/work/data/file.txt"
print(os.path.basename(path))
```

1. `C:/work/data`
2. `file`
3. `file.txt`
4. `.txt`

## Q4 (객관식 · 2점)

`shutil` 모듈에서 디렉터리 전체를 복사하는 함수는?

1. `shutil.copy()`
2. `shutil.copytree()`
3. `shutil.copydir()`
4. `shutil.rmtree()`

## Q5 (객관식 · 2점)

`shutil` 모듈에 대한 설명으로 옳지 **않은** 것은?

1. 고수준 파일 조작 기능을 제공하는 모듈이고 `import shutil` 로 불러온다.
2. `shutil.copy("source.txt", "destination.txt")` 를 실행해도 `source.txt` 는 원래 자리에 남는다.
3. `shutil.move("old.txt", "new.txt")` 를 실행한 뒤에도 `old.txt` 는 원래 자리에 남는다.
4. `shutil.copy2()` 는 메타데이터를 유지하며 파일을 복사한다.

## Q6 (객관식 · 2점)

`backup` 폴더 안에 파일이 여러 개 들어 있습니다. 이 폴더를 안에 든 파일까지 한 번에 삭제하는 코드는? (`import os`, `import shutil`, `from pathlib import Path` 를 실행한 상태입니다.)

1. `shutil.rmtree("backup")`
2. `os.rmdir("backup")`
3. `Path("backup").rmdir()`
4. `Path("backup").unlink()`

## Q7 (객관식 · 2점)

`pathlib` 모듈에서 현재 작업 디렉터리를 가져오는 코드는? (`from pathlib import Path` 를 실행한 상태입니다.)

1. `Path.pwd()`
2. `Path.cwd()`
3. `Path.getcwd()`
4. `Path.workdir()`

## Q8 (객관식 · 2점)

`pathlib` 모듈에 대한 설명으로 옳지 **않은** 것은?

1. `Path("report.txt").suffix` 는 확장자를 뺀 이름 `report` 를 돌려준다.
2. 파일과 디렉터리를 객체 지향 방식으로 다룬다.
3. `from pathlib import Path` 로 `Path` 클래스를 불러와서 쓴다.
4. `Path("folder") / "file.txt"` 처럼 `/` 연산자로 경로를 결합한다.

## Q9 (객관식 · 2점)

`new_folder` 폴더가 없으면 새로 만들고, 이미 있으면 오류 없이 넘어가는 코드는? (`import os` 와 `from pathlib import Path` 를 실행한 상태입니다.)

1. `Path("new_folder").mkdir()`
2. `os.mkdir("new_folder")`
3. `Path("new_folder").mkdir(exist_ok=True)`
4. `Path("new_folder").touch()`

## Q10 (단답 · 3점)

`docs` 폴더에서 확장자가 `.txt` 인 항목만 출력하는 코드입니다. 빈칸(`____`)에 들어갈 속성 이름을 적으세요.

```python
from pathlib import Path

path = Path("docs")
for item in path.iterdir():
    if item.____ == ".txt":
        print(item)
```

## Q11 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. 실행 전 현재 폴더는 비어 있습니다.

```python
from pathlib import Path

folder = Path("box")
folder.mkdir(exist_ok=True)
file_path = folder / "memo.txt"
print(file_path.exists())
file_path.touch()
print(file_path.exists(), file_path.is_file(), file_path.is_dir())
print(file_path.suffix)
file_path.unlink()
print(file_path.exists(), folder.exists())
folder.rmdir()
print(folder.exists())
```

## Q12 (객관식 · 2점)

다음 중 **기존** 엑셀 파일을 불러올 때 사용하는 openpyxl 의 함수는?

1. `Workbook`
2. `active`
3. `to_excel`
4. `load_workbook`
5. `read_excel`

## Q13 (객관식 · 2점)

새 엑셀 파일을 만들어 `data.xlsx` 로 저장하는 코드입니다. 빈칸(`____`)에 들어갈 메서드는?

```python
from openpyxl import Workbook

wb = Workbook()
sheet = wb.active
sheet['A1'] = 'Hello'
wb.____('data.xlsx')
```

1. `to_excel`
2. `save`
3. `write`
4. `dump`

## Q14 (객관식 · 2점)

`data.xlsx` 의 첫 번째 시트 A1 셀에 `이름` 이 들어 있습니다. 이 내용을 남겨 둔 채 같은 시트의 A2 셀에 `홍길동` 을 추가하고 `data.xlsx` 에 저장하는 코드는? (`from openpyxl import Workbook, load_workbook` 을 실행한 상태입니다.)

**1번**

```python
wb = Workbook()
sheet = wb.active
sheet['A2'] = '홍길동'
wb.save('data.xlsx')
```

**2번**

```python
wb = load_workbook('data.xlsx')
sheet = wb.active
sheet['A2'] = '홍길동'
```

**3번**

```python
wb = load_workbook('data.xlsx')
sheet = wb.active
sheet['A2'] = '홍길동'
wb.save('data.xlsx')
```

**4번**

```python
wb = load_workbook('data.xlsx')
sheet = wb.active()
sheet['A2'] = '홍길동'
wb.save('data.xlsx')
```

## Q15 (객관식 · 2점)

다음 코드의 실행 결과에 대한 설명으로 옳은 것은?

```python
from openpyxl import Workbook

wb = Workbook()
sheet = wb.active
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'

for row in sheet.iter_rows(min_row=1, max_col=3, max_row=5):
    for cell in row:
        print(cell.value)
```

1. `Hello`, `World` 두 줄만 출력된다.
2. 모두 15줄이 출력되고, 값이 없는 셀은 `None` 으로 출력된다.
3. 모두 15줄이 출력되고, 값이 없는 셀은 빈 줄로 출력된다.
4. 모두 8줄이 출력되고, 값이 없는 셀은 `None` 으로 출력된다.

## Q16 (객관식 · 2점)

`sheet` 는 openpyxl 로 연 시트이고 B1 셀에는 숫자 `100` 이 들어 있습니다. C1 셀에 'B1 값의 2배'를 계산하는 **수식**을 입력하는 코드는?

1. `sheet['C1'] = B1*2`
2. `sheet['C1'] = 'B1*2'`
3. `sheet['C1'] = sheet['B1']*2`
4. `sheet['C1'] = '=B1*2'`

## Q17 (단답 · 3점)

Excel 파일을 불러와 DataFrame 으로 바꿔 주는 pandas 함수의 이름을 적으세요. 아래 코드의 빈칸(`____`)에 들어갑니다.

```python
import pandas as pd

df = pd.____("파일명.xlsx", sheet_name="Sheet1")
```

## Q18 (객관식 · 2점)

pandas 로 Excel 파일을 읽어 만든 DataFrame `df` 가 있습니다. 수치형 데이터의 평균, 최댓값, 최솟값 같은 요약 정보를 보여 주는 코드는?

1. `df.head()`
2. `df.info()`
3. `df.to_excel()`
4. `df.describe()`

## Q19 (객관식 · 2점)

`df.to_excel("modified_example.xlsx", index=False)` 에서 `index=False` 가 하는 일은?

1. 자동으로 만들어진 index 열을 빼고 저장한다.
2. 첫 행의 열 이름을 빼고 저장한다.
3. 같은 이름의 파일이 이미 있으면 저장하지 않는다.
4. 값이 비어 있는 행을 빼고 저장한다.

## Q20 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import pandas as pd

df = pd.DataFrame({"이름": ["홍길동", "Alice", "Bob"],
                   "나이": [30, 25, 29]})
df["출생년도"] = 2025 - df["나이"]
print(df["나이"].sum(), df["출생년도"].max())
```

1. `84 1995`
2. `84 2000`
3. `28.0 2000`
4. 오류가 발생한다

## Q21 (단답 · 3점)

다음 문장들이 설명하는 데이터 형식의 이름을 영어로 적으세요.

- 데이터를 저장하고 전송하는 데 사용하는 경량 데이터 형식
- 사람과 기계가 모두 읽기 쉬운 텍스트 기반 구조
- 객체(딕셔너리)와 배열(리스트)이 주요 데이터 구조

## Q22 (객관식 · 2점)

`json` 모듈의 함수와 하는 일을 짝지은 것으로 옳지 **않은** 것은?

1. `json.loads(문자열)`: JSON 문자열을 파이썬 객체로 변환한다.
2. `json.dumps(객체)`: 파이썬 객체를 JSON 문자열로 변환한다.
3. `json.dump(객체, 파일)`: 파이썬 객체를 JSON 형식으로 파일에 저장한다.
4. `json.load(문자열)`: JSON 문자열을 파이썬 객체로 변환한다.

## Q23 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import json

json_string = '{"name": "Alice", "age": 25, "skills": ["Python", "Django"]}'
data = json.loads(json_string)
print(type(data))
print(data["name"], data["age"] + 1)
print(data["skills"][1], len(data["skills"]))
```

## Q24 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. 따옴표의 종류와 들여쓰기 칸 수까지 같아야 합니다.

```python
import json

info = {"name": "Bob", "age": 30}
text = json.dumps(info)
print(info)
print(text)
print(type(text))
print(json.dumps(info, indent=4))
```

## Q25 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import json

scores = {"kim": [80, 90], "lee": [70]}

with open("scores.json", "w", encoding="utf-8") as file:
    json.dump(scores, file, indent=4)

with open("scores.json", "r", encoding="utf-8") as file:
    loaded = json.load(file)

loaded["lee"].append(100)
print(loaded["lee"])
print(scores["lee"])
print(loaded == scores, len(loaded))
```

## Q26 (객관식 · 2점)

API 에 대한 설명으로 옳지 **않은** 것은?

1. API 는 Application Programming Interface 의 줄임말이다.
2. API 는 프로그램 간에 데이터와 기능을 주고받을 수 있게 하는 인터페이스이다.
3. REST API 는 HTTP 프로토콜을 기반으로 JSON 형태의 데이터를 주고받는 방식이다.
4. REST API 로 받은 JSON 데이터는 파이썬 딕셔너리로 바꿀 수 없어 문자열 그대로 다뤄야 한다.

## Q27 (객관식 · 2점)

가짜 데이터를 제공하는 무료 API 사이트에서 데이터를 받아와 출력하는 프로그램입니다. `<1>`, `<2>`, `<3>` 에 들어갈 코드를 차례대로 나열한 것은?

```python
import requests

url = "https://jsonplaceholder.typicode.com/posts/1"

response = <1>.get(<2>)

print("상태 코드:", response.status_code)

data = response.<3>()

print("게시글 ID:", data["id"])
print("제목:", data["title"])
print("내용:", data["body"])
```

1. `requests`, `url`, `json`
2. `request`, `url`, `json`
3. `requests`, `"url"`, `loads`
4. `response`, `url`, `text`

## Q28 (객관식 · 2점)

날씨 API 가 돌려준 JSON 문자열을 딕셔너리로 바꿨습니다. `data` 에서 문자열 `clear sky` 를 꺼내는 식은?

```python
import json

text = '{"name": "Seoul", "weather": [{"description": "clear sky"}], "main": {"humidity": 68}}'
data = json.loads(text)
```

1. `data["weather"]["description"]`
2. `data["description"]`
3. `data["weather"][0]["description"]`
4. `data["main"]["description"]`

## Q29 (객관식 · 2점)

`data.xlsx` 의 첫 번째 시트 A1 셀에 `이름` 이 들어 있습니다. 아래 코드에 이어서 실행했을 때 `이름` 이 출력되는 코드는?

```python
from openpyxl import load_workbook

wb = load_workbook('data.xlsx')
sheet = wb.active
```

1. `print(sheet['A1'])`
2. `print(sheet['A1'].value)`
3. `print(sheet['A1'].value())`
4. `print(wb['A1'].value)`

## Q30 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요. 실행 전 현재 폴더는 비어 있습니다.

```python
from pathlib import Path

path = Path("example.txt")
path.touch()
destination = Path("new_folder/example.txt")
print(destination.parent.exists())
destination.parent.mkdir(exist_ok=True)
path.rename(destination)
print(path.exists(), destination.exists())
print(destination.parent.is_dir(), destination.suffix)
```

## Q31 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
api = "weather?q={city}&APPID={key}"
city = "Seoul,KR"
apikey = "abc123"

url = api.format(city=city, key=apikey)
print(url)
print(api.format(key="K", city="C"))
print(api)
```

## Q32 (출력 예측 · 3점)

다음 코드의 출력 결과를 그대로 적으세요.

```python
import json

text = '{"name": "Seoul", "weather": [{"description": "clear sky"}], "main": {"humidity": 68, "pressure": 1029}, "wind": {"deg": 310}}'
data = json.loads(text)

print("+ 도시 =", data["name"])
print("| 날씨 =", data["weather"][0]["description"])
print("| 습도 =", data["main"]["humidity"])
print("| 풍향 =", data["wind"]["deg"])
```

## Q33 (객관식 · 2점)

다음 코드를 실행했을 때 출력되는 것은?

```python
import os

path = "C:/work/data/file.txt"
print(os.path.dirname(path))
```

1. `C:/work/data`
2. `C:/work/data/`
3. `data`
4. `file.txt`
