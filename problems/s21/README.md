# 21차시 · 파이썬 활용 심화(os·pathlib·JSON)

이 차시는 시험 범위가 아니라서 회차에 나오지 않고 단원 띠와 준비도에서도 빠집니다.

파일과 폴더를 다루는 표준 모듈 `os`, `shutil`, `pathlib` 과 Excel 파일을 다루는 `openpyxl`, `pandas`, 데이터 형식 JSON 과 웹 API 를 배우는 차시입니다.
함수 이름과 하는 일을 짝짓는 객관식, 빈칸에 함수 이름을 채우는 문제가 나오기 좋은 단원이라 모듈별로 이름을 철자까지 외워 둡니다.
`openpyxl`, `pandas`, `requests` 는 따로 설치하는 패키지라서 이 세트에서는 객관식과 단답으로만 다루고, 코드 문제는 `os`, `shutil`, `pathlib`, `json` 으로 풉니다.

| 강의 절 | 내용 |
|---|---|
| 21.1 파일관리 기본 | `os` 모듈(작업 디렉터리, 목록, 생성·삭제, 경로 다루기), `shutil` 모듈(복사·이동·삭제) |
| 21.2 파일 정리 프로그램 제작 | `pathlib` 의 `Path`(경로 결합, 존재 확인, 생성·삭제, 목록, 확장자, 이동) |
| 21.3 Excel 읽기/쓰기 기초 | `openpyxl` 의 `Workbook`, `load_workbook`, 셀 읽기와 쓰기, 저장 |
| 21.4 Excel 데이터 정리 자동화 | `pandas` 의 `read_excel`, 열 연산, `to_excel` |
| 21.5 JSON 과 API 활용 기초 | `json` 모듈의 `loads`·`dumps`·`load`·`dump`, API 와 REST API, `requests` |

## 1. os 모듈

운영 체제와 상호 작용하는 기능을 제공하는 내장 모듈입니다. 설치하지 않고 `import os` 로 불러옵니다.

| 코드 | 하는 일 |
|---|---|
| `os.getcwd()` | 현재 작업 디렉터리 확인 |
| `os.chdir("경로")` | 작업 디렉터리 변경 |
| `os.listdir(".")` | 그 디렉터리에 있는 파일과 폴더의 이름을 리스트로 반환 |
| `os.mkdir("test_dir")` | 디렉터리 생성 |
| `os.rmdir("test_dir")` | 디렉터리 삭제(비어 있는 디렉터리만) |
| `os.path.exists("file.txt")` | 경로가 있으면 `True`, 없으면 `False` |
| `os.path.join(folder, "file.txt")` | 경로 합치기 |
| `os.path.basename(경로)` | 파일명만 추출 |
| `os.path.dirname(경로)` | 디렉터리 경로 추출 |

```python
import os

os.mkdir("test_dir")                               # 디렉터리 생성
print(os.path.exists("test_dir"))                  # True
print(os.listdir("test_dir"))                      # []  (빈 폴더)
os.rmdir("test_dir")                               # 디렉터리 삭제
print(os.path.exists("test_dir"))                  # False

print(os.path.basename("C:/work/data/file.txt"))   # file.txt
print(os.path.dirname("C:/work/data/file.txt"))    # C:/work/data
```

- `os.listdir()` 가 돌려주는 것은 이름 문자열의 리스트입니다. 파일과 폴더가 구분 없이 들어 있고, 하위 폴더 안에 든 파일은 들어 있지 않습니다. 이름의 순서는 운영 체제에 따라 달라질 수 있습니다.
- 목록에서 꺼낸 이름으로 파일을 열거나 복사하려면 `os.path.join(폴더, 이름)` 으로 폴더 경로와 합칩니다. `join` 은 운영 체제에 맞는 구분자를 넣어 줍니다.
- `os.path.exists()` 는 확인만 하고 아무것도 만들지 않습니다. `if os.path.exists("file.txt"):` 처럼 조건문에 넣어 씁니다.
- `os.mkdir()` 는 같은 이름의 디렉터리가 이미 있으면 `FileExistsError` 를 냅니다.

