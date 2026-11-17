# 응용 5차시 사전학습 CNN을 새 분류와 추론에 맞추기


## AlexNet 공간 크기를 내림으로 따라가기


### 먼저 풀어 보기
<!-- facts: FA05-a1 FA05-a4 -->

```ai-guess
{"id": "g1", "q": "AlexNet 첫 합성곱 층에서 (224 + 4 − 11) ÷ 4를 계산하면 54.25입니다. 출력 한 변은 무엇일까요?", "options": ["55", "56"], "answer": 0, "reveal_step": 2, "cards": ["a05-b01"]}
```

```ai-guess
{"id": "g2", "q": "펼치기 직전 모양이 [25, 16, 6, 6]인 텐서에 view(-1, 400)을 쓰면 어떻게 될까요?", "options": ["원소 수가 맞지 않아 바로 오류가 납니다.", "모양이 [36, 400]인 텐서가 나옵니다."], "answer": 1, "reveal_step": 5, "cards": ["a05-c11"]}
```


### 11×11 창의 시작 위치 세기
<!-- facts: FA05-a1 -->

54.25는 AlexNet 첫 층의 출력 크기 식에서 나온 값입니다. torchvision의 AlexNet을 `print(model)`로 보면 features[0]은 `Conv2d(3, 64, kernel_size=(11, 11), stride=(4, 4), padding=(2, 2))`입니다. 둘째 단원에서는 AlexNet으로 개미와 벌 사진을 분류하고, 검증 이미지를 224×224로 잘라 8장씩 넣습니다. 그래서 입력 모양은 [8, 3, 224, 224]입니다.

`padding=2`는 양 끝에 두 칸씩 채웁니다. 채운 뒤의 한 변은 224 + 4 = 228칸이고 칸 번호는 0부터 227까지입니다. 11칸 창의 왼쪽 끝을 0, 4, 8, …처럼 4칸씩 옮깁니다. 시작 위치 216에 놓은 창은 216번부터 226번 칸까지 덮습니다. 다음 시작 위치 220에 놓으면 창 끝이 230번 칸이라 마지막 칸인 227번을 넘으므로 이 위치는 세지 않습니다. 시작 위치는 0부터 216까지 4칸 간격이라 216 ÷ 4 + 1 = 55개입니다.

같은 계산을 식으로 쓰면 floor((224 + 4 − 11) ÷ 4) + 1 = floor(54.25) + 1 = 55입니다. 소수 0.25는 마지막 창 뒤에 남은 227번 칸 하나를 이동 간격 4로 나눈 값입니다. 남은 한 칸으로는 11칸 창을 더 놓을 수 없어서 <mark>내림</mark>을 씁니다. PyTorch 문서의 Conv2d 출력 크기 식도 floor를 씁니다. 올림으로 계산하면 56이 되어 첫 층 출력의 한 변이 실제 55보다 하나 커집니다.

높이와 너비에 같은 식을 따로 적용하므로 첫 층 뒤 모양은 [8, 64, 55, 55]입니다. 64는 출력 채널 수이고 공간 계산에 들어가지 않습니다.

```ai-code-help
{"title": "Conv2d의 stride와 padding", "explanation": "stride는 창을 옮기는 간격이고 padding은 양 끝에 채우는 칸 수입니다. 출력 한 변은 floor((입력 + 2 × padding − 커널) ÷ stride) + 1입니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11b", "step": 3, "title": "바깥을 채운 길이에서 출력 크기 계산하기"}}
```

```figure
파일: assets/a5a-1.gif
캡션: 그림 1. 224×224 입력의 한 변이 AlexNet features를 지나며 55, 27, 13, 6으로 줄어듭니다. 배치 8은 모든 장에서 바뀌지 않습니다.
내용: 224×224 입력의 한 변이 AlexNet features를 지나며 55, 27, 13, 6으로 줄어듭니다. 배치 8은 모든 장에서 바뀌지 않습니다.
프레임:
1. features[0] 합성곱이 [8, 3, 224, 224]를 [8, 64, 55, 55]로 바꿉니다. (2200ms)
2. features[2] 최대 풀링이 한 변을 27로 줄이고 features[3] 합성곱은 채널만 192로 늘립니다. (2200ms)
3. features[5] 최대 풀링이 한 변을 13으로 줄이고 합성곱 세 층은 13을 유지하며 채널을 256으로 맞춥니다. (2200ms)
4. features[12] 최대 풀링이 한 변을 6으로 줄이고 avgpool을 지난 모양은 [8, 256, 6, 6]입니다. (2400ms)
```

```figure
파일: assets/a5a-2.png
캡션: 그림 2. 양 끝을 두 칸씩 채운 228칸에서 11칸 창의 시작 위치는 0부터 216까지 55개입니다. 시작 위치 220은 창 끝이 230번 칸이라 세지 않습니다.
내용: 양 끝을 두 칸씩 채운 228칸에서 11칸 창의 시작 위치는 0부터 216까지 55개입니다. 시작 위치 220은 창 끝이 230번 칸이라 세지 않습니다.
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r1", "q": "224 입력의 양 끝을 padding=2로 채우면 채운 뒤의 한 변은 ____ 칸입니다.", "answer": ["228"], "mode": "number"}
```
```ai-why
{"q": "padding을 0으로 바꾸면 첫 층 출력 한 변은 왜 54가 될까요?", "a": "(224 − 11) ÷ 4 = 53.25를 내리면 53이고 1을 더해 54입니다. 채운 네 칸이 없어져 마지막 시작 위치 하나가 빠집니다."}
```


### 겹치는 최대 풀링으로 27·13·6 따라가기
<!-- facts: FA05-a2 -->

2단계에서 첫 층 뒤 한 변은 55였습니다. 다음 층 features[2]는 `MaxPool2d(kernel_size=3, stride=2)`입니다. 창 크기 3보다 이동 간격 2가 작아서 이웃한 두 창이 한 칸씩 겹칩니다. 개론 11차시 넷째 단원에서 쓴 `MaxPool2d(2)`는 창 크기와 이동 간격이 같아 겹치는 칸이 없었습니다.

창이 겹쳐도 출력 크기는 같은 식으로 셉니다. padding 0에서 floor((55 − 3) ÷ 2) + 1 = 27입니다. 뒤 층에도 같은 식을 차례로 적용해 표에 적었습니다. ReLU 층은 값만 바꾸고 모양을 바꾸지 않아서 표에서 뺐습니다.

| 층 | 설정 | 한 변 |
|---|---|---|
| features[0] Conv2d | 커널 11, stride 4, padding 2 | 224→55 |
| features[2] MaxPool2d | 커널 3, stride 2 | 55→27 |
| features[3] Conv2d | 커널 5, padding 2 | 27→27 |
| features[5] MaxPool2d | 커널 3, stride 2 | 27→13 |
| features[6]·[8]·[10] Conv2d | 커널 3, padding 1 | 13→13 |
| features[12] MaxPool2d | 커널 3, stride 2 | 13→6 |

features[0] 뒤의 합성곱 네 층은 padding으로 한 변을 유지합니다. 한 변을 줄이는 층은 최대 풀링 세 개입니다. 이 풀링의 출력 한 변은 floor((n − 3) ÷ 2) + 1입니다. 55, 27, 13처럼 홀수이면 절반을 내린 값과 같습니다. 짝수 26을 넣으면 12가 나와 절반인 13보다 작습니다.

```ai-code-help
{"title": "MaxPool2d의 kernel_size와 stride", "explanation": "stride를 생략하면 kernel_size와 같은 값을 씁니다. AlexNet처럼 stride를 kernel_size보다 작게 주면 이웃한 창이 겹칩니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11d", "step": 3, "title": "커널 크기와 이동 간격 확인하기"}}
```

```figure
파일: assets/a5a-3.png
캡션: 그림 3. 13칸에 3칸 창을 2칸씩 옮기면 시작 위치는 0, 2, 4, 6, 8, 10입니다. 굵은 테두리 칸은 이웃한 두 창이 함께 덮는 칸입니다.
내용: 13칸에 3칸 창을 2칸씩 옮기면 시작 위치는 0, 2, 4, 6, 8, 10입니다. 굵은 테두리 칸은 이웃한 두 창이 함께 덮는 칸입니다.
```
```ai-recall
{"id": "r2", "q": "MaxPool2d(kernel_size=3, stride=2)에 한 변 61을 넣으면 출력 한 변은 ____ 입니다.", "answer": ["30"], "mode": "number"}
```
```ai-why
{"q": "창이 겹치면 같은 55칸에서 출력 칸 수가 왜 늘어날까요?", "a": "창을 옮기는 간격이 3에서 2로 줄어 시작 위치가 늘어납니다. 55칸에 3칸 창을 3칸씩 옮기면 18칸이고 2칸씩 옮기면 27칸입니다."}
```

```ai-levels
{"id": "v1", "concept": "겹치는 최대 풀링", "levels": [{"level": 7, "text": "칸 13개가 한 줄로 있습니다. 세 칸짜리 상자를 맨 왼쪽에 놓고 오른쪽으로 두 칸씩 옮깁니다. 상자가 줄 밖으로 나가는 자리에는 놓지 않습니다.", "q": "이웃한 두 상자가 함께 덮는 칸은 ____ 칸입니다.", "answer": ["1"], "mode": "number", "why": "세 칸 상자를 두 칸만 옮기므로 앞 상자의 마지막 칸을 다음 상자가 다시 덮습니다.", "figure": {"file": "assets/a5a-31.png", "caption": "13칸 줄에서 세 칸 상자를 두 칸씩 옮겨 놓은 모습입니다.", "content": "13칸 줄 위에 세 칸 상자 여섯 개가 두 칸 간격으로 놓여 있습니다."}}, {"level": 15, "text": "13칸 줄에서 상자를 놓는 시작 칸은 0, 2, 4, 6, 8, 10의 6곳이고 상자마다 3칸을 덮습니다. 상자마다 덮은 칸을 모두 더하면 6 × 3 = 18입니다. 18에는 두 상자가 함께 덮은 칸이 두 번씩 들어 있어서 함께 덮는 칸은 18 − 13 = 5개입니다.", "q": "같은 방법으로 15칸 줄에 상자를 놓으면 두 상자가 함께 덮는 칸은 모두 ____ 개입니다.", "answer": ["6"], "mode": "number", "why": "시작 칸은 0, 2, …, 12의 7곳이라 7 × 3 = 21입니다. 21 − 15 = 6이고 2, 4, 6, 8, 10, 12번 칸이 두 번 세어졌습니다.", "figure": {"file": "assets/a5a-32.png", "caption": "상자마다 시작 칸과 끝 칸을 적은 표입니다.", "content": "상자 번호 1부터 6까지의 시작 칸과 끝 칸을 적은 표입니다."}}, {"level": 20, "text": "MaxPool2d에 kernel_size보다 작은 stride를 주면 이웃한 창이 겹칩니다. kernel_size=3, stride=2, padding=0에서 출력 한 변은 (n − 3) ÷ 2를 내린 값에 하나를 더한 수입니다.", "code": "pool = nn.MaxPool2d(kernel_size=3, stride=2)\nx = torch.zeros(8, 64, 66, 66)\ny = pool(x)", "mistake": "stride=2이면 출력이 늘 입력의 절반이라고 보는 착각입니다. 마지막 창 뒤에 남은 칸으로 창을 하나 더 놓을 수 있는지 확인합니다.", "q": "y.shape의 마지막 값은 ____ 입니다.", "answer": ["32"], "mode": "number", "why": "floor((66 − 3) ÷ 2) + 1 = 31 + 1 = 32입니다. 짝수 입력이라 절반인 33보다 작습니다.", "figure": {"file": "assets/a5a-33.png", "caption": "66칸의 끝부분에서 마지막 창의 시작 칸과 남은 칸을 표시했습니다.", "content": "66칸 줄의 오른쪽 끝에 시작 칸 62의 창이 62번부터 64번 칸을 덮고 65번 칸이 남은 모습입니다. 시작 칸 60의 창과 놓을 수 없는 시작 칸 64의 점선 창도 그렸습니다."}}]}
```


### 적응형 평균 풀링이 224에서 크기를 바꾸지 않는 이유
<!-- facts: FA05-a3 -->

