# p10. txt 파일만 삭제하기 (빈칸 채우기 · 6점)

`folder_path` 폴더 바로 안에 있는 파일 가운데 확장자가 `.txt` 인 파일만 삭제하고, 삭제한 파일 수를 반환하는 `delete_txt_files` 함수입니다. `pathlib` 모듈을 사용합니다.
빈칸(`____`) 3곳을 채워 함수를 완성하세요.

- 첫 번째 빈칸: 폴더 안의 파일과 폴더를 하나씩 꺼내는 메서드
- 두 번째 빈칸: 확장자를 돌려주는 속성
- 세 번째 빈칸: 파일을 삭제하는 메서드
- 폴더는 이름이 `.txt` 로 끝나도 삭제하지 않습니다. 하위 폴더 안에 든 파일도 삭제하지 않습니다.
- 빈칸만 채웁니다. 다른 줄을 고치거나 줄을 추가하면 오답 처리됩니다.

```python
from pathlib import Path


def delete_txt_files(folder_path):
    count = 0
    for item in Path(folder_path).____():
        if item.is_file() and item.____ == ".txt":
            item.____()
            count += 1
    return count
```

## 테스트 코드와 출력 예

`inbox` 폴더에 파일 `a.txt`, `b.txt`, `c.png` 가 있을 때

```python
import os
print(delete_txt_files("inbox"))
print(os.path.exists("inbox/a.txt"), os.path.exists("inbox/c.png"))
print(len(os.listdir("inbox")))
```

```
2
False True
1
```

`work` 폴더에 파일 `memo.txt`, `memo.txt.bak` 과 폴더 `old.txt`, `sub` 가 있고, `sub` 폴더 안에 `inner.txt` 가 있을 때

```python
import os
print(delete_txt_files("work"))
print(os.path.exists("work/memo.txt"), os.path.exists("work/old.txt"))
print(os.path.exists("work/sub/inner.txt"), os.path.exists("work/memo.txt.bak"))
```

```
1
False True
True True
```