## 2. shutil 모듈

고수준 파일 조작 기능을 제공하는 모듈입니다. `import shutil` 로 불러옵니다.

| 코드 | 하는 일 |
|---|---|
| `shutil.copy("source.txt", "destination.txt")` | 파일 복사 |
| `shutil.copy2("source.txt", "destination.txt")` | 메타데이터를 유지하며 파일 복사 |
| `shutil.copytree("source_dir", "destination_dir")` | 디렉터리 전체 복사 |
| `shutil.move("old_location", "new_location")` | 파일이나 디렉터리 이동 |
| `shutil.rmtree("directory_to_delete")` | 디렉터리와 하위 파일을 모두 삭제 |

- 인자는 원본을 먼저, 대상을 나중에 적습니다.
- 복사(`copy`, `copy2`, `copytree`)는 원본이 남고, 이동(`move`)은 원본이 원래 자리에서 사라집니다.
- `os.rmdir()` 는 빈 디렉터리만 지웁니다. 안에 파일이 있는 디렉터리를 통째로 지울 때는 `shutil.rmtree()` 를 씁니다.

강의 실습(텍스트 파일만 찾아 복사·이동·삭제)은 `os.listdir()` 로 이름을 꺼내고, `.txt` 로 끝나는 이름만 골라 `shutil` 함수에 넘기는 구조입니다.

```python
import os
import shutil


def copy_txt_files(source_folder, destination_folder):
    if not os.path.exists(destination_folder):         # 대상 폴더가 없을 때만 생성
        os.mkdir(destination_folder)
    for name in os.listdir(source_folder):
        if name[-4:] == ".txt":                        # 이름의 끝 네 글자 확인
            source = os.path.join(source_folder, name)
            destination = os.path.join(destination_folder, name)
            shutil.copy(source, destination)
```

`shutil.copy` 자리에 `shutil.move` 를 쓰면 이동하는 함수가 됩니다.

## 3. pathlib 모듈

파일과 디렉터리를 객체 지향 방식으로 다루는 모듈입니다. `from pathlib import Path` 로 `Path` 클래스를 불러오고, 경로 하나를 `Path("이름")` 객체로 만들어 메서드를 부릅니다.

| 코드 | 하는 일 |
|---|---|
| `Path.cwd()` | 현재 작업 디렉터리 확인 |
| `Path("folder") / "file.txt"` | 경로 결합(`/` 연산자) |
| `path.exists()` | 존재 여부 확인 |
| `path.is_file()` | 존재하고 파일인지 확인 |
| `path.is_dir()` | 디렉터리인지 확인 |
| `path.mkdir(exist_ok=True)` | 폴더 생성(이미 있어도 오류 없음) |
| `path.rmdir()` | 폴더 삭제 |
| `path.touch()` | 빈 파일 생성 |
| `path.unlink()` | 파일 삭제 |
| `path.iterdir()` | 폴더 안의 파일과 폴더를 하나씩 꺼냄 |
| `path.suffix` | 확장자(`.txt`) |
| `path.parent` | 그 경로가 들어 있는 상위 폴더 |
| `path.rename(새 경로)` | 이름 변경, 이동 |

```python
from pathlib import Path

folder = Path("new_folder")
folder.mkdir(exist_ok=True)                 # 폴더 생성
file_path = folder / "test.txt"             # 경로 결합
print(file_path.exists())                   # False  (경로 객체만 있고 파일은 아직 없음)
file_path.touch()                           # 빈 파일 생성
print(file_path.exists(), file_path.is_file(), file_path.is_dir())   # True True False
print(file_path.suffix)                     # .txt
file_path.unlink()                          # 파일 삭제
folder.rmdir()                              # 폴더 삭제
print(folder.exists())                      # False
```