3단계에서 features를 지난 모양은 [8, 256, 6, 6]이었습니다. 다음 모듈 avgpool은 `AdaptiveAvgPool2d(output_size=(6, 6))`입니다. 이 적응형 평균 풀링 층은 들어온 공간 크기와 관계없이 출력 높이와 너비를 6×6으로 맞춥니다. 224 입력에서는 들어오는 크기가 이미 6×6이라 공간 크기를 바꾸지 않고, avgpool 뒤 모양도 [8, 256, 6, 6]입니다.

입력 크기가 달라지면 이 층이 크기를 맞춥니다. 256×256 이미지를 넣으면 features를 지나는 한 변은 63 → 31 → 31 → 15 → 15 → 7입니다. avgpool이 7×7을 6×6으로 맞추므로 뒤 분류기가 받는 모양은 224 입력과 같습니다. 개론 13차시 넷째 단원 3단계의 VGG는 같은 종류의 층으로 공간을 7×7에 맞췄습니다.

AlexNet이 모든 입력 크기를 받지는 않습니다. torchvision 문서는 AlexNet 가중치의 최소 입력을 63×63으로 적었습니다. 63을 넣으면 features 끝의 한 변이 1이고, 62를 넣으면 마지막 최대 풀링에 들어가는 한 변이 2라 3칸 창을 놓을 자리가 없습니다.

```ai-code-help
{"title": "AdaptiveAvgPool2d", "explanation": "AdaptiveAvgPool2d는 배치와 채널 축을 유지하고 높이와 너비만 지정한 크기로 맞춥니다. AlexNet의 avgpool은 6×6을 지정했습니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13b", "step": 3, "title": "원하는 출력 공간 크기 지정하기"}}
```

```figure
파일: assets/a5a-4.png
캡션: 그림 4. 224 입력은 features 끝이 6×6이고 256 입력은 7×7입니다. 두 경우 모두 avgpool 뒤에는 6×6입니다.
내용: 224 입력은 features 끝이 6×6이고 256 입력은 7×7입니다. 두 경우 모두 avgpool 뒤에는 6×6입니다.
```
```ai-why
{"q": "256 입력에서 avgpool을 빼고 바로 펼치면 뒤 분류기와 왜 맞지 않을까요?", "a": "features 끝이 7×7이면 한 장의 길이는 256 × 7 × 7 = 12,544입니다. 224 입력의 6×6에서 나온 길이보다 커서 뒤 분류기가 받는 길이와 다릅니다."}
```
```ai-recall
{"id": "r3", "q": "AdaptiveAvgPool2d((6, 6))에 [8, 256, 5, 5]를 넣으면 출력 모양은 ____ 입니다.", "answer": ["[8, 256, 6, 6]"], "mode": "shape"}
```


### 펼칠 길이를 실행 중에 세기
<!-- facts: FA05-a4 -->

4단계까지 따라가면 avgpool 뒤 모양은 224 입력과 256 입력 모두 [8, 256, 6, 6]입니다. 분류기에 넣으려면 샘플마다 256 × 6 × 6 = 9,216개를 한 줄로 펼칩니다. 펼칠 길이를 숫자로 적지 않고 아래 함수로 실행 중에 셀 수도 있습니다. 이 함수를 AlexNet의 avgpool 출력에 써 봅니다.

```python
def flat_length(x):
    n = 1
    for s in x.size()[1:]:
        n *= s
    return n

x = x.view(-1, flat_length(x))
```

함수 이름 flat_length는 강의 노트북의 LeNet 예제에 있는 flattened_features를 줄여 쓴 것입니다. 둘째 줄의 n은 곱을 모을 변수이고 셋째 줄의 `x.size()[1:]`은 0번 배치 축을 뺀 나머지 축 길이입니다. AlexNet의 avgpool 출력에서는 (256, 6, 6)이고, 셋을 곱하면 9,216입니다. 마지막 줄의 view 결과는 [8, 9216]이고 classifier[1]의 `Linear(9216, 4096)`이 받는 길이와 같습니다. 검증 이미지 153장을 8장씩 묶으면 마지막 배치는 1장인데, 이때도 결과는 [1, 9216]입니다.

펼칠 길이를 숫자로 적으면 `-1` 자리가 전체 원소 수를 그 길이로 나눈 값이 됩니다. 개론 11차시 다섯째 단원 3단계에서 `view(-1, 4)`가 [2, 2, 2, 2]를 [4, 4]로 바꾼 것과 같은 계산입니다. 32×32 입력에 맞춰 만든 LeNet을 생각해 봅니다. 이 LeNet의 fc1은 `Linear(16 * 5 * 5, 120)`이라 펼친 값 400개를 받습니다. 펼치는 줄을 `view(-1, 400)`처럼 숫자로 적었다고 합시다. 여기에 36×36 이미지를 넣으면 펼치기 직전 모양은 [배치 크기, 16, 6, 6]이고 한 장의 원소는 576개입니다.

배치가 25장이면 원소 14,400개를 400개씩 묶어 [36, 400]이 됩니다. fc1은 한 행의 길이가 400인지만 보므로 fc1 줄에서도 오류가 나지 않습니다. 마지막 층은 점수 10개를 내므로 출력은 [36, 10]입니다. 오류는 `nn.CrossEntropyLoss()`로 이 출력과 정답 25개의 손실을 구하는 줄에서 처음 납니다. 배치가 24장이면 원소 13,824개가 400으로 나누어떨어지지 않아 view 줄에서 바로 오류가 납니다.

flat_length를 쓰면 같은 25장이 [25, 576]이 되고 fc1의 `Linear(400, 120)`에서 바로 모양 오류가 납니다. 실행 중에 세는 함수는 샘플 수를 지키지만 fc1의 입력 수를 바꾸지는 않습니다. 개론 16차시 넷째 단원 4단계에서 본 것처럼 입력 크기를 바꾸면 첫 Linear의 입력 수를 다시 계산합니다.

```ai-code-help
{"title": "view와 배치 축", "explanation": "view(-1, n)은 전체 원소 수를 n개씩 묶고 첫 축 길이를 원소 수에 맞춰 정합니다. 샘플 수를 지키려면 현재 배치의 샘플 수를 첫 축에 적거나 배치를 뺀 축만 곱한 길이를 씁니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11e", "step": 3, "title": "앞 층의 공간 크기로 Linear 입력 정하기"}}
```

```figure
파일: assets/a5a-5.png
캡션: 그림 5. [25, 16, 6, 6]에 실행 중에 센 576을 쓰면 [25, 576]이고 고정한 400을 쓰면 [36, 400]입니다. 앞의 경우는 fc1에서, 뒤의 경우는 CrossEntropyLoss로 손실을 구하는 줄에서 오류가 납니다.
내용: [25, 16, 6, 6]에 실행 중에 센 576을 쓰면 [25, 576]이고 고정한 400을 쓰면 [36, 400]입니다. 앞의 경우는 fc1에서, 뒤의 경우는 CrossEntropyLoss로 손실을 구하는 줄에서 오류가 납니다.
```
```ai-reveal
{"guess": "g2"}
```
```ai-recall
{"id": "r4", "q": "[8, 256, 6, 6]에 view(-1, 9216)을 적용하면 첫 축 길이는 ____ 입니다.", "answer": ["8"], "mode": "number"}
```
```ai-why
{"q": "view(-1, 400)이 [36, 400]을 낼 때 fc1에서 오류가 나지 않는 까닭은 무엇일까요?", "a": "fc1은 한 행의 길이가 400인지만 봅니다. 샘플 수는 첫 축에 들어가므로 25가 36으로 바뀐 것을 fc1이 알아채지 못합니다."}
```


### 외울 것
<!-- facts: FA05-a1 FA05-a2 FA05-a3 FA05-a4 -->

```ai-memo
[{"q": "Conv2d(3, 64, kernel_size=11, stride=4, padding=2)에 224를 넣으면 출력 한 변은 얼마인가요?", "a": "floor((224 + 4 − 11) ÷ 4) + 1 = 55입니다. 54.25의 소수는 창을 더 놓을 수 없는 남은 칸이라 내립니다.", "cards": ["a05-b01"]}, {"q": "MaxPool2d(kernel_size=3, stride=2)에 55를 넣으면 출력 한 변은 얼마인가요?", "a": "floor((55 − 3) ÷ 2) + 1 = 27입니다. 이웃한 창이 한 칸씩 겹칩니다.", "cards": ["a05-b03"]}, {"q": "224 입력에서 AdaptiveAvgPool2d((6, 6))은 공간 크기를 바꾸나요?", "a": "features 끝이 이미 6×6이라 바꾸지 않습니다. 256 입력의 7×7은 6×6으로 맞춥니다.", "cards": ["a05-c02"]}, {"q": "[배치 크기, 16, 6, 6]에 view(-1, 400)을 쓰면 24장과 25장에서 처음 오류가 나는 줄은 어디인가요?", "a": "24장은 원소 13,824개가 400으로 나누어떨어지지 않아 view 줄에서 멈춥니다. 25장은 [36, 400]이 되어 fc1을 지나고 손실 줄에서 멈춥니다.", "cards": ["a05-c11"]}]
```


## 한 함수에서 학습 단계와 검증 단계 나누기


### 먼저 풀어 보기
<!-- facts: FA05-b3 -->

```ai-guess
{"id": "g1", "q": "학습 사진 244장과 검증 사진 153장을 배치 8로 나눠 한 에폭을 돌립니다. 이 에폭에서 optimizer.step()은 몇 번 불릴까요?", "options": ["31번", "51번"], "answer": 0, "reveal_step": 3, "cards": ["a05-c03"]}
```


### dset 값으로 모드와 기울기 기록 함께 바꾸기
<!-- facts: FA05-b1 FA05-b2 -->

첫째 단원에서 따라간 AlexNet의 마지막 층 classifier[6]을 `Linear(4096, 2)`로 바꾸면 ants와 bees 두 클래스의 점수를 냅니다. 이 모델을 학습 사진 244장으로 미세 조정하고 검증 사진 153장으로 성능을 잽니다. 아래 함수는 학습 단계와 검증 단계를 반복문 하나로 처리합니다.

```python
def finetune_model(model, loss_func, optimizer, epochs=10):
    for e in range(epochs):
        for dset in ['train', 'val']:
            if dset == 'train':
                model.train()
            else:
                model.eval()
            loss = 0.0
            for imgs, tgts in dloaders[dset]:
                imgs, tgts = imgs.to(dvc), tgts.to(dvc)
                optimizer.zero_grad()
                with torch.set_grad_enabled(dset == 'train'):
                    ops = model(imgs)
                    loss_curr = loss_func(ops, tgts)
                    if dset == 'train':
                        loss_curr.backward()
                        optimizer.step()
                loss += loss_curr.item() * imgs.size(0)
```

dloaders는 'train'과 'val' 키로 두 DataLoader를 담은 사전이고 dvc는 계산할 장치입니다. 셋째 줄의 dset은 한 에폭 안에서 'train'을 먼저, 'val'을 다음에 가리킵니다. 넷째 줄부터 일곱째 줄까지는 이 값으로 모델의 모드를 정합니다. AlexNet에는 BatchNorm 층이 없어서 `eval()`로 동작이 바뀌는 층은 분류기 안의 Dropout 두 개입니다.

with 줄의 `torch.set_grad_enabled(mode)`는 mode가 True이면 블록 안 계산의 기울기 기록을 켜고 False이면 끕니다. `dset == 'train'`은 학습 단계에서 True, 검증 단계에서 False입니다. False를 넘긴 블록은 `torch.no_grad()` 블록처럼 기울기 기록을 남기지 않습니다.

```figure
파일: assets/a5b-1.png
캡션: 그림 6. dset이 'train'이면 train() 모드에서 기울기 기록을 켜고, 'val'이면 eval() 모드에서 기록을 끕니다.
내용: 두 행 세 열 표입니다. 행은 dset 값 'train'과 'val'이고 열은 모드, set_grad_enabled 값, 기울기 기록입니다. 'train' 행은 train(), True, 켬이고 'val' 행은 eval(), False, 끔입니다. 표 아래에 AlexNet에서 모드에 따라 바뀌는 층은 classifier 안 Dropout 두 개라고 적었습니다.
```

