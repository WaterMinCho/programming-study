# p04. 폴더가 없으면 만들고 빈 파일 만들기 (빈칸 채우기 · 6점)

파일 이름을 입력받아 `new_folder` 폴더 안에 그 이름의 빈 파일을 만드는 프로그램입니다. `pathlib` 모듈을 사용합니다.
빈칸(`____`) 3곳을 채워 프로그램을 완성하세요.

- 첫 번째 빈칸: `new_folder` 폴더를 만드는 메서드. `exist_ok=True` 를 주었으므로 폴더가 이미 있어도 오류가 나지 않습니다.
- 두 번째 빈칸: 폴더 경로와 파일 이름을 결합하는 연산자
- 세 번째 빈칸: 그 경로에 빈 파일을 만드는 메서드
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
from pathlib import Path

name = input()

folder = Path("new_folder")
folder.____(exist_ok=True)

file_path = folder ____ name
file_path.____()

print(folder.is_dir(), file_path.is_file())
print(file_path.suffix)
```

## 입출력 예

`new_folder` 가 없는 상태에서 실행

입력

```
memo.txt
```

출력

```
True True
.txt
```

실행이 끝나면 `new_folder` 폴더 안에 내용이 없는 `memo.txt` 가 있어야 합니다.

`new_folder` 안에 `old.txt` 가 이미 있는 상태에서 실행

입력

```
data.csv
```

출력

```
True True
.csv
```

실행이 끝나면 `new_folder` 안에 `old.txt` 가 내용 그대로 남아 있고, 빈 파일 `data.csv` 가 새로 생겨 있어야 합니다.
