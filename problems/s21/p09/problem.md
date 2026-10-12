# p09. 확장자별 폴더로 정리하기 (출력 · 8점)

폴더 안의 파일을 확장자별로 나눠 담는 `organize(source_folder)` 함수를 작성하세요.

1. `source_folder` **바로 안에** 있는 파일을 하나씩 확인합니다.
2. 파일의 확장자에서 점을 뺀 이름으로 `source_folder` 안에 하위 폴더를 만들고, 파일을 그 폴더로 **이동**합니다. `inbox` 폴더의 `a.txt` 는 `inbox/txt/a.txt` 로 옮깁니다.
3. 하위 폴더가 이미 있으면 새로 만들지 않고 그 폴더를 그대로 씁니다.
4. 원래부터 있던 폴더와 확장자가 없는 파일(예: `README`)은 옮기지 않고 그대로 둡니다.
5. 다 옮긴 뒤 `이동한 파일: N개` (`N` 은 옮긴 파일 수)를 출력합니다.

- 확장자는 파일 이름의 마지막 점부터 끝까지입니다. `archive.tar.gz` 의 확장자는 `.gz` 이므로 `gz` 폴더로 옮깁니다.
- 파일을 복사하는 것이 아니라 이동해야 합니다. 정리가 끝나면 원래 자리에는 그 파일이 없어야 합니다.
- 함수만 정의하면 됩니다. 필요한 모듈은 직접 `import` 합니다. 채점할 때는 아래와 같은 테스트 코드가 함수를 호출합니다.

## 제한 사항
- `source_folder` 는 실제로 있는 폴더의 경로입니다.
- 옮길 자리에 같은 이름의 파일이 이미 있는 경우는 주어지지 않습니다.
- 확장자와 같은 이름을 가진 파일(예: 확장자 없는 파일 `txt`)은 주어지지 않습니다.

## 테스트 코드와 출력 예

`inbox` 폴더에 파일 `a.txt`, `b.txt`, `photo.png` 가 있을 때

```python
import os
organize("inbox")
print(os.path.exists("inbox/a.txt"), os.path.exists("inbox/txt/a.txt"))
print(os.path.exists("inbox/photo.png"), os.path.exists("inbox/png/photo.png"))
```

```
이동한 파일: 3개
False True
False True
```

실행이 끝나면 `inbox/txt` 폴더에 `a.txt`, `b.txt` 가, `inbox/png` 폴더에 `photo.png` 가 원래 내용 그대로 들어 있어야 합니다.

`work` 폴더에 파일 `new.txt`, `data.csv`, `README` 와 폴더 `txt` 가 있고, `txt` 폴더 안에 `old.txt` 가 있을 때

```python
import os
organize("work")
print(os.path.exists("work/new.txt"), os.path.exists("work/README"))
```

```
이동한 파일: 2개
False True
```

실행이 끝나면 `work/txt` 폴더에 `old.txt`, `new.txt` 가, `work/csv` 폴더에 `data.csv` 가 있고 `README` 는 제자리에 있어야 합니다.

- 출력은 글자 하나까지 같아야 합니다(띄어쓰기 포함).