```ai-code-help
{"title": "평가 모드와 기울기 기록", "explanation": "eval()은 Dropout 같은 층의 동작을 바꾸고, 기울기 기록을 끄는 일은 따로 합니다. 여기서는 set_grad_enabled에 False를 넘겨 검증 단계의 기록을 끕니다.", "reference": {"course": "intro", "lesson": "l14", "unit": "14h", "step": 4, "title": "평가에는 모드 전환과 기록 중단 같이 쓰기"}}
```
```ai-recall
{"id": "r1", "q": "AlexNet을 eval() 모드로 바꾸면 동작이 바뀌는 층은 분류기 안의 ____ 두 개입니다.", "answer": ["Dropout", "드롭아웃"], "mode": "word", "why": "AlexNet에는 BatchNorm이 없고 분류기에 Dropout(p=0.5)이 두 개 있습니다."}
```


### 학습 단계에서만 backward와 step 부르기
<!-- facts: FA05-b3 -->

2단계 함수에서 backward와 step을 부르는 두 줄은 dset이 'train'일 때만 실행됩니다. 학습 사진 244장을 배치 8로 나누면 31배치이고 마지막 배치는 4장입니다. 학습 단계의 31배치는 모두 기울기 기록을 켠 채 손실을 구하고 backward와 step을 부르므로 step은 한 에폭에 31번 불립니다.

```ai-code-help
{"title": "작은 마지막 배치", "explanation": "drop_last를 지정하지 않은 DataLoader는 남은 사진을 작은 마지막 배치로 보냅니다. 학습 단계의 4장과 검증 단계의 1장이 그 마지막 배치입니다.", "reference": {"course": "intro", "lesson": "l15", "unit": "15d", "step": 3, "title": "마지막 배치를 작은 크기로 보내기"}}
```

검증 사진 153장은 20배치이고 마지막 배치는 1장입니다. 검증 단계의 20배치는 기록을 끈 채 순전파와 손실만 계산하고 step을 한 번도 부르지 않습니다. 검증 사진으로 파라미터를 바꾸지 않아야 검증 점수가 학습에 쓰지 않은 사진의 점수로 남습니다. 파라미터를 바꾸지 않으니 기울기 기록도 필요 없습니다. 기록을 끈 블록에서 만든 loss_curr는 requires_grad가 False입니다.

```figure
파일: assets/a5b-2.gif
캡션: 그림 7. 한 에폭에서 학습 31배치는 기록을 켜고 step을 부르고, 검증 20배치는 기록을 끄고 step을 부르지 않습니다.
내용: 위 띠는 학습 31배치, 아래 띠는 검증 20배치를 칸으로 나란히 놓았습니다. 마지막 칸은 남은 장수만큼 폭이 좁습니다. 학습 띠는 기록 켬이고 칸마다 step 호출 표시가 있습니다. 검증 띠는 기록 끔이고 step 호출 표시가 없습니다. 오른쪽 상자에 step 누적 횟수를 적었습니다.
프레임:
1. 학습 첫 배치 8장은 기울기 기록을 켜고 backward와 step을 부릅니다. step 누적은 1번입니다. (2000ms)
2. 학습 31번째 배치는 남은 4장이고 같은 순서를 거칩니다. step 누적은 31번입니다. (2000ms)
3. 검증 첫 배치 8장은 기울기 기록을 끄고 순전파와 손실만 계산합니다. step 누적은 31번에 머뭅니다. (2000ms)
4. 검증 20번째 배치는 남은 1장입니다. 한 에폭이 끝나도 step 누적은 31번입니다. (2000ms)
```
```ai-reveal
{"guess": "g1"}
```

2단계 함수의 `optimizer.zero_grad()`는 검증 배치에서도 불립니다. `zero_grad()`는 등록한 파라미터의 기울기를 비울 뿐 파라미터 값을 바꾸지 않습니다. 검증 단계에서는 step을 부르지 않으므로 이 줄을 backward 앞의 `if dset == 'train':` 블록 안으로 옮겨도 학습이 끝난 뒤의 파라미터는 같습니다.

`loss = 0.0` 줄은 학습 단계와 검증 단계가 시작될 때마다 손실 합 loss를 0.0으로 되돌립니다. 마지막 줄은 배치마다 `loss_curr.item() * imgs.size(0)`을 더합니다. 단계가 끝나면 이 합을 사진 수 244나 153으로 나눠 에폭 손실을 구합니다. 이렇게 더하면 마지막 배치가 4장, 1장으로 작아도 사진마다 같은 비중이 들어갑니다.

```ai-code-help
{"title": "배치 크기를 곱한 손실 합", "explanation": "배치 평균 손실에 그 배치의 사진 수를 곱해 더하고 전체 사진 수로 나눕니다. 학습 244장과 검증 153장의 마지막 배치도 같은 식으로 셉니다.", "reference": {"course": "intro", "lesson": "l16", "unit": "16f", "step": 3, "title": "샘플 수로 평균 손실 합치기"}}
```
```ai-recall
{"id": "r2", "q": "같은 자료로 10에폭을 돌면 optimizer.step()은 모두 ____ 번 불립니다.", "answer": ["310"], "mode": "number", "why": "학습 단계에서만 한 에폭에 31번 부르므로 31×10=310번입니다."}
```
```ai-why
{"q": "검증 배치에서도 optimizer.zero_grad()를 부르는데 파라미터가 바뀌지 않는 까닭은 무엇일까요?", "a": "zero_grad()는 기울기만 비웁니다. 파라미터를 바꾸는 step()은 학습 단계에서만 부릅니다."}
```


### 모듈 이름을 가리는 인자 이름 읽기
<!-- facts: FA05-b4 -->

2단계 코드는 옵티마이저 인자를 optimizer라고 불렀습니다. 강의 노트북은 같은 자리의 인자를 optim이라고 쓰고, 맨 앞에서 `import torch.optim as optim`으로 torch.optim 모듈도 optim이라는 이름으로 불러옵니다. 아래 코드는 그 노트북에서 optim이 나오는 줄만 모은 것입니다. 모델 인자와 옵티마이저 변수 이름은 이 노트에서 쓰는 이름으로 바꿨습니다.

```python
import torch.optim as optim

def finetune_model(model, loss_func, optim, epochs=10):
    ...
    optim.zero_grad()
    ...
    optim.step()

optimizer = optim.SGD(model_finetuned.parameters(), lr=0.0001)
finetune_model(model_finetuned, loss_func, optimizer)
```

`def` 줄의 인자 이름도 optim이라서 함수 안에서는 인자가 모듈 이름을 가립니다. 파이썬은 이름을 함수 안에서 먼저 찾기 때문입니다. 그래서 `optim.zero_grad()`와 `optim.step()`의 optim은 마지막 줄에서 넘겨받은 SGD 옵티마이저이고, 두 줄은 그 옵티마이저의 메서드를 부릅니다.

함수 밖에 있는 `optim.SGD` 줄의 optim은 여전히 torch.optim 모듈입니다. 함수 안에서 `optim.SGD`를 쓰면 넘겨받은 옵티마이저에 SGD라는 속성이 없어 AttributeError가 납니다. 이 노트의 코드는 인자를 optimizer라고 불러 함수 안팎에서 optim이 늘 모듈을 가리키게 합니다.

```figure
파일: assets/a5b-3.png
캡션: 그림 8. 함수 밖에서 optim은 torch.optim 모듈이고, 인자 이름이 optim인 함수 안에서는 넘겨받은 SGD 옵티마이저입니다.
내용: 큰 상자는 위 코드 전체이고 그 안의 작은 상자는 finetune_model 함수 안입니다. 큰 상자의 import 줄과 optim.SGD 줄에 있는 optim에서 torch.optim 모듈로 화살표가 갑니다. 작은 상자 안의 인자 optim, optim.zero_grad(), optim.step()에서는 넘겨받은 SGD 옵티마이저로 화살표가 갑니다.
```
```ai-recall
{"id": "r3", "q": "인자 이름이 optim인 함수 안에서 optim.SGD(...)를 부르면 ____ 오류가 납니다.", "answer": ["AttributeError"], "mode": "code", "why": "함수 안의 optim은 넘겨받은 옵티마이저 객체이고, 이 객체에는 SGD라는 속성이 없습니다."}
```
```ai-why
{"q": "인자 이름을 optim으로 써도 학습은 제대로 됩니다. 그래도 이 노트에서 optimizer로 바꿔 쓰는 까닭은 무엇일까요?", "a": "같은 이름이 줄마다 다른 대상을 가리키면 코드를 읽을 때 헷갈립니다. 함수 안에서 optim.Adam(...)처럼 옵티마이저를 새로 만들려고 하면 AttributeError가 납니다."}
```


### 백본까지 바꾸는 미세 조정 읽기
<!-- facts: FA05-b5 -->

4단계에서 함수에 넘긴 옵티마이저는 `optim.SGD(model_finetuned.parameters(), lr=0.0001)`로 만들었습니다. `parameters()`는 features와 classifier를 합친 모델 전체의 파라미터를 돌려줍니다. classifier[6]을 `Linear(4096, 2)`로 바꾼 AlexNet의 파라미터는 57,012,034개이고 새 층은 그 가운데 8,194개입니다.

사전학습 가중치를 불러온 파라미터도 requires_grad가 True입니다. 그래서 학습 배치마다 backward가 57,012,034개 파라미터의 기울기를 모두 구하고, step이 백본을 포함한 모든 파라미터를 바꿉니다.

옵티마이저에 classifier[6]의 파라미터만 넘기면 step은 8,194개만 바꿉니다.

```figure
파일: assets/a5b-4.png
캡션: 그림 9. model_finetuned.parameters()를 넘기면 57,012,034개를 모두 바꾸고, classifier[6]만 넘기면 8,194개만 바꿉니다.
내용: 위아래 두 줄에 features, classifier 앞쪽 층, classifier[6] 상자를 차례로 놓았습니다. 위 줄은 세 상자를 모두 칠하고 오른쪽에 57,012,034개를 적었습니다. 아래 줄은 classifier[6]만 칠하고 오른쪽에 8,194개를 적었습니다. 칠한 상자는 step이 바꾸는 파라미터이고 상자 폭은 축척이 없습니다.
```

```ai-code-help
{"title": "고정 특징 추출과 미세 조정", "explanation": "이 함수는 백본을 고정하지 않고 전체 파라미터를 옵티마이저에 넘깁니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13a", "step": 3, "title": "고정할 범위 먼저 정하기"}}
```
```ai-code-help
{"title": "기울기 계산과 바꿀 대상", "explanation": "requires_grad는 기울기를 구할지 정하고, 옵티마이저에 넘긴 파라미터 목록은 step이 바꿀 대상을 정합니다.", "reference": {"course": "intro", "lesson": "l14", "unit": "14b", "step": 2, "title": "계산할 기울기와 바꿀 가중치 목록 구분하기"}}
```
```ai-recall
{"id": "r4", "q": "model_finetuned.parameters()를 넘긴 SGD의 step은 features의 가중치도 ____.", "answer": ["바꿉니다", "바꾼다", "갱신합니다"], "mode": "word", "why": "parameters()가 features를 포함한 모델 전체의 파라미터를 옵티마이저에 넘기기 때문입니다."}
```


### 외울 것
<!-- facts: FA05-b1 FA05-b3 -->

```ai-memo
[{"q": "조건 값 하나로 with 블록 안의 기울기 기록을 켜고 끄는 코드는 무엇인가요?", "a": "with torch.set_grad_enabled(mode):입니다. mode가 True이면 켜고 False이면 끕니다.", "cards": ["a05-b08"]}, {"q": "학습 단계에서만 기울기 기록을 켜려면 set_grad_enabled에 무엇을 넘기나요?", "a": "dset == 'train'을 넘깁니다. 학습 단계에서는 True, 검증 단계에서는 False가 됩니다.", "cards": ["a05-b06"]}, {"q": "검증 단계에서 계산한 loss_curr의 requires_grad는 무엇인가요?", "a": "기울기 기록을 끈 블록에서 계산해 False입니다. 검증 단계는 파라미터를 바꾸지 않으므로 기록이 필요 없습니다.", "cards": ["a05-b09"]}]
```


## 손실 기준과 정확도 기준으로 고른 에폭 비교하기