- `Path("이름")` 을 만드는 것만으로는 파일이나 폴더가 생기지 않습니다. `touch()` 나 `mkdir()` 을 불러야 만들어집니다.
- `suffix` 는 메서드가 아니라 속성이라 괄호를 붙이지 않습니다. 값에는 점이 포함됩니다. 마지막 점부터 끝까지라서 `archive.tar.gz` 는 `.gz`, 확장자가 없는 `README` 는 빈 문자열입니다.
- `mkdir()` 에 `exist_ok=True` 를 주지 않으면 폴더가 이미 있을 때 `FileExistsError` 가 납니다.
- `Path.cwd()` 는 `Path` 클래스에 바로 붙여 부릅니다. `os` 모듈의 `os.getcwd()` 와 이름이 다릅니다.

파일을 다른 폴더로 옮길 때는 옮길 경로를 만들고, 그 경로의 상위 폴더(`parent`)를 만든 다음 `rename()` 을 부릅니다.

```python
path = Path("example.txt")
path.touch()                                   # 파일 생성
destination = Path("new_folder/example.txt")
destination.parent.mkdir(exist_ok=True)        # 대상 폴더 생성
path.rename(destination)                       # new_folder 안으로 이동
```

강의 실습(확장자별 자동 분류)은 폴더 안의 항목 가운데 파일만 골라, 확장자 이름의 폴더로 옮기는 구조입니다. 아래 코드는 `os.listdir()` 로 꺼낸 이름을 `Path` 와 결합해서 씁니다.

```python
import os
from pathlib import Path


def organize(source_folder):
    folder = Path(source_folder)
    for name in os.listdir(source_folder):
        path = folder / name
        if path.is_file() and path.suffix != "":
            target = folder / path.suffix[1:]      # ".txt" 에서 점을 뺀 "txt"
            target.mkdir(exist_ok=True)
            path.rename(target / name)
```

같은 일을 하는 `os`·`shutil` 코드와 `pathlib` 코드

| 하는 일 | os · shutil | pathlib |
|---|---|---|
| 현재 작업 디렉터리 | `os.getcwd()` | `Path.cwd()` |
| 경로 합치기 | `os.path.join(a, b)` | `Path(a) / b` |
| 존재 확인 | `os.path.exists(p)` | `Path(p).exists()` |
| 폴더 생성 | `os.mkdir(p)` | `Path(p).mkdir(exist_ok=True)` |
| 폴더 삭제 | `os.rmdir(p)` | `Path(p).rmdir()` |
| 목록 조회 | `os.listdir(p)` | `Path(p).iterdir()` |
| 이동 | `shutil.move(a, b)` | `Path(a).rename(b)` |

## 4. openpyxl 로 Excel 읽고 쓰기

파이썬에서 Excel 파일을 읽고 쓰는 라이브러리입니다. xlsx 포맷을 지원하고, 설치 명령은 `pip install openpyxl` 입니다.

```python
from openpyxl import Workbook, load_workbook

wb = Workbook()                          # 새 워크북 생성
sheet = wb.active                        # 활성 시트 선택
sheet['A1'] = 'Hello'                    # 셀에 값 입력
sheet['B1'] = 'World'
wb.save('new_example.xlsx')              # 파일로 저장

wb = load_workbook('new_example.xlsx')   # 기존 파일 열기
sheet = wb.active                        # 기본(첫 번째) 시트
print(sheet['A1'].value)                 # Hello
sheet['A1'] = '새로운 값'                 # 셀 값 수정
wb.save('modified_example.xlsx')         # 바뀐 내용을 새 파일로 저장
```

- 새 파일은 `Workbook()`, 기존 파일은 `load_workbook('파일명.xlsx')` 입니다.
- `wb.active` 는 속성입니다. 괄호를 붙여 `wb.active()` 로 쓰면 오류가 납니다.
- 셀에 넣을 때는 `sheet['A1'] = 값`, 셀에서 읽을 때는 `sheet['A1'].value` 입니다. `.value` 를 빼고 `print(sheet['A1'])` 하면 값이 아니라 `<Cell 'Sheet'.A1>` 같은 셀 객체가 출력됩니다. `value` 는 속성이라 괄호를 붙이지 않습니다.
- 셀 값을 바꿔도 `wb.save()` 를 부르기 전에는 파일이 바뀌지 않습니다. 불러온 파일과 같은 이름으로 저장하면 그 파일이 수정됩니다.

