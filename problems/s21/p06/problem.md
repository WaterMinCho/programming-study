# p06. txt 파일만 복사하기 (빈칸 채우기 · 6점)

`source_folder` 폴더에서 이름이 `.txt` 로 끝나는 파일만 찾아 `destination_folder` 폴더로 복사하고, 복사한 파일 수를 반환하는 `copy_txt_files` 함수입니다. `os` 와 `shutil` 모듈을 사용합니다.
빈칸(`____`) 3곳을 채워 함수를 완성하세요.

- 첫 번째 빈칸: 경로가 있는지 확인하는 `os.path` 의 함수. `destination_folder` 가 없을 때만 폴더를 새로 만듭니다.
- 두 번째 빈칸: 폴더 경로와 파일 이름을 합쳐 경로 하나로 만드는 `os.path` 의 함수
- 세 번째 빈칸: 파일을 복사하는 `shutil` 의 함수. 복사한 뒤에도 원본 파일은 `source_folder` 에 남아 있어야 합니다.
- `source_folder` 바로 안에는 파일만 있다고 가정합니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
import os
import shutil


def copy_txt_files(source_folder, destination_folder):
    if not os.path.____(destination_folder):
        os.mkdir(destination_folder)
    count = 0
    for name in os.listdir(source_folder):
        if name[-4:] == ".txt":
            source = os.path.join(source_folder, name)
            destination = os.path.____(destination_folder, name)
            shutil.____(source, destination)
            count += 1
    return count
```

## 테스트 코드와 출력 예

`inbox` 폴더에 `a.txt`, `b.txt`, `c.png` 가 있고 `backup` 폴더는 없을 때

```python
print(copy_txt_files("inbox", "backup"))
print(os.path.exists("inbox/a.txt"), os.path.exists("backup/a.txt"))
print(os.path.exists("backup/c.png"))
```

```
2
True True
False
```

실행이 끝나면 `backup` 폴더에 `a.txt`, `b.txt` 가 원본과 같은 내용으로 들어 있어야 합니다.

`notes` 폴더에 `todo.txt` 가 있고, `saved` 폴더에 `old.txt` 가 이미 있을 때

```python
print(copy_txt_files("notes", "saved"))
print(len(os.listdir("saved")))
```

```
1
2
```