### 먼저 풀어 보기
<!-- facts: FA05-c1 -->

```ai-guess
{"id": "g1", "q": "둘째 단원의 finetune_model은 검증 정확도가 지금까지의 최고보다 클 때만 가중치를 복사합니다. 0부터 센 7·8·9번 에폭의 검증 정확도가 모두 0.9020이면 학습이 끝난 뒤 어느 에폭의 가중치가 남을까요?", "options": ["7번 에폭", "9번 에폭"], "answer": 0, "reveal_step": 3, "cards": ["a05-b11"]}
```


### 정확도가 더 클 때만 가중치 복사하기
<!-- facts: FA05-c1 -->

1단계 물음의 0.9020은 강의 노트북에 저장된 AlexNet 학습 로그의 검증 정확도입니다. 이 단원에 나오는 값은 모두 이 저장된 로그에서 읽었고 다시 실행해 얻은 값이 아닙니다. 검증 사진은 153장이고 0.9020은 그 가운데 138장을 맞힌 값입니다.

아래 코드는 finetune_model에서 가장 좋은 가중치를 고르는 줄만 남긴 것입니다. 둘째 단원 2단계의 코드에서는 이 부분을 뺐습니다.

```python
accuracy = 0.0
model_weights = copy.deepcopy(model.state_dict())
for e in range(epochs):
    for dset in ['train', 'val']:
        # 학습 또는 검증을 마치고 accuracy_epoch 를 계산함
        if dset == 'val' and accuracy_epoch > accuracy:
            accuracy = accuracy_epoch
            model_weights = copy.deepcopy(model.state_dict())
model.load_state_dict(model_weights)
```

첫 줄의 accuracy는 지금까지 나온 가장 높은 검증 정확도를 담으며 0.0에서 시작합니다. 둘째 줄은 학습을 시작하기 전의 가중치를 먼저 복사해 둡니다. accuracy_epoch는 이번 에폭에서 맞힌 장수를 전체 장수로 나눈 정확도입니다. 여섯째 줄은 val 단계가 끝날 때마다 accuracy_epoch를 accuracy와 비교합니다. 비교가 참이면 일곱째 줄과 여덟째 줄이 최고값과 가중치 사본을 함께 바꿉니다. 반복이 끝나면 마지막 줄이 가장 나중에 복사한 가중치를 모델에 다시 넣습니다.
```ai-code-help
{"title": "state_dict와 deepcopy", "explanation": "state_dict()가 돌려주는 사전의 텐서는 학습 중인 모델과 저장소를 함께 씁니다. deepcopy로 그 시점의 값을 따로 복사해야 뒤의 학습에서 값이 바뀌지 않습니다.", "reference": {"course": "intro", "lesson": "l10", "unit": "10e", "step": 4, "title": "좋았던 시점의 텐서 따로 복사하기"}}
```

로그의 번호는 0부터 셉니다. 저장된 로그에는 `epoch_number 0 / 9`부터 `epoch_number 9 / 9`까지 찍혀 있습니다. finetune_model을 epochs 기본값 10으로 부르므로 셋째 줄의 `range(epochs)`가 e에 0부터 9까지 차례로 넣습니다. 개론 10차시의 조기 종료 예는 에폭을 1부터 셌습니다. 이 단원의 7번 에폭은 1부터 세면 여덟째 에폭입니다.

저장된 로그에서 0번 에폭의 검증 정확도는 0.7124입니다. 0.0보다 크므로 여섯째 줄의 비교가 참이 되어 복사합니다. 1번부터 4번 에폭까지는 0.8170, 0.8627, 0.8824, 0.8954로 매번 이전 최고보다 커서 에폭마다 복사합니다. 4번 에폭이 끝났을 때 accuracy는 0.8954이고 model_weights는 4번 에폭의 사본입니다.

```figure
파일: assets/a5c-1.png
캡션: 그림 10. 저장된 로그에서 0~4번 에폭의 검증 정확도는 매번 이전 최고보다 커서 에폭마다 가중치를 복사합니다.
내용: 표의 행은 0부터 4번 에폭입니다. 열은 검증 정확도, 비교 직전의 accuracy, 비교 결과, 복사 여부입니다. 0번은 0.7124와 0.0, 1번은 0.8170과 0.7124, 2번은 0.8627과 0.8170, 3번은 0.8824와 0.8627, 4번은 0.8954와 0.8824이며 다섯 행 모두 비교가 참이고 복사합니다. 아래에 저장된 로그라고 적었습니다.
```

```ai-recall
{"id": "r1", "q": "저장된 로그의 0번부터 4번 에폭까지 여섯째 줄의 비교가 참이 된 횟수는 ____ 번입니다.", "answer": ["5"], "mode": "number", "why": "0번의 0.7124부터 4번의 0.8954까지 다섯 값이 모두 이전 최고보다 큽니다."}
```


### 같은 최고값이 다시 나올 때 남는 에폭 찾기
<!-- facts: FA05-c1 -->

2단계 끝에서 accuracy는 0.8954였습니다. 5번과 6번 에폭도 137장을 맞혀 검증 정확도가 0.8954입니다. 0.8954 > 0.8954는 거짓이라 복사하지 않고 model_weights는 4번 에폭의 사본으로 남습니다. 7번 에폭에서 138장을 맞혀 0.9020으로 오르면 비교가 참이 되어 복사합니다. 8번과 9번 에폭은 0.9020으로 7번과 같아 복사하지 않습니다. 반복이 끝난 뒤 마지막 줄이 불러오는 가중치는 7번 에폭의 것입니다.

```ai-reveal
{"guess": "g1"}
```

여섯째 줄의 비교 기호를 `>=`로 바꾸면 같은 값에서도 비교가 참이 됩니다. 이 로그에서는 5·6번과 8·9번에서도 복사가 일어나 9번 에폭의 가중치가 남습니다.

```figure
파일: assets/a5c-2.gif
캡션: 그림 11. 저장된 로그의 검증 정확도를 에폭 순서로 놓고, > 비교와 >= 비교가 가중치를 복사하는 에폭을 견줍니다.
내용: 가로축은 0부터 9까지의 에폭 번호, 세로축은 검증 정확도입니다. 4~6번은 0.8954, 7~9번은 0.9020으로 평평한 구간입니다. 복사한 에폭은 채운 점, 건너뛴 에폭은 빈 점으로 찍고 마지막 장에서 두 비교 기호가 남기는 에폭을 나란히 적습니다.
프레임:
1. 0번부터 4번 에폭까지 검증 정확도가 매번 올라 다섯 번 모두 복사합니다. (2000ms)
2. 5번과 6번은 0.8954로 4번과 같아 > 비교에서는 복사하지 않습니다. 남은 사본은 4번 에폭의 것입니다. (2200ms)
3. 7번에서 0.9020으로 올라 복사하고 8번과 9번은 같은 값이라 건너뜁니다. 불러오는 가중치는 7번 에폭의 것입니다. (2200ms)
4. 같은 로그에 >= 비교를 쓰면 5·6·8·9번에서도 복사해 9번 에폭의 가중치가 남습니다. (2200ms)
```

```ai-recall
{"id": "r2", "q": "여섯째 줄의 비교 기호를 >= 로 바꾸면 저장된 로그의 0번부터 9번 에폭까지 가중치 복사는 모두 ____ 번 일어납니다.", "answer": ["10"], "mode": "number", "why": "검증 정확도가 한 번도 내려가지 않아 열 에폭 모두 이전 최고 이상입니다."}
```

```ai-why
{"q": ">와 >= 가운데 어느 쪽이 맞는 코드일까요?", "a": "둘 다 동작합니다. 같은 최고값이 다시 나오면 >는 먼저 도달한 에폭을, >=는 나중 에폭을 남깁니다. 어느 쪽을 쓸지 실험 전에 정해 둡니다."}
```

```ai-levels
{"id": "v1", "concept": "같은 최고값", "levels": [{"level": 7, "text": "사진 153장을 세 번 보여 주고 맞힌 장수를 셌습니다. 맞힌 장수는 차례로 137, 138, 138입니다. 앞선 최고보다 더 많이 맞힌 차례에만 그때의 모델을 따로 보관합니다.", "q": "끝까지 남는 모델을 보관한 차례를 숫자로 쓰면 ____ 입니다.", "answer": ["2"], "mode": "number", "why": "셋째 차례의 138장은 둘째 차례의 138장보다 많지 않아서 새로 보관하지 않습니다.", "figure": {"file": "assets/a5c-31.png", "caption": "세 번 보여 주고 맞힌 장수를 차례로 놓았습니다.", "content": "첫째 137장, 둘째 138장, 셋째 138장을 적은 상자 세 개를 왼쪽부터 화살표로 이었습니다."}}, {"level": 15, "text": "에폭 번호를 0부터 셉니다. 3번 에폭까지 가장 많이 맞힌 장수는 135장이고 4·5·6번 에폭에서는 모두 137장을 맞혔습니다. 정확도는 맞힌 장수를 153으로 나눈 값이라 4번 에폭은 137 ÷ 153 ≈ 0.8954입니다. 이번에는 이전 최고와 같은 값이 나와도 보관하는 규칙을 씁니다.", "q": "6번 에폭이 끝난 뒤 남아 있는 모델은 ____ 번 에폭의 것입니다.", "answer": ["6"], "mode": "number", "why": "4번은 137 > 135라서 보관하고, 5번과 6번은 맞힌 장수가 137 = 137로 최고와 같아서 보관합니다. 마지막으로 보관한 것은 6번입니다.", "figure": {"file": "assets/a5c-32.png", "caption": "3~6번 에폭의 맞힌 장수와 정확도를 표로 놓았습니다.", "content": "표의 열은 에폭 3, 4, 5, 6입니다. 맞힌 장수 행은 135, 137, 137, 137이고 정확도 행은 0.8824, 0.8954, 0.8954, 0.8954입니다."}}, {"level": 20, "text": "비교 기호가 >이면 이전 최고와 같은 값에서 조건이 거짓이라 복사하지 않습니다. 그래서 최고값이 여러 번 나오면 그 값이 처음 나온 에폭이 남습니다. 아래 코드는 finetune_model의 비교만 떼어 0부터 센 위치를 kept에 담습니다.", "code": "best, kept = 0.0, None\nfor e, acc in enumerate(accs):\n    if acc > best:\n        best, kept = acc, e", "mistake": "같은 최고값이 뒤에 다시 나오면 kept도 뒤로 옮겨 간다고 착각하기 쉽습니다. 같은 값에서는 조건이 거짓이라 kept가 바뀌지 않습니다.", "q": "accs = [0.6, 0.8, 0.8, 0.7, 0.8]이면 반복이 끝난 뒤 kept는 ____ 입니다.", "answer": ["1"], "mode": "number", "why": "0.8이 처음 나온 위치 1에서 복사한 뒤 위치 2와 4의 0.8은 best와 같아 조건이 거짓입니다.", "figure": {"file": "assets/a5c-33.png", "caption": "다른 목록 [0.5, 0.7, 0.7]에서 비교 결과와 kept가 바뀌는 과정을 따라갑니다.", "content": "표의 행은 위치 0, 1, 2입니다. 열은 acc, 비교 직전의 best, acc > best의 결과, 반복 뒤 kept입니다. 위치 0은 0.5와 0.0으로 참이고 kept는 0, 위치 1은 0.7과 0.5로 참이고 kept는 1, 위치 2는 0.7과 0.7로 거짓이고 kept는 1입니다."}}]}
```


### 손실 기준과 정확도 기준이 고르는 에폭 비교하기
<!-- facts: FA05-c2 FA05-c4 -->

3단계에서 정확도 기준은 7번 에폭을 남겼습니다. 같은 로그의 검증 손실은 0번 에폭의 0.5955에서 9번 에폭의 0.2898까지 에폭마다 줄었습니다. 개론 15차시 다섯째 단원 5단계처럼 검증 손실이 가장 작은 상태를 보관했다면 9번 에폭의 가중치가 남습니다.

```ai-code-help
{"title": "검증 손실이 가장 작은 상태 보관", "explanation": "검증 손실이 이전 최솟값보다 작을 때 state_dict의 사본을 바꿉니다. 이 단원의 정확도 기준과 견주면 비교하는 값과 부등호 방향이 다릅니다.", "reference": {"course": "intro", "lesson": "l15", "unit": "15e", "step": 5, "title": "심화 검증 손실이 가장 작았던 상태 보관하기"}}
```

