# 상황별 코드

시험용 상황별 코드 노트입니다. 학습 루프 하나를 줄마다 따라갑니다.

## 시험 뼈대 단원

### 학습 루프 여덟 줄
<!-- facts: F18-01 F18-02 F18-03 -->

모델을 학습 모드로 두고 묶음마다 파라미터를 한 번 바꿉니다.

<!-- skel: S90 가 -->
```python
net.train()            # 학습 모드
for a, b in data:
    opt.zero_grad()
    c = net(a)
    e = crit(c, b)
    e.backward()
    opt.step()
    n += c.argmax(1).sum()
```

`opt.zero_grad()` 는 앞 묶음에서 쌓인 값을 비웁니다.

```ai-recall
{"id": "r1", "q": "학습 모드로 바꾸는 메서드 이름은 ____ 입니다.", "answer": ["train"], "mode": "code"}
```

### 두 판 나란히 보기
<!-- facts: F18-04 -->

```ai-diff
{"skel": "S90", "left": "가", "right": "나"}
```

나 판은 평가 모드로 두고 0번 축에서 위치를 고릅니다.

### 돌려 가며 빈칸
<!-- facts: F18-01 -->

```ai-rotate
{"id": "t1", "skel": "S90", "variant": "가"}
```

가린 자리를 하나씩 채웁니다. 틀린 자리는 세 자리 뒤에 다시 나옵니다.

### 외울 것
<!-- facts: F18-01 F18-02 F18-03 -->

```ai-memo
[{"q": "학습 모드로 바꾸는 줄은 무엇인가요?", "a": "net.train() 입니다.", "cards": ["pc-k01"]},
 {"q": "zero_grad 는 언제 부르면 되나요?", "a": "다음 backward 전에만 부르면 됩니다.", "cards": ["pc-o01"]},
 {"q": "1번 축에서 고른 위치를 더하는 줄은 무엇인가요?", "a": "n += c.argmax(1).sum() 입니다.", "cards": ["pc-p01"]}]
```