여러 셀은 `iter_rows()` 로 읽습니다. 값이 없는 셀의 `value` 는 `None` 입니다.

```python
for row in sheet.iter_rows(min_row=1, max_col=3, max_row=5):   # 1~5행, 1~3열
    for cell in row:
        print(cell.value)        # Hello, World, None, None, ... 모두 15줄
```

숫자, 날짜, 수식도 셀에 넣을 수 있습니다. 수식은 `=` 로 시작하는 문자열로 적습니다.

```python
from datetime import datetime

sheet['A1'] = datetime(2025, 1, 28)   # 날짜 입력
sheet['B1'] = 100                     # 숫자 입력
sheet['C1'] = '=B1*2'                 # 수식 입력
```

## 5. pandas 로 Excel 다루기

`pip install pandas openpyxl` 로 설치하고 `import pandas as pd` 로 불러옵니다. Excel 데이터를 DataFrame 으로 바꿔서 처리합니다.

```python
import pandas as pd

df = pd.read_excel("파일명.xlsx", sheet_name="Sheet1")   # 시트를 DataFrame 으로 읽기
print(df.head())                    # 처음 5개 행
print(df.info())                    # 데이터 타입, Null 값 여부
print(df.describe())                # 수치형 데이터의 평균, 최댓값, 최솟값 등 요약

print(df["나이"])                    # 특정 열
print(df["나이"].sum())              # 합계
print(df["나이"].mean())             # 평균
df["출생년도"] = 2025 - df["나이"]    # 기존 열로 새 열 만들기

df.to_excel("modified_example.xlsx", index=False)   # index 열을 빼고 저장
```

- `2025 - df["나이"]` 는 행마다 계산됩니다. 나이가 30, 25, 28 이면 출생년도는 1995, 2000, 1997 입니다.
- `to_excel()` 은 `index=False` 를 주지 않으면 0, 1, 2 … 로 자동 생성된 index 를 맨 앞 열에 함께 저장합니다.
- 읽는 쪽은 `pd.read_excel()` 처럼 `pd.` 에 붙이고, 저장하는 쪽은 `df.to_excel()` 처럼 DataFrame 에 붙입니다.

## 6. JSON

JSON(JavaScript Object Notation)은 데이터를 저장하고 전송하는 데 사용하는 경량 데이터 형식입니다. 사람과 기계가 모두 읽기 쉬운 텍스트 기반 구조이고, 주요 데이터 구조는 객체(파이썬의 딕셔너리)와 배열(파이썬의 리스트)입니다.

```json
{
    "name": "Alice",
    "age": 25,
    "city": "Seoul",
    "skills": ["Python", "Django", "Machine Learning"]
}
```

파이썬에서는 내장 모듈 `json` 으로 다룹니다.

| 함수 | 방향 | 다루는 대상 |
|---|---|---|
| `json.loads(문자열)` | JSON 문자열 → 파이썬 객체 | 문자열 |
| `json.dumps(객체, indent=4)` | 파이썬 객체 → JSON 문자열 | 문자열 |
| `json.dump(객체, 파일, indent=4)` | 파이썬 객체 → JSON 파일 | 파일 |
| `json.load(파일)` | JSON 파일 → 파이썬 객체 | 파일 |

```python
import json

json_string = '{"name": "Alice", "age": 25, "city": "Seoul"}'
data = json.loads(json_string)            # 문자열 → 딕셔너리
print(data["name"])                       # Alice

python_dict = {"name": "Bob", "age": 30}
print(python_dict)                        # {'name': 'Bob', 'age': 30}
print(json.dumps(python_dict))            # {"name": "Bob", "age": 30}
print(json.dumps(python_dict, indent=4))  # 아래처럼 4칸 들여 쓴 여러 줄
# {
#     "name": "Bob",
#     "age": 30
# }

with open("data.json", "w", encoding="utf-8") as file:
    json.dump(python_dict, file, indent=4)     # 파일로 저장

with open("data.json", "r", encoding="utf-8") as file:
    loaded_data = json.load(file)              # 파일에서 불러오기
print(loaded_data)                             # {'name': 'Bob', 'age': 30}
```