정확도는 맞힌 장수를 153으로 나눈 값이라 한 장을 더 맞혀야 오릅니다. 7·8·9번 에폭은 모두 138장을 맞혀 정확도가 같습니다.

```ai-code-help
{"title": "검증 자료의 한 장 차이", "explanation": "정확도는 맞힌 장수를 전체 장수로 나눈 값이라 한 장 단위로만 바뀝니다. 검증 자료가 적을수록 한 장 차이가 큽니다.", "reference": {"course": "intro", "lesson": "l15", "unit": "15e", "step": 4, "title": "적은 검증 자료의 한 장 차이 구분하기"}}
```

검증 손실은 사진마다 정답 클래스의 확률로 구한 교차 엔트로피를 153장에서 평균한 값입니다.

```ai-code-help
{"title": "교차 엔트로피", "explanation": "정답 클래스의 소프트맥스 확률이 클수록 그 사진의 손실이 작습니다. nn.CrossEntropyLoss()는 소프트맥스, log, 정답 칸 고르기를 안에서 모두 합니다.", "reference": {"course": "intro", "lesson": "l06", "unit": "6d", "step": 2, "title": "소프트맥스, log, 정답 칸을 거쳐 나오는 손실 0.417"}}
```

맞힌 장수가 같아도 정답 클래스의 확률이 커지면 손실은 줄어듭니다. 7번부터 9번 에폭까지 맞힌 장수는 138장으로 같지만 손실은 0.3050, 0.2958, 0.2898로 줄었습니다.

<u>정확도 기준과 손실 기준은 같은 로그에서도 서로 다른 에폭을 고를 수 있습니다.</u> 이 로그 하나만으로 어느 기준이 낫다고 정하지 않습니다. 모델을 고를 지표는 실험 전에 정해 둡니다. 같은 최고값이 다시 나왔을 때 어느 에폭을 남길지도 함께 정합니다.

```ai-code-help
{"title": "보관한 상태와 마지막 상태", "explanation": "멈추는 규칙과 최고 모델을 고르는 지표는 실험 전에 정합니다. 보관한 상태는 학습이 끝난 마지막 상태와 다를 수 있습니다.", "reference": {"course": "intro", "lesson": "l12", "unit": "12c", "step": 3, "title": "보관한 상태와 마지막 상태 구분하기"}}
```

finetune_model은 검증 사진 153장으로 에폭을 고르고 마지막에 같은 사진의 최고 정확도 0.9020을 찍습니다. 이 점수는 고르는 데 쓴 점수라서 새 사진에서 나올 정확도로 읽지 않습니다. 개미·벌 자료에는 학습과 검증 폴더만 있고 따로 떼어 둔 테스트 자료가 없습니다.

```ai-code-help
{"title": "고르는 자료와 최종 확인 자료", "explanation": "검증 자료로 설정과 저장할 모델을 고르고, 고른 뒤에는 따로 둔 테스트 자료로 최종 결과를 확인합니다.", "reference": {"course": "intro", "lesson": "l16", "unit": "16g", "step": 6, "title": "모델을 고르는 자료와 최종 확인 자료 나누기"}}
```

```figure
파일: assets/a5c-3.png
캡션: 그림 12. 저장된 같은 로그에서 검증 손실이 가장 작은 9번 에폭과, > 로 비교한 정확도 기준이 남긴 7번 에폭을 나란히 표시합니다.
내용: 왼쪽 그래프는 0~9번 에폭의 검증 손실이 0.5955에서 0.2898까지 줄어드는 선이고 9번에 표시가 있습니다. 오른쪽 그래프는 같은 에폭의 검증 정확도 계단이고 4~6번 0.8954, 7~9번 0.9020 구간 가운데 7번에 표시가 있습니다. 두 그래프의 가로축은 0부터 센 에폭 번호입니다.
```

```ai-recall
{"id": "r3", "q": "저장된 로그에서 검증 손실이 가장 작은 상태를 보관하면 남는 에폭은 ____ 번입니다.", "answer": ["9"], "mode": "number", "why": "검증 손실이 에폭마다 줄어 마지막 9번의 0.2898이 가장 작습니다."}
```

```ai-why
{"q": "7번과 9번은 검증 정확도가 같은데 왜 9번의 검증 손실이 더 작을까요?", "a": "정확도는 맞힌 장수만 셉니다. 손실은 사진마다 정답 클래스의 확률을 반영하므로 맞힌 장수가 같아도 정답 확률이 커지면 줄어듭니다."}
```


### 시각화가 늘 같은 네 장을 보이는 이유
<!-- facts: FA05-c3 -->

4단계까지는 두 기준이 남기는 에폭을 숫자로 비교했습니다. 학습을 마친 뒤 부르는 visualize_predictions 함수는 검증 사진 네 장의 예측과 정답을 2×2로 보입니다. 이 함수를 몇 번 불러도 같은 네 장이 나옵니다.

함수는 dloaders['val']을 처음부터 읽다가 네 장을 채우면 멈춥니다. 검증 로더는 `shuffle=False`로 만들어서 부를 때마다 표본을 같은 순서로 꺼냅니다.

```ai-code-help
{"title": "검증 로더의 순서", "explanation": "shuffle은 에폭마다 표본 순서를 섞을지 정합니다. 검증용은 같은 순서로 두면 파일별 예측을 추적하기 쉽습니다.", "reference": {"course": "intro", "lesson": "l15", "unit": "15d", "step": 4, "title": "훈련과 검증의 순서 정하기"}}
```

ImageFolder는 클래스 폴더 이름과 파일 이름을 정렬해 표본 목록을 만듭니다. ants가 0번 클래스라서 검증 로더의 앞 네 장은 ants 폴더의 앞 네 파일입니다. 검증 변환은 `Resize(256)`과 `CenterCrop(224)`라 무작위로 바꾸는 단계가 없습니다. 함수 안에서 `eval()`을 부르면 Dropout이 값을 0으로 바꾸지 않아 같은 가중치에서는 예측도 같습니다. 검증 경로에 무작위 요소가 없으니 시드를 정하지 않아도 같은 네 장이 나옵니다. 저장된 로그 아래에 남은 예측 그림에서도 네 장 모두 정답이 ants입니다.

```ai-code-help
{"title": "ImageFolder의 클래스 번호", "explanation": "ImageFolder는 폴더 이름을 정렬한 순서로 0부터 번호를 붙입니다. ants와 bees면 ants가 0번입니다.", "reference": {"course": "intro", "lesson": "l15", "unit": "15a", "step": 3, "title": "실제 정렬 결과를 메타데이터에서 읽기"}}
```

함수는 처음에 `model.training` 값을 변수에 담아 두고 `eval()`로 바꿔 예측합니다. 끝날 때는 `train(담아 둔 값)`으로 함수를 부르기 전의 모드로 되돌립니다.

```ai-code-help
{"title": "원래 모드 기록과 복원", "explanation": "training 속성은 train() 모드에서 True, eval() 모드에서 False입니다. train(False)는 eval()과 같은 일을 합니다.", "reference": {"course": "intro", "lesson": "l12", "unit": "12g", "step": 2, "title": "모델의 원래 모드를 확인한 뒤 평가하기"}}
```

```figure
파일: assets/a5c-4.png
캡션: 그림 13. 검증 폴더의 정렬, 섞지 않는 로더, 고정된 검증 변환을 거쳐 시각화 함수가 매번 같은 네 장을 고릅니다.
내용: 왼쪽에서 오른쪽으로 상자 다섯 개가 화살표로 이어집니다. 첫 상자는 폴더 이름 정렬로 ants가 0번, bees가 1번입니다. 둘째는 파일 이름 정렬로 ants 폴더의 파일이 앞에 옵니다. 셋째는 shuffle=False 로더가 같은 순서로 8장씩 꺼냅니다. 넷째는 Resize(256)과 CenterCrop(224)로 무작위 단계가 없습니다. 다섯째는 첫 배치의 앞 네 장을 사진 대신 번호 칸으로 2×2에 놓고 네 칸 모두 정답 번호 0이라고 적었습니다.
```

```ai-recall
{"id": "r4", "q": "시각화 함수가 보이는 처음 네 장의 정답 클래스 번호는 모두 ____ 입니다.", "answer": ["0"], "mode": "number", "why": "정렬 결과 ants가 0번 클래스이고 검증 로더는 ants 폴더의 파일부터 꺼냅니다."}
```

```ai-why
{"q": "검증 로더를 shuffle=True로 바꾸면 무엇이 달라질까요?", "a": "부를 때마다 표본 순서가 섞여 다른 네 장이 나올 수 있습니다. eval()에서 사진마다 따로 예측하므로 검증 사진 전체로 센 정확도는 순서와 관계없이 같습니다."}
```


### 외울 것
<!-- facts: FA05-c1 FA05-c2 -->

```ai-memo
[{"q": "검증 정확도가 이전 최고보다 클 때만 가중치를 복사하려면 어떤 비교 기호를 쓰나요?", "a": "accuracy_epoch > accuracy처럼 >를 씁니다.", "cards": ["a05-b10"]}, {"q": "> 로 비교할 때 최고 정확도가 여러 에폭에 나오면 어느 에폭의 가중치가 남나요?", "a": "그 값이 처음 나온 에폭이 남습니다. 저장된 로그에서는 0부터 센 7번 에폭입니다.", "cards": ["a05-b11"]}, {"q": "같은 로그에서 손실 기준과 정확도 기준이 다른 에폭을 고를 수 있는 까닭은 무엇인가요?", "a": "정확도는 맞힌 장수가 바뀔 때만 오르고 손실은 정답 클래스의 확률이 커지면 계속 줄어듭니다. 저장된 로그에서는 손실 기준이 9번, 정확도 기준이 7번을 고릅니다.", "cards": ["a05-b13"]}]
```


## 1000개 출력 번호를 라벨 사전으로 이름 바꾸기


### 먼저 풀어 보기
<!-- facts: FA05-d3 -->

```ai-guess
{"id": "g1", "q": "개미 사진의 ImageFolder 라벨은 0입니다. 이 0을 ImageNet 라벨 사전 classes_dict에 그대로 넣으면 어떤 이름이 나올까요?", "options": ["ants", "tench, Tinca tinca", "bees"], "answer": 1, "reveal_step": 4, "cards": ["a05-b16"]}
```


### 1000개 점수에서 가장 큰 번호 고르기
<!-- facts: FA05-d1 -->

개미 사진 한 장을 이번에는 사전학습 VGG13으로 학습 없이 분류합니다. VGG13은 ImageNet의 1000개 클래스로 학습한 모델입니다. 학습하지 않으므로 파라미터 133,047,848개는 하나도 바뀌지 않습니다. 마지막 층을 바꾸지 않으면 사진 한 장마다 점수 1000개를 냅니다.

```python
model.eval()
with torch.no_grad():
    imgs, labels = next(iter(dloaders['val']))
    ops = model(imgs.to(dvc))
    _, preds = torch.max(ops, 1)
```

model은 ImageNet 가중치를 읽은 VGG13이고, 만드는 줄은 5단계에서 다룹니다. dloaders['val']은 배치 크기 8, `shuffle=False`로 만든 검증 로더입니다. dvc는 GPU가 있으면 cuda:0, 없으면 cpu입니다. 사진 8장을 넣으면 ops의 모양은 [8, 1000]입니다. `torch.max(ops, 1)`은 행마다 가장 큰 점수의 위치를 preds에 담습니다. preds의 값은 0부터 999까지의 ImageNet 번호입니다.

첫째 사진은 개미 사진입니다. 이 사진의 점수 가운데 307번부터 312번까지만 꺼내 봅니다. 아래 숫자는 설명을 위해 정한 값이고 모델을 실행한 결과가 아닙니다. 307번 1.2, 308번 2.1, 309번 6.4, 310번 8.3, 311번 0.7, 312번 1.5이고 나머지 994개는 모두 8.3보다 작다고 둡니다. 가장 큰 8.3이 310번에 있으니 preds[0]은 310입니다.

```figure
파일: assets/a5d-1.gif
캡션: 그림 14. 사진 한 장의 점수 1000개 가운데 307~312번을 꺼낸 설명용 값입니다. 가장 큰 8.3이 있는 310번이 예측 번호가 됩니다.
내용: 사진 한 장의 점수 1000개 가운데 307~312번을 꺼낸 설명용 값입니다. 가장 큰 8.3이 있는 310번이 예측 번호가 됩니다.
프레임:
1. 사진 한 장의 출력은 0번부터 999번까지 점수 1000개입니다. (1800ms)
2. 307~312번 점수는 1.2, 2.1, 6.4, 8.3, 0.7, 1.5인 설명용 값입니다. (2000ms)
3. 가장 큰 8.3이 310번에 있어 preds[0]에는 310이 담깁니다. (1800ms)
```

```ai-code-help
{"title": "행마다 가장 큰 점수의 위치", "explanation": "torch.max(ops, 1)은 1번 축을 따라 가장 큰 값과 그 위치를 함께 돌려줍니다. 여기서는 위치만 preds로 받아 ImageNet 번호로 씁니다.", "reference": {"course": "intro", "lesson": "l09", "unit": "9e", "step": 2, "title": "torch.max(outputs, 1)의 indices에서 예측 클래스 읽기"}}
```
```ai-code-help
{"title": "평가 모드와 기울기 기록 끄기", "explanation": "eval()은 Dropout 같은 층을 평가 동작으로 바꾸고 no_grad()는 기울기 기록을 끕니다. 가중치를 바꾸지 않는 추론이라 두 설정을 함께 씁니다.", "reference": {"course": "intro", "lesson": "l14", "unit": "14h", "step": 4, "title": "평가에는 모드 전환과 기록 중단 같이 쓰기"}}
```
```ai-code-help
{"title": "사전학습 모델로 추론만 하기", "explanation": "응용 4차시 RAFT도 사전학습 가중치를 고정하고 eval()과 no_grad() 안에서 결과만 계산했습니다. VGG13 추론도 같은 순서로 씁니다.", "reference": {"course": "applied", "lesson": "al04", "unit": "a4g", "step": 3, "title": "입력부터 반환값까지 코드로 연결하기"}}
```


### 정수 키 사전 파일을 literal_eval로 읽기
<!-- facts: FA05-d2 -->

2단계에서 얻은 310은 번호이고 이름이 아닙니다. 라벨 파일에는 번호와 이름이 파이썬 사전 문법으로 적혀 있습니다. 키는 정수 0부터 999까지이고 값은 따옴표로 감싼 이름입니다. 벌과 개미는 309: 'bee', 310: 'ant, emmet, pismire' 항목에 있습니다.

```python
import ast
with open(label_path) as f:
    text = f.read()
classes_dict = ast.literal_eval(text)
name = classes_dict[int(preds[0])]
```

label_path는 라벨 파일의 경로입니다. ast.literal_eval은 글에 적힌 파이썬 값을 실제 값으로 바꿉니다. classes_dict는 정수 키 1000개를 담은 사전이 되고 classes_dict[310]은 'ant, emmet, pismire'입니다.

마지막 줄의 `int(preds[0])`은 텐서 원소를 파이썬 정수로 바꿉니다. 텐서를 그대로 키로 넣으면 사전이 정수 키 310과 같은 키로 보지 않아 KeyError가 납니다.

같은 글 text를 json.loads로 읽으면 첫 키 0에서 JSONDecodeError가 납니다. JSON은 키를 큰따옴표 문자열로만 받는데 이 파일은 키가 정수이고 값도 대부분 작은따옴표로 감쌌습니다.

```figure
파일: assets/a5d-2.png
캡션: 그림 15. 같은 글 text를 ast.literal_eval은 정수 키 사전으로 읽고, json.loads는 첫 키 0에서 JSONDecodeError를 냅니다. 그림에는 글의 일부만 보였습니다.
내용: 맨 위에 라벨 파일 글의 일부를 줄여 적었고 첫 키 0 아래에 빨간 밑줄이 있습니다. 왼쪽은 ast.literal_eval이 309와 310을 정수 키로 읽은 표이고, 오른쪽은 json.loads가 첫 키 0에서 JSONDecodeError를 내는 상자입니다.
```
```ai-why
{"q": "키와 값을 큰따옴표로 바꿔 json.loads로 읽은 사전에서 classes_dict[310]을 찾으면 이름이 나올까요?", "a": "나오지 않습니다. JSON의 키는 문자열이라 읽은 사전의 키는 '310'입니다. 정수 310으로 찾으면 KeyError가 나므로 키를 int로 바꾼 사전을 다시 만들어야 합니다."}
```


### ImageFolder 번호와 ImageNet 번호 나란히 놓기
<!-- facts: FA05-d3 -->

3단계의 classes_dict는 0번부터 999번까지 1000개 번호에 이름을 붙입니다. 그런데 같은 개미 사진에 ImageFolder가 붙인 라벨은 0입니다. 개론 15차시 첫째 단원 3단계의 정렬 규칙대로 ImageFolder는 ants에 0, bees에 1을 붙이고 classes에 ['ants', 'bees']를 담습니다.

이 0을 classes_dict에 넣으면 물고기 이름 'tench, Tinca tinca'가 나옵니다. 0은 ImageFolder 목록의 번호이고 310은 ImageNet 목록의 번호라서 섞어 쓸 수 없습니다. ImageNet 목록에서 개미는 310번, 벌은 309번입니다.

<u>ImageFolder 라벨은 classes로, 1000개 출력에서 고른 번호는 classes_dict로 읽습니다.</u> 정답 라벨 0과 예측 310을 `==`로 비교하면 개미를 맞혀도 False가 나옵니다. 그래서 이 추론에서는 정답 라벨과 비교해 정확도를 내지 않고 예측 이름만 확인합니다.

```figure
파일: assets/a5d-3.png
캡션: 그림 16. 같은 개미 사진이 ImageFolder 목록에서는 0번, ImageNet 목록에서는 310번입니다. ImageNet 목록의 0번은 tench입니다.
내용: 같은 개미 사진이 ImageFolder 목록에서는 0번, ImageNet 목록에서는 310번입니다. ImageNet 목록의 0번은 tench입니다.
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r1", "q": "개미 사진의 정답 라벨 0과 예측 번호 310을 == 로 비교한 결과는 ____ 입니다.", "answer": ["False", "거짓"], "mode": "word", "why": "0은 ImageFolder 목록의 번호이고 310은 ImageNet 목록의 번호라 값이 다릅니다."}
```


### 가중치 인자와 권장 전처리 맞추기
<!-- facts: FA05-d4 -->

2단계부터 써 온 model은 아래 코드로 만듭니다. 응용 4차시 일곱째 단원 3단계의 RAFT처럼 `weights=`로 가중치를 고르고 `weights.transforms()`로 전처리를 얻습니다.

```python
weights = models.VGG13_Weights.IMAGENET1K_V1
model = models.vgg13(weights=weights).to(dvc)
preprocess = weights.transforms()
```

VGG13의 ImageNet 가중치는 VGG13_Weights.IMAGENET1K_V1입니다. 현재 torchvision에서는 VGG13_Weights.DEFAULT도 같은 가중치를 가리킵니다. weights를 넘기지 않으면 기본값 None이 쓰여 무작위로 초기화한 모델이 만들어집니다. 옛 코드의 `pretrained=True`도 IMAGENET1K_V1을 고르지만, torchvision 0.13부터는 weights를 쓰라는 경고가 함께 나옵니다.

preprocess는 이 가중치에 맞는 추론용 전처리입니다. 짧은 변을 256에 맞추고 가운데 224×224를 자른 뒤 0~1 범위로 바꿉니다. 마지막으로 평균 (0.485, 0.456, 0.406), 표준편차 (0.229, 0.224, 0.225)로 정규화합니다. 셋째 단원 5단계에서 본 검증 변환도 짧은 변을 256에 맞추고 224를 자릅니다. 그 뒤 정규화에는 평균 (0.490, 0.449, 0.411), 표준편차 (0.231, 0.221, 0.230)을 씁니다. 가중치를 학습할 때와 입력 조건을 맞추려면 preprocess를 쓰거나 그 평균·표준편차를 그대로 적습니다.
```figure
파일: assets/a5d-4.png
캡션: 그림 17. VGG13_Weights.IMAGENET1K_V1.transforms()와 셋째 단원의 검증 변환을 단계별로 나란히 놓았습니다. 크기 조절과 자르기는 같고 정규화 평균·표준편차가 다릅니다.
내용: 위 줄은 transforms()의 네 단계이고 아래 줄은 Resize(256), CenterCrop(224), ToTensor(), Normalize입니다. 앞 세 단계는 회색 테두리로 같다고 표시했고, 마지막 정규화 칸만 주황 굵은 테두리로 평균·표준편차가 다르다고 표시했습니다.
```
```ai-code-help
{"title": "가중치 버전과 변환", "explanation": "가중치 enum의 transforms()는 추론용 크기 조절과 정규화를 제공합니다. 학습 때 사진마다 무작위로 바꾸는 증강은 transforms()에 들어 있지 않습니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13g", "step": 4, "title": "가중치 버전과 변환의 역할 나누기"}}
```
```ai-code-help
{"title": "가중치와 전처리 함께 적기", "explanation": "결과를 비교할 때는 가중치 버전과 전처리를 함께 기록합니다. MobileNetV2처럼 DEFAULT가 V1이 아닌 가중치를 가리키는 모델도 있어서 IMAGENET1K_V1처럼 버전 이름을 적습니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13e", "step": 4, "title": "가중치와 전처리를 고정해 비교하기"}}
```


### 외울 것
<!-- facts: FA05-d1 FA05-d2 FA05-d3 -->

```ai-memo
[{"q": "사진 8장을 넣은 사전학습 VGG13의 출력은 어떤 모양인가요?", "a": "사진마다 점수 1000개라 [8, 1000]입니다.", "cards": ["a05-b18"]}, {"q": "정수 키로 적은 라벨 파일의 글을 사전으로 읽는 함수는 무엇인가요?", "a": "ast.literal_eval입니다. json.loads는 키를 큰따옴표 문자열로만 받아 이 글에서 JSONDecodeError를 냅니다.", "cards": ["a05-b15"]}, {"q": "개미 사진의 ImageFolder 라벨 0을 classes_dict에 넣으면 무엇이 나오나요?", "a": "ImageNet 0번 'tench, Tinca tinca'입니다. ImageFolder 라벨은 classes로 읽습니다.", "cards": ["a05-b16"]}]
```


## Inception 갈래를 합치고 코드에 적힌 층으로 계산량 세기


### 먼저 풀어 보기
<!-- facts: FA05-e1 FA05-e4 -->

이 단원의 GoogLeNet 코드는 Inception 모듈 아홉 개를 im1부터 im9까지 차례로 만듭니다. Inception 모듈은 입력 하나를 네 갈래에서 따로 계산한 뒤 결과를 합칩니다. 넷째 모듈 im4는 `InceptionModule(512, 160, 112, 224, 24, 64, 64)`입니다. 첫째 인자는 입력 채널이고 나머지 여섯은 네 갈래 층의 채널 수입니다.
```ai-guess
{"id": "g1", "q": "im4를 지난 출력의 채널은 몇 개일까요?", "options": ["512개", "648개", "64개"], "answer": 0, "reveal_step": 2, "cards": ["a05-b19"]}
```

```ai-guess
{"id": "g2", "q": "이 GoogLeNet 코드의 마지막 층은 nn.Linear(4096, 1000)입니다. 넣을 수 있는 정사각형 이미지의 한 변은 어느 쪽일까요?", "options": ["32", "224"], "answer": 0, "reveal_step": 5, "cards": ["a05-b22"]}
```


### 네 갈래의 출력 채널을 더해 다음 모듈과 맞추기
<!-- facts: FA05-e1 -->

1단계의 im4가 받는 인자 일곱 개는 아래 클래스의 `__init__`으로 들어갑니다.