- 이름 끝에 `s` 가 붙은 `loads`, `dumps` 는 문자열(string)을 다루고, `s` 가 없는 `load`, `dump` 는 파일을 다룹니다.
- `json.dumps()` 가 돌려주는 값은 딕셔너리가 아니라 문자열(`str`)입니다. JSON 문자열 안의 글자는 큰따옴표로 감싸고, 딕셔너리를 `print` 하면 작은따옴표로 나옵니다.
- `indent=4` 를 주면 항목마다 줄을 바꾸고 4칸 들여 씁니다. 주지 않으면 한 줄로 만들어집니다.
- `json.loads()` 로 바꾼 뒤에는 보통의 딕셔너리와 리스트입니다. JSON 의 숫자 `25` 는 정수가 되어 계산에 바로 쓸 수 있습니다.
- `json.load()` 가 만든 객체는 저장하기 전의 객체와 내용은 같지만 별개의 객체입니다. 불러온 쪽을 고쳐도 원래 딕셔너리는 바뀌지 않습니다.
- 한글을 `dumps` 나 `dump` 로 바꾸면 `\ud64d` 같은 모양으로 적힙니다. `loads` 나 `load` 로 읽으면 원래 글자로 돌아옵니다.

## 7. API 와 requests

- API(Application Programming Interface)는 프로그램 간에 데이터와 기능을 주고받을 수 있도록 하는 인터페이스입니다.
- REST API 는 HTTP 프로토콜을 기반으로 JSON 형태의 데이터를 주고받는 방식입니다.
- 강의는 OpenWeatherMap 의 날씨 API 를 썼습니다. 회원 가입 뒤 [API keys] 탭에서 확인하는 API 키는 32자 길이의 알파벳과 숫자 조합입니다.

```python
import requests
import json

apikey = "발급받은 API 키"
city = "Seoul,KR"
api = "http://api.openweathermap.org/data/2.5/weather?q={city}&APPID={key}"
k2c = lambda k: k - 273.15                      # 켈빈 온도를 섭씨 온도로 변환

url = api.format(city=city, key=apikey)         # {city}, {key} 자리에 값을 넣어 URL 구성
r = requests.get(url)                           # API 에 요청 보내기
data = json.loads(r.text)                       # 응답 문자열을 딕셔너리로 변환

print("+ 도시 =", data["name"])
print("| 날씨 =", data["weather"][0]["description"])
print("| 최저 기온 =", k2c(data["main"]["temp_min"]))
print("| 습도 =", data["main"]["humidity"])
```

- 요청은 `requests.get(url)` 로 보냅니다. 모듈 이름은 끝에 `s` 가 붙은 `requests` 입니다.
- 응답을 딕셔너리로 바꾸는 방법은 `json.loads(r.text)` 와 `r.json()` 이 있습니다. 강의 슬라이드는 앞의 방법을, 주간 과제는 `response.json()` 을 썼습니다. `response.status_code` 는 상태 코드입니다.
- 응답은 딕셔너리와 리스트가 겹쳐 있어서 바깥부터 차례로 꺼냅니다. `data["weather"]` 는 리스트라서 `[0]` 으로 첫 원소를 꺼낸 뒤 `["description"]` 을 읽고, `data["main"]` 은 딕셔너리라서 바로 `["temp_min"]` 을 읽습니다.
- `"…{city}…{key}".format(city=값, key=값)` 은 문자열의 `{이름}` 자리에 값을 넣은 새 문자열을 만듭니다. 값은 적은 순서가 아니라 이름으로 짝지어지고, 원래 문자열 `api` 는 바뀌지 않습니다.

## 시험에서 헷갈리기 쉬운 점