```python
import torch
import torch.nn as nn

class InceptionModule(nn.Module):
    def __init__(self, in_planes, n1x1, n3x3red, n3x3,
                 n5x5red, n5x5, pool_planes):
        super().__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(in_planes, n1x1, kernel_size=1),
            nn.BatchNorm2d(n1x1), nn.ReLU(True))
        self.block2 = nn.Sequential(
            nn.Conv2d(in_planes, n3x3red, kernel_size=1),
            nn.BatchNorm2d(n3x3red), nn.ReLU(True),
            nn.Conv2d(n3x3red, n3x3, kernel_size=3, padding=1),
            nn.BatchNorm2d(n3x3), nn.ReLU(True))
        self.block3 = nn.Sequential(
            nn.Conv2d(in_planes, n5x5red, kernel_size=1),
            nn.BatchNorm2d(n5x5red), nn.ReLU(True),
            nn.Conv2d(n5x5red, n5x5, kernel_size=3, padding=1),
            nn.BatchNorm2d(n5x5), nn.ReLU(True),
            nn.Conv2d(n5x5, n5x5, kernel_size=3, padding=1),
            nn.BatchNorm2d(n5x5), nn.ReLU(True))
        self.block4 = nn.Sequential(
            nn.MaxPool2d(3, stride=1, padding=1),
            nn.Conv2d(in_planes, pool_planes, kernel_size=1),
            nn.BatchNorm2d(pool_planes), nn.ReLU(True))

    def forward(self, ip):
        outs = [self.block1(ip), self.block2(ip),
                self.block3(ip), self.block4(ip)]
        return torch.cat(outs, 1)
```

네 갈래는 코드의 block1부터 block4까지입니다. block1은 1×1 합성곱 한 층이고, block4는 최대 풀링 뒤에 1×1 합성곱을 둡니다. block2는 1×1 합성곱 뒤에 3×3 합성곱을 둡니다. block3은 인자 이름에 5x5가 있지만 실제로는 1×1 합성곱 뒤에 3×3 합성곱을 두 번 둡니다.

block2와 block3은 첫 1×1 합성곱에서 채널을 n3x3red개, n5x5red개로 줄여 같은 갈래의 다음 층에 넘깁니다. 이 첫 층 출력은 갈래 밖으로 나가지 않습니다. 인자 일곱 개는 차례로 입력 채널, block1 출력, block2 첫 층 출력, block2 출력, block3 첫 층 출력, block3 출력, block4 출력입니다. 인자 이름은 강의 노트북 예제의 n_channels1x1 같은 긴 이름을 줄여 쓴 것입니다.

각 합성곱 뒤에는 BatchNorm2d와 `nn.ReLU(True)`가 붙습니다. BatchNorm2d는 개론 12차시 넷째 단원 3단계에서 본 배치 정규화 층입니다. `nn.ReLU(True)`는 ReLU를 `inplace=True`로 만든 것입니다.

forward는 네 갈래에 같은 입력 ip를 넣고 `torch.cat(outs, 1)`로 결과를 1번 축에 이어 붙입니다. 1번 축이 채널 축이므로 <u>출력 채널은 block1부터 block4까지 네 갈래의 출력 채널을 더한 값입니다.</u> im4는 160 + 224 + 64 + 64 = 512이고 다음 모듈 im5의 입력 채널 512와 같습니다.

이어 붙이려면 네 갈래의 높이·너비가 같아야 합니다. 3×3 합성곱은 `padding=1`이라 크기가 바뀌지 않습니다. block4의 `MaxPool2d(3, stride=1, padding=1)`도 출력 한 변이 floor((H + 2 − 3) ÷ 1) + 1 = H라서 크기가 바뀌지 않습니다.

```ai-code-help
{"title": "채널 축으로 갈래 이어 붙이기", "explanation": "네 갈래의 출력은 배치와 높이·너비가 같고 채널 수만 다릅니다. torch.cat으로 1번 축을 따라 이으면 채널 수끼리 더해집니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13f", "step": 3, "title": "갈래의 공간을 맞춘 뒤 채널 이어 붙이기"}}
```

```figure
파일: assets/a5e-1.gif
캡션: 그림 18. im4의 네 갈래가 낸 160, 224, 64, 64 채널을 채널 축으로 이어 붙이면 512 채널이 되고, im5의 입력 512와 맞습니다.
내용: im4의 네 갈래가 낸 160, 224, 64, 64 채널을 채널 축으로 이어 붙이면 512 채널이 되고, im5의 입력 512와 맞습니다.
프레임:
1. block1~block4의 출력 160, 224, 64, 64 채널을 한 줄에 하나씩 막대로 놓습니다. 높이·너비는 모두 H×W입니다. (2000ms)
2. block2와 block3의 첫 층 출력 112와 24 채널은 옅은 막대로 놓습니다. 같은 갈래의 다음 층으로만 들어가는 채널이라 이어 붙이지 않습니다. (2200ms)
3. 진한 막대 넷을 채널 축을 따라 한 줄로 옮깁니다. (2200ms)
4. 이어 붙인 막대의 길이는 160 + 224 + 64 + 64 = 512 채널입니다. (2200ms)
5. 이 512가 다음 모듈 im5의 첫째 인자와 같습니다. (2000ms)
```

```ai-reveal
{"guess": "g1"}
```

```ai-recall
{"id": "r1", "q": "InceptionModule(528, 256, 160, 320, 32, 128, 128)을 지난 출력의 채널은 ____ 개입니다.", "answer": ["832"], "mode": "number", "why": "256 + 320 + 128 + 128 = 832입니다. block2와 block3의 첫 층 출력 160과 32는 더하지 않습니다."}
```

```ai-why
{"q": "im4의 block2 첫 층 출력 112와 block3 첫 층 출력 24를 모듈의 출력 채널에 더하지 않는 까닭은 무엇일까요?", "a": "두 값은 같은 갈래 안에서 다음 합성곱이 받는 채널 수입니다. torch.cat에는 갈래마다 마지막 층의 출력만 들어갑니다. 각 모듈의 출력 채널은 다음 모듈의 첫째 인자와 같습니다."}
```


### block3을 코드에 적힌 층으로 세기
<!-- facts: FA05-e2 -->

2단계에서 im4의 block3은 64 채널을 냈습니다. 이 64 채널은 2단계 코드의 self.block3에 적힌 1×1 합성곱 한 층과 3×3 합성곱 두 층이 만듭니다.

block3의 계산량은 위치 하나당 곱셈 수로 셉니다. 위치 하나당 곱셈 수는 출력의 높이·너비 위치 하나에서 모든 출력 채널 값을 만들 때 합성곱 층이 하는 곱셈의 수입니다. 합성곱 한 층이면 커널 높이 × 커널 너비 × 입력 채널 × 출력 채널입니다. bias 덧셈과 BatchNorm2d, ReLU는 넣지 않습니다.

아래 목록은 im4의 block3을 층마다 센 곱셈 수입니다.

- 1×1 합성곱, 512 → 24: 1 × 1 × 512 × 24 = 12,288번
- 3×3 합성곱, 24 → 64: 3 × 3 × 24 × 64 = 13,824번
- 3×3 합성곱, 64 → 64: 3 × 3 × 64 × 64 = 36,864번

세 층을 더하면 위치 하나당 62,976번입니다. 층마다 센 수는 개론 11차시 셋째 단원 3단계에서 센 weight 원소 수와 같습니다. 같은 weight를 모든 위치에서 다시 쓰므로 높이·너비가 H×W인 특징 맵 전체에서는 62,976 × H × W번 곱합니다. 파라미터 수는 H×W와 상관없이 같고 곱셈 수는 H×W에 비례합니다.

```ai-code-help
{"title": "3×3 두 층이 보는 범위", "explanation": "stride 1, padding 1인 3×3 합성곱을 두 번 지나면 출력 한 칸이 원래 입력의 5×5 범위를 봅니다. 입력과 출력 채널이 모두 c로 같다면 위치 하나당 곱셈은 3×3 두 층이 18 × c × c번, 5×5 한 층이 25 × c × c번입니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13f", "step": 2, "title": "이전 모델의 계산을 다른 배치로 이어가기"}}
```

```figure
파일: assets/a5e-2.png
캡션: 그림 19. im4 block3의 세 합성곱 층과 층마다 센 위치 하나당 곱셈 수입니다. bias와 BatchNorm2d, ReLU는 세지 않았습니다.
내용: 1×1 512→24 는 12,288번, 3×3 24→64 는 13,824번, 3×3 64→64 는 36,864번이고 합은 62,976번입니다.
```

```ai-recall
{"id": "r2", "q": "im7은 InceptionModule(528, 256, 160, 320, 32, 128, 128)입니다. block3을 같은 방법으로 세면 위치 하나당 곱셈 수는 ____ 번입니다.", "answer": ["201216"], "mode": "number", "why": "block3은 1×1 528→32, 3×3 32→128, 3×3 128→128입니다. 16,896 + 36,864 + 147,456 = 201,216입니다."}
```

```ai-why
{"q": "im4의 block3 곱셈 수를 셀 때 앞의 1×1 층도 넣는 까닭은 무엇일까요?", "a": "1×1 층도 출력 위치마다 512 채널을 받아 24 채널을 만드는 합성곱입니다. 위치 하나에서 12,288번 곱합니다. 이 층을 빼고 3×3 두 층만 더한 값은 block3 전체의 곱셈 수가 아닙니다."}
```

```ai-levels
{"id": "v1", "concept": "위치 하나당 곱셈 수", "levels": [{"level": 7, "text": "한 자리에 들어오는 값이 3개 있습니다. 이 자리에서 나가는 값 2개를 만듭니다. 나가는 값 하나를 만들 때마다 들어온 값 3개에 서로 다른 수를 하나씩 곱합니다.", "q": "이 자리에서 하는 곱셈은 모두 ____ 번입니다.", "answer": ["6"], "mode": "number", "why": "나가는 값 하나마다 세 번 곱하고, 나가는 값이 두 개라 여섯 번입니다.", "figure": {"file": "assets/a5e-31.png", "caption": "들어오는 값 3개와 나가는 값 2개를 모두 선으로 이었습니다.", "content": "왼쪽에 들어오는 값 3개, 오른쪽에 나가는 값 2개가 있고 모든 쌍이 선으로 이어져 있습니다. 선마다 곱셈을 한 번 합니다."}}, {"level": 15, "text": "3×3 합성곱은 출력 채널 하나를 만들 때 칸 9개와 입력 채널 전부에 weight를 하나씩 곱합니다. block3의 둘째 층은 24 채널을 받아 64 채널을 내므로 9 × 24 × 64 = 13,824번입니다.", "q": "같은 3×3 층의 출력 채널을 64에서 32로 줄이면 위치 하나당 곱셈 수는 ____ 번입니다.", "answer": ["6912"], "mode": "number", "why": "9 × 24 × 32 = 6,912입니다. 출력 채널이 절반이면 곱셈 수도 절반입니다.", "figure": {"file": "assets/a5e-32.png", "caption": "칸 수, 입력 채널, 출력 채널을 곱해 한 층의 곱셈 수를 셉니다.", "content": "칸 9, 입력 채널 24, 출력 채널 64를 한 줄에 놓고 곱한 결과 13,824를 적은 표입니다."}}, {"level": 20, "text": "합성곱 층의 위치 하나당 곱셈 수는 k × k × 입력 채널 × 출력 채널입니다. 이 값은 bias를 뺀 weight 원소 수와 같습니다. 아래 코드는 im4에서 block3 출력 n5x5를 96으로 바꾸고 세 층을 더합니다.", "q": "코드를 실행하면 mults는 ____ 입니다.", "answer": ["115968"], "mode": "number", "why": "12,288 + 3 × 3 × 24 × 96 + 3 × 3 × 96 × 96 = 12,288 + 20,736 + 82,944 = 115,968입니다. 두 3×3 층이 모두 n5x5를 쓰므로 둘 다 바뀝니다.", "code": "layers = [(1, 512, 24), (3, 24, 96), (3, 96, 96)]\nmults = sum(k * k * cin * cout for k, cin, cout in layers)", "mistake": "3×3 두 층만 더하고 앞의 1×1 층을 빠뜨리기 쉽습니다. 1×1 층도 출력 위치마다 입력 채널 전체를 받아 곱셈을 합니다.", "figure": {"file": "assets/a5e-33.png", "caption": "layers의 세 항목을 weight 모양으로 바꿔 놓았습니다.", "content": "세 층의 weight 모양 [24, 512, 1, 1], [96, 24, 3, 3], [96, 96, 3, 3]을 차례로 놓았습니다. 원소 수의 합은 적지 않았습니다."}}]}
```


### 5×5 구성과 같은 출력으로 비교하기
<!-- facts: FA05-e2 FA05-e3 -->

3단계에서 센 im4의 block3은 위치 하나당 62,976번 곱했습니다. 같은 자리에 1×1 합성곱 뒤 5×5 합성곱 한 층을 두는 구성도 있습니다. GoogLeNet 원 논문은 이 자리에 1×1·5×5 구성을 둡니다. 같은 채널 수로 세면 1×1 512 → 24는 12,288번, 5×5 24 → 64는 5 × 5 × 24 × 64 = 38,400번이라 합이 50,688번입니다.

im4에서는 1×1·3×3·3×3 구성의 3×3 두 층만 더해도 13,824 + 36,864 = 50,688이 나옵니다. 두 값이 같아진 것은 입력 512, 첫 층 출력 24, block3 출력 64라는 채널 수 조합에서 생긴 우연입니다. im3인 `InceptionModule(480, 192, 96, 208, 16, 48, 64)`로 세면 3×3 두 층만 27,648번, 1×1·5×5 구성 26,880번, 1×1·3×3·3×3 구성 35,328번으로 셋이 모두 다릅니다.

이번에는 1×1 합성곱으로 채널을 줄이지 않고 5×5 한 층으로 512 채널을 받아 64 채널을 바로 만들어 봅니다. 5 × 5 × 512 × 64 = 819,200번입니다. 세 계산 모두 64 채널을 내므로 바로 견줄 수 있습니다. 819,200은 1×1·3×3·3×3 구성의 약 13.0배, 1×1·5×5 구성의 약 16.2배입니다.

1×1 합성곱 없이 5×5 한 층이 512 채널을 받아 512 채널을 내면 위치 하나당 5 × 5 × 512 × 512 = 6,553,600번 곱합니다. 이 값을 1×1·5×5 구성의 50,688로 나누면 약 129가 나옵니다. 그런데 한쪽은 512 채널, 다른 쪽은 64 채널을 내므로 같은 출력을 만드는 계산끼리 견준 값이 아닙니다. <u>계산량을 비교할 때는 출력 채널과 높이·너비를 맞춥니다.</u>

네 갈래가 모두 높이·너비를 지키므로 위치 하나당 곱셈 수의 비는 특징 맵 전체의 곱셈 수 비와 같습니다. 곱셈 수의 비가 실행 시간의 비와 같지는 않습니다.

```figure
파일: assets/a5e-3.png
캡션: 그림 20. 왼쪽은 block3 자리에 둘 수 있는 두 구성이고 오른쪽은 출력 64 채널을 내는 세 계산의 위치 하나당 곱셈 수입니다. bias는 세지 않았습니다.
내용: 왼쪽에 1×1·3×3·3×3 구성(12,288, 13,824, 36,864)과 1×1·5×5 구성(12,288, 38,400)의 층별 곱셈 수를 막대 두 개에 쌓아 나란히 놓았습니다. 오른쪽 막대는 62,976, 50,688, 819,200이고 세로축 이름은 위치 하나당 곱셈 수(bias 제외)입니다.
```

```ai-recall
{"id": "r3", "q": "6,553,600 ÷ 819,200은 ____ 입니다.", "answer": ["8"], "mode": "number", "why": "두 계산은 출력 채널만 512와 64로 다릅니다. 6,553,600 ÷ 50,688 ≈ 129.3을 8로 나누면 약 16.2이고, 819,200 ÷ 50,688과 같은 값입니다."}
```

```ai-why
{"q": "1×1·3×3·3×3 구성의 곱셈 수는 512 채널을 받아 64 채널을 바로 만드는 5×5 한 층의 약 13분의 1입니다. 실행 시간도 13분의 1로 줄어들까요?", "a": "그렇다고 말할 수 없습니다. 층이 셋으로 늘고 BatchNorm2d·ReLU와 중간 결과를 읽고 쓰는 시간이 더해집니다. 장치마다 계산을 나눠 처리하는 방식도 달라서 시간은 직접 재야 합니다."}
```


### fc 입력 4096에서 입력 크기 거꾸로 구하기
<!-- facts: FA05-e4 FA05-e5 -->

2단계에서 Inception 모듈은 높이·너비를 지켰습니다. 아래 GoogLeNet 코드의 stem도 `padding=1`인 3×3 합성곱이라 크기를 지키므로, 높이·너비를 바꾸는 층은 풀링 층뿐입니다.

```python
class GoogLeNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, 192, kernel_size=3, padding=1),
            nn.BatchNorm2d(192), nn.ReLU(True))
        # im1 출력 채널 256
        self.im1 = InceptionModule(192, 64, 96, 128, 16, 32, 32)
        # im2 출력 채널 480
        self.im2 = InceptionModule(256, 128, 128, 192, 32, 96, 64)
        self.max_pool = nn.MaxPool2d(3, stride=2, padding=1)
        # im3 출력 채널 512
        self.im3 = InceptionModule(480, 192, 96, 208, 16, 48, 64)
        # im4 출력 채널 512
        self.im4 = InceptionModule(512, 160, 112, 224, 24, 64, 64)
        # im5 출력 채널 512
        self.im5 = InceptionModule(512, 128, 128, 256, 24, 64, 64)
        # im6 출력 채널 528
        self.im6 = InceptionModule(512, 112, 144, 288, 32, 64, 64)
        # im7 출력 채널 832
        self.im7 = InceptionModule(528, 256, 160, 320, 32, 128, 128)
        # im8 출력 채널 832
        self.im8 = InceptionModule(832, 256, 160, 320, 32, 128, 128)
        # im9 출력 채널 1024
        self.im9 = InceptionModule(832, 384, 192, 384, 48, 128, 128)
        self.average_pool = nn.AvgPool2d(7, stride=1)
        self.fc = nn.Linear(4096, 1000)

    def forward(self, ip):
        op = self.im2(self.im1(self.stem(ip)))
        op = self.max_pool(op)
        op = self.im5(self.im4(self.im3(op)))
        op = self.im7(self.im6(op))
        op = self.max_pool(op)
        op = self.im9(self.im8(op))
        op = self.average_pool(op)
        op = op.view(op.size(0), -1)
        return self.fc(op)
```

forward는 `__init__`에서 만든 stem, im1~im9, max_pool, average_pool, fc를 같은 이름으로 부릅니다. forward의 `op = self.max_pool(op)` 두 줄은 max_pool 객체 하나를 두 번 부릅니다. MaxPool2d에는 weight도 없고, 학습 중 모아 두는 평균·분산 같은 기록도 없습니다. 그래서 한 객체를 두 번 불러도 됩니다.

max_pool은 `MaxPool2d(3, stride=2, padding=1)`이라 한 변 s를 floor((s + 2 − 3) ÷ 2) + 1로 바꿉니다. average_pool은 `AvgPool2d(7, stride=1)`이라 한 변 s를 s − 7 + 1 = s − 6으로 바꿉니다. 마지막 `op.view(op.size(0), -1)`은 개론 11차시 다섯째 단원에서 본 것처럼 배치 축만 남기고 펼칩니다.

fc는 `nn.Linear(4096, 1000)`이라 펼친 길이가 4096이어야 합니다. im9의 출력이 1024 채널이므로 1024 × s × s = 4096에서 평균 풀링 뒤 한 변 s는 2입니다. 거꾸로 따라가면 평균 풀링 앞은 2 + 6 = 8입니다. max_pool을 지나 8이 되는 한 변은 15와 16이고, 다시 max_pool을 지나 15나 16이 되는 입력은 29, 30, 31, 32입니다. floor가 소수 부분을 버리므로 거꾸로 구한 크기가 하나로 정해지지 않습니다. 개론 11차시 여섯째 단원에서 다룬 CIFAR-10 이미지와 같은 32×32를 넣으면 32 → 16 → 8 → 2로 줄고 1024 × 2 × 2 = 4096입니다.

224×224 이미지를 넣으면 224 → 112 → 56 → 50이라 펼친 길이가 1024 × 50 × 50 = 2,560,000입니다. fc가 받는 4096과 달라 fc에서 모양 오류가 납니다. <u>fc의 입력 수 4096은 fc 앞 층의 노드 수가 아니라 마지막 특징 맵을 펼친 길이입니다.</u> GoogLeNet 원 논문은 7×7 특징 맵에 7×7 평균 풀링을 해서 한 변을 1로 만든 뒤 1024개 값을 선형층에 넣습니다. 평균 풀링 뒤에도 선형 분류기가 남는 구조는 개론 13차시 여섯째 단원 4단계에서 보았습니다.

```ai-code-help
{"title": "__init__에서 등록하고 forward에서 부르기", "explanation": "forward는 __init__에서 self.이름으로 등록한 층만 부를 수 있습니다. 등록하지 않은 이름을 부르면 모델을 만들 때가 아니라 입력을 넣어 forward를 실행할 때 오류가 납니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11g", "step": 2, "title": "층을 등록하는 때와 실행하는 때 나누기"}}
```

```ai-code-help
{"title": "풀링 층의 출력 길이", "explanation": "MaxPool2d(기본 dilation=1)와 AvgPool2d도 합성곱과 같은 식 floor((입력 + 2 × padding − 커널) ÷ stride) + 1로 출력 길이를 정합니다. 기본 ceil_mode=False에서는 소수 부분을 버립니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11b", "step": 3, "title": "바깥을 채운 길이에서 출력 크기 계산하기"}}
```

```figure
파일: assets/a5e-4.png
캡션: 그림 21. 한 변 32와 224를 넣었을 때 두 번의 max_pool과 average_pool을 지나는 한 변 길이입니다. 두 크기 가운데 32만 펼친 길이가 fc의 4096과 맞습니다.
내용: 위 띠는 32 → 16 → 8 → 2이고 1024 × 2 × 2 = 4096입니다. 아래 띠는 224 → 112 → 56 → 50이고 1024 × 50 × 50 = 2,560,000입니다.
```

```ai-reveal
{"guess": "g2"}
```

```ai-recall
{"id": "r4", "q": "한 변 40인 이미지를 넣으면 average_pool 뒤 한 변은 ____ 입니다.", "answer": ["4"], "mode": "number", "why": "40 → 20 → 10을 지나 10 − 6 = 4입니다."}
```

```ai-why
{"q": "224×224 이미지를 넣으면 forward의 어느 줄에서 처음 멈출까요?", "a": "224 입력이면 합성곱과 풀링은 모두 계산을 마칩니다. op.view 뒤 길이 2,560,000이 fc가 받는 4096과 달라 마지막 줄 self.fc(op)에서 모양 오류가 납니다."}
```


### 외울 것
<!-- facts: FA05-e1 FA05-e2 FA05-e3 FA05-e4 -->

```ai-memo
[{"q": "Inception 모듈의 출력 채널은 어떻게 구하나요?", "a": "block1부터 block4까지 네 갈래의 출력 채널을 더합니다. block2와 block3의 첫 층 출력은 더하지 않습니다. im4는 160 + 224 + 64 + 64 = 512입니다.", "cards": ["a05-b19"]}, {"q": "im4의 block3을 코드에 적힌 층으로 세면 위치 하나당 곱셈 수는 얼마인가요?", "a": "1×1 512→24, 3×3 24→64, 3×3 64→64를 더해 12,288 + 13,824 + 36,864 = 62,976번입니다. bias와 BatchNorm2d, ReLU는 세지 않습니다.", "cards": ["a05-b20"]}, {"q": "계산량 129배 비교에서 맞추지 않은 조건은 무엇인가요?", "a": "출력 채널입니다. 같은 출력 64 채널로 맞추면 5×5 한 층은 819,200번이고 1×1·3×3·3×3 구성의 약 13.0배입니다.", "cards": ["a05-c09"]}, {"q": "두 번의 MaxPool2d(3, stride=2, padding=1)와 AvgPool2d(7, stride=1)를 지나면 한 변 32와 224는 몇이 되나요?", "a": "32 → 16 → 8 → 2, 224 → 112 → 56 → 50입니다. 둘 가운데 32만 1024 × 2 × 2 = 4096이 되어 fc 입력과 맞습니다.", "cards": ["a05-b22"]}]
```