- `os.getcwd()` 는 확인, `os.chdir()` 는 변경입니다. `pathlib` 에서 현재 작업 디렉터리는 `Path.cwd()` 이고 `Path.getcwd()` 는 없습니다.
- 디렉터리 전체 복사는 `shutil.copytree()`, 디렉터리 전체 삭제는 `shutil.rmtree()` 입니다. `copydir`, `rmdir` 같은 이름과 섞지 않습니다. `rmdir` 은 `os` 와 `Path` 에 있고 빈 디렉터리만 지웁니다.
- `shutil.copy()` 와 `shutil.copy2()` 는 메타데이터를 유지하는지로 구분합니다. 유지하는 쪽이 `copy2` 입니다.
- 삭제 함수는 대상에 따라 나뉩니다. 파일은 `Path.unlink()`, 빈 폴더는 `Path.rmdir()` 나 `os.rmdir()`, 내용이 있는 폴더는 `shutil.rmtree()` 입니다.
- 만드는 함수도 대상에 따라 나뉩니다. 빈 파일은 `Path.touch()`, 폴더는 `Path.mkdir()` 나 `os.mkdir()` 입니다.
- "없으면 만들고 있으면 넘어간다"는 `mkdir(exist_ok=True)` 입니다.
- `path.rename(destination)` 을 실행하면 파일이 `destination` 으로 옮겨져서 `path.exists()` 는 `False`, `destination.exists()` 는 `True` 가 됩니다. `destination.parent` 는 `destination` 이 들어 있는 폴더입니다.
- `os.path.basename()` 은 확장자를 포함한 파일명(`file.txt`)을, `Path.suffix` 는 점을 포함한 확장자(`.txt`)를 돌려줍니다.
- `os.path.exists()`, `Path.exists()`, `is_file()`, `is_dir()` 의 결과는 `True` 나 `False` 입니다. 폴더에 `is_file()` 을 부르면 `False` 입니다.
- 경로 결합은 `os.path.join(a, b)` 와 `Path(a) / b` 입니다. `Path` 에 `+` 를 쓰면 오류가 납니다.
- openpyxl 에서 새 파일은 `Workbook()`, 기존 파일은 `load_workbook()`, 저장은 `wb.save()` 입니다. pandas 의 `read_excel()`, `to_excel()` 과 섞지 않습니다.
- `Workbook()` 으로 만든 빈 워크북을 기존 파일과 같은 이름으로 저장하면 기존 내용이 없어집니다. 기존 파일에 데이터를 추가할 때는 `load_workbook()` 으로 연 뒤 셀에 값을 넣고 `save()` 합니다.
- `iter_rows(min_row=1, max_col=3, max_row=5)` 는 5행 × 3열 = 15개 셀을 돕니다. 빈 셀은 `None` 으로 출력됩니다.
- 수식은 `'=B1*2'` 처럼 `=` 로 시작하는 문자열입니다. `=` 가 없으면 글자 그대로 들어갑니다.
- `df.head()` 는 처음 5개 행, `df.info()` 는 데이터 타입과 Null 값 여부, `df.describe()` 는 수치형 데이터의 요약 정보입니다.
- `to_excel(..., index=False)` 는 자동 생성된 index 열을 빼고 저장합니다. 열 이름이 적힌 첫 행은 저장됩니다.
- `json.loads` / `json.load`, `json.dumps` / `json.dump` 는 끝의 `s` 하나로 갈립니다. 문자열이면 `s` 가 있는 쪽, 파일이면 `s` 가 없는 쪽입니다. `json.dump(객체, 파일)` 은 인자 순서가 객체 먼저입니다.
- `json.dumps()` 의 결과를 출력할 때는 큰따옴표, 쉼표와 콜론 뒤의 공백 한 칸, `indent=4` 일 때의 4칸 들여쓰기를 그대로 적습니다. 마지막 항목 뒤에는 쉼표가 없고 중괄호는 들여 쓰지 않습니다.
- JSON 문자열을 파이썬 코드에 적을 때는 `'{"name": "Alice"}'` 처럼 바깥을 작은따옴표로, 안을 큰따옴표로 씁니다.
- `data["weather"][0]["description"]` 에서 `[0]` 을 빼면 리스트에 문자열 인덱스를 쓴 것이 되어 `TypeError` 가 납니다.
- 강의의 날씨 예제 출력은 `print("+ 도시 =", data["name"])` 처럼 쉼표로 나열해서 `=` 뒤에 공백이 한 칸 들어간 `+ 도시 = Seoul` 입니다.
