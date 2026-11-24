# 응용 7차시 노이즈에서 이미지를 만드는 GAN과 VAE


## 판별기와 생성기의 손실을 정답 레이블로 나누기


### 먼저 풀어 보기
<!-- facts: FA07-a4 FA07-a6 -->

```ai-guess
{"id": "g1", "q": "생성기는 노이즈를 받아 가짜 사진을 만들고, 판별기는 사진을 받아 진짜일 확률을 냅니다. 생성기를 갱신할 때 판별기가 가짜 사진에 낸 값과 비교하는 정답 레이블은 무엇일까요?", "options": ["1(진짜)", "0(가짜)"], "answer": 0, "reveal_step": 4, "cards": ["a07-b03"]}
```

```ai-guess
{"id": "g2", "q": "학습을 오래 하자 판별기가 진짜 사진과 가짜 사진에 모두 0.5를 냅니다. 이 상태를 바르게 설명한 것은 무엇일까요?", "options": ["판별기가 진짜와 가짜를 가려내지 못할 만큼 생성기가 진짜 같은 사진을 만듭니다.", "판별기 학습이 망가져서 생성기도 더 배울 것이 없습니다."], "answer": 0, "reveal_step": 5, "cards": ["a07-c01"]}
```


### 풀 문제: 노이즈 100개로 손글씨 숫자 사진 만들기
<!-- facts: FA07-a1 FA07-a2 -->

이번 차시에서 풀 문제는 학습 데이터에 없는 새 손글씨 숫자 사진을 만드는 일입니다. 학습 데이터는 MNIST 손글씨 숫자 사진 60,000장입니다. 사진 한 장은 가로 28픽셀, 세로 28픽셀이라 픽셀이 784개입니다.

사진을 만드는 신경망을 생성기(generator)라고 부릅니다. 생성기는 정규분포에서 뽑은 숫자 100개를 받아 픽셀 784개를 냅니다. 생성기가 받는 무작위 숫자 묶음을 노이즈라고 부릅니다. 노이즈를 바꿔 넣으면 다른 사진이 나옵니다.

생성기를 학습시키려면 만든 사진이 진짜 같은지 알려 주는 신경망이 하나 더 있어야 합니다. 이 신경망을 판별기(discriminator)라고 부릅니다. 판별기는 사진 한 장을 받아 그 사진이 진짜일 확률을 0과 1 사이의 수로 냅니다. 생성기와 판별기를 번갈아 학습시키는 방법을 GAN(Generative Adversarial Network)이라고 부릅니다.

```python
generator = nn.Sequential(
    nn.Linear(100, 256), nn.LeakyReLU(0.2),
    nn.Linear(256, 512), nn.LeakyReLU(0.2),
    nn.Linear(512, 784), nn.Tanh())

discriminator = nn.Sequential(
    nn.Linear(784, 512), nn.LeakyReLU(0.2), nn.Dropout(0.3),
    nn.Linear(512, 256), nn.LeakyReLU(0.2), nn.Dropout(0.3),
    nn.Linear(256, 1), nn.Sigmoid())
```

`nn.LeakyReLU(0.2)`는 음수 입력에 0.2를 곱해 내보냅니다. 생성기 끝의 `nn.Tanh()`는 출력을 −1과 1 사이로 만듭니다. 판별기 끝의 `nn.Sigmoid()`는 출력을 0과 1 사이로 만들어 확률로 읽게 합니다. 생성기의 파라미터는 559,632개이고 판별기의 파라미터는 533,505개입니다.

진짜 사진의 픽셀도 생성기 출력과 같은 범위로 맞춥니다. `transforms.ToTensor()`는 픽셀 값을 0과 1 사이로 바꿉니다. 이어서 `transforms.Normalize([0.5], [0.5])`가 (x − 0.5) ÷ 0.5를 계산합니다. 그래서 0은 −1이 되고, 0.5는 0이 되고, 1은 1이 됩니다.

응용 6차시의 스타일 전이는 이미지 한 장의 픽셀을 여러 번 갱신해 결과를 얻었습니다. GAN은 생성기의 가중치를 학습해 둡니다. 학습을 마친 뒤에는 노이즈를 넣을 때마다 새 사진이 바로 나옵니다.

```figure
파일: assets/a7a-1.gif
캡션: 그림 1. 노이즈가 생성기를 지나 가짜 사진이 되고, 판별기는 진짜 사진과 가짜 사진을 받아 확률을 냅니다.
내용: 왼쪽에 노이즈 100칸, 가운데에 생성기 상자와 가짜 사진 칸, 위쪽에 진짜 사진 칸이 있습니다. 두 사진 칸에서 판별기 상자로 화살표가 가고 판별기 오른쪽에 0과 1 사이의 확률 칸이 있습니다.
프레임:
1. 숫자 100개로 된 노이즈가 생성기를 지나 픽셀 784개의 가짜 사진이 됩니다. (2200ms)
2. 진짜 사진은 Normalize를 지나 −1과 1 사이 값이 됩니다. (2200ms)
3. 판별기가 진짜 사진에 0.8, 가짜 사진에 0.3을 냅니다. (2200ms)
4. 진짜 사진 쪽에는 정답 1, 가짜 사진 쪽에는 정답 0 이름표가 붙습니다. (2400ms)
```
```ai-recall
{"id": "r1", "q": "`transforms.Normalize([0.5], [0.5])`가 픽셀 값 0.25를 바꾼 값은 ____ 입니다.", "answer": ["-0.5", "−0.5"], "mode": "number"}
```


### 판별기 손실: 진짜에는 정답 1, 가짜에는 정답 0
<!-- facts: FA07-a3 -->

2단계의 판별기가 진짜 사진 한 장에 0.8, 생성기가 만든 가짜 사진 한 장에 0.3을 냈다고 해 봅니다. 판별기는 진짜 사진에 1을, 가짜 사진에 0을 내야 맞습니다. 그래서 진짜 사진의 정답 레이블은 1이고 가짜 사진의 정답 레이블은 0입니다.

판별기의 출력은 확률이라 손실로 이진 교차 엔트로피(BCE)를 씁니다. 판별기가 낸 값을 p라고 하면, 정답이 1일 때 BCE는 −ln p이고 정답이 0일 때 BCE는 −ln(1 − p)입니다.

- 진짜 사진의 손실은 −ln 0.8입니다. 이 값은 0.2231입니다.
- 가짜 사진의 손실은 −ln(1 − 0.3)입니다. 이 값은 −ln 0.7 = 0.3567입니다.

판별기 손실은 두 값을 더한 0.5798입니다.

```ai-code-help
{"title": "BCE", "explanation": "정답이 1이면 −ln p, 정답이 0이면 −ln(1 − p)를 손실로 씁니다. p가 정답에서 멀수록 손실이 커집니다.", "reference": {"course": "intro", "lesson": "l06", "unit": "6c", "step": 2, "title": "BCE는 정답이 1이면 −log p, 0이면 −log(1 − p)"}}
```

```python
criterion = nn.BCELoss()
real_labels = torch.ones(current_batch_size, 1)
fake_labels = torch.zeros(current_batch_size, 1)

outputs_real = discriminator(real_images)
loss_D_real = criterion(outputs_real, real_labels)
outputs_fake = discriminator(fake_images.detach())
loss_D_fake = criterion(outputs_fake, fake_labels)
loss_D = loss_D_real + loss_D_fake
```

`torch.ones(current_batch_size, 1)`은 1만 담은 (배치 크기, 1) 텐서를 만듭니다. `torch.zeros(current_batch_size, 1)`은 0만 담은 같은 모양의 텐서를 만듭니다. 두 텐서의 모양은 판별기 출력의 모양 (배치 크기, 1)과 같습니다. `fake_images.detach()`의 detach()는 둘째 단원에서 봅니다.

`nn.BCELoss()`는 reduction 기본값이 'mean'이라 배치에 든 사진마다 BCE를 구한 뒤 평균을 냅니다. loss_D는 진짜 쪽 평균과 가짜 쪽 평균을 더한 값입니다. 판별기 손실을 두 값의 평균으로 계산하는 코드도 있습니다. 이 단계의 두 사진으로 평균을 계산하면 0.5798 ÷ 2 = 0.2899입니다.

```figure
파일: assets/a7a-2.png
캡션: 그림 2. 정답이 1일 때의 −ln p 곡선과 정답이 0일 때의 −ln(1 − p) 곡선입니다. 판별기가 낸 0.8과 0.3에 점을 찍었습니다.
내용: 가로축은 판별기 출력 p(0~1), 세로축은 BCE입니다. 파란 곡선 −ln p 위의 점 (0.8, 0.2231)과 주황 곡선 −ln(1 − p) 위의 점 (0.3, 0.3567)이 있습니다. 오른쪽 위에 0.2231 + 0.3567 = 0.5798이 적혀 있습니다.
```
```ai-recall
{"id": "r2", "q": "판별기가 진짜 사진에 0.9, 가짜 사진에 0.2를 냈습니다. 두 손실을 더한 판별기 손실은 소수 넷째 자리까지 ____ 입니다.", "answer": ["0.3285"], "mode": "number", "places": 4}
```
```ai-why
{"q": "판별기가 손실을 줄이려면 가짜 사진에 내는 값을 0.3에서 어느 쪽으로 바꿔야 할까요?", "a": "가짜 사진의 손실 −ln(1 − p)는 p가 0에 가까울수록 작아집니다. p를 0.3에서 0.1로 낮추면 가짜 사진의 손실은 0.3567에서 −ln 0.9 = 0.1054로 줄어듭니다."}
```

```ai-levels
{"id": "v1", "concept": "판별기 손실", "levels": [{"level": 7, "text": "판별기는 사진마다 0과 1 사이의 수를 하나 냅니다. 진짜 사진에는 1에 가까운 수를, 생성기가 만든 가짜 사진에는 0에 가까운 수를 내야 맞힌 것입니다. 진짜 사진 한 장에 0.8을 냈다면 1까지 0.2가 모자랍니다. 가짜 사진 한 장에 0.3을 냈다면 0보다 0.3만큼 큽니다. 모자란 수나 넘친 수가 클수록 판별기가 더 크게 틀린 것입니다.", "figure": {"file": "assets/a7a-31.png", "caption": "진짜 사진 칸의 0.8이 1에서, 가짜 사진 칸의 0.3이 0에서 떨어진 거리입니다.", "content": "위 줄은 0부터 1까지 그은 막대에 진짜 사진 표시와 0.8 점이 있고, 0.8에서 1까지 0.2라고 적은 괄호가 있습니다. 아래 줄은 같은 막대에 가짜 사진 표시와 0.3 점이 있고, 0에서 0.3까지 0.3이라고 적은 괄호가 있습니다."}, "q": "판별기가 진짜 사진에 0.65를 냈다면 1까지 모자란 수는 ____ 입니다.", "answer": ["0.35"], "mode": "number", "why": "1에서 0.65를 빼면 0.35가 남습니다."}, {"level": 15, "text": "판별기가 낸 수를 p라고 하면 진짜 사진의 손실은 −ln p이고, 가짜 사진의 손실은 −ln(1 − p)입니다. 진짜 사진에 0.8을 냈으면 −ln 0.8 = 0.2231입니다. 가짜 사진에 0.3을 냈으면 −ln(1 − 0.3) = −ln 0.7 = 0.3567입니다. 두 수를 더한 0.2231 + 0.3567 = 0.5798이 판별기 손실입니다.", "figure": {"file": "assets/a7a-32.png", "caption": "진짜 사진과 가짜 사진의 출력, 정답, 쓰는 식, 손실을 적은 표입니다.", "content": "두 행 표입니다. 열은 사진, 출력 p, 정답, 식, 손실입니다. 첫 행은 진짜, 0.8, 1, −ln p, 0.2231이고 둘째 행은 가짜, 0.3, 0, −ln(1 − p), 0.3567입니다. 아래에 합 0.5798이 있습니다."}, "q": "판별기가 가짜 사진에 0.4를 냈다면 가짜 사진의 손실은 소수 넷째 자리까지 ____ 입니다.", "answer": ["0.5108"], "mode": "number", "places": 4, "why": "−ln(1 − 0.4) = −ln 0.6 = 0.5108입니다."}, {"level": 20, "text": "`nn.BCELoss()`는 reduction 기본값이 'mean'이라 데이터마다 구한 BCE의 평균을 돌려줍니다. 진짜 출력 0.8과 가짜 출력 0.3을 한 텐서에 넣으면 두 BCE 0.2231과 0.3567의 평균이 나옵니다. reduction='sum'을 주면 두 BCE를 더한 값이 나옵니다.", "code": "criterion = nn.BCELoss()\nout = torch.tensor([[0.8], [0.3]])\ny = torch.tensor([[1.], [0.]])\ncriterion(out, y)                      # tensor(0.2899)\nnn.BCELoss(reduction='sum')(out, y)    # tensor(0.5798)", "mistake": "진짜 출력과 가짜 출력을 한 텐서에 넣어 계산하면 loss_D_real + loss_D_fake와 같은 값이 나온다고 보는 착각입니다. 진짜와 가짜가 같은 수만큼 든 한 텐서를 넣으면 합의 절반인 평균이 나옵니다. 합을 얻으려면 두 손실을 따로 구해 더하거나 reduction='sum'을 줍니다.", "figure": {"file": "assets/a7a-33.png", "caption": "진짜 출력과 가짜 출력을 따로 넣어 더할 때와 한 텐서에 넣을 때 BCELoss가 돌려주는 값입니다.", "content": "위 줄은 0.8 칸과 0.3 칸이 각각 BCELoss 상자를 지나 0.2231과 0.3567이 되고 더하기 기호 뒤에 0.5798이 있습니다. 아래 줄은 [[0.8], [0.3]] 텐서 하나가 BCELoss 상자를 지나 0.2899가 됩니다."}, "q": "위 코드에서 out을 [[0.6], [0.1]]로 바꾸면 criterion(out, y)는 소수 넷째 자리까지 ____ 입니다.", "answer": ["0.3081"], "mode": "number", "places": 4, "why": "진짜 쪽 −ln 0.6과 가짜 쪽 −ln(1 − 0.1)의 평균입니다. 계산하면 0.3081입니다."}]}
```


### 생성기 손실: 가짜 사진에 정답 1 붙이기
<!-- facts: FA07-a4 FA07-a5 -->

3단계에서 판별기는 가짜 사진에 0.3을 냈습니다. 생성기는 판별기가 이 가짜 사진에 1에 가까운 값을 내게 만들어야 합니다. 그래서 생성기 손실은 가짜 사진에 대한 판별기 출력을 정답 1과 비교합니다.

```python
noise = torch.randn(current_batch_size, 100)
fake_images = generator(noise)
outputs = discriminator(fake_images)
loss_G = criterion(outputs, real_labels)
```

`real_labels`는 3단계에서 진짜 사진에 붙인, 1만 담은 텐서입니다. 판별기 출력 0.3을 정답 1과 비교하면 생성기 손실은 −ln 0.3입니다. 이 값은 1.2040입니다. 판별기가 가짜 사진에 내는 값이 1에 가까워질수록 생성기 손실은 0에 가까워집니다.

GAN을 처음 낸 Goodfellow 등의 2014년 논문은 생성기가 ln(1 − D(G(z)))를 줄이도록 문제를 적었습니다. G(z)는 생성기가 노이즈 z로 만든 가짜 사진이고, D(G(z))는 판별기가 그 사진에 낸 값입니다. 같은 논문은 학습 초반에는 이 식 대신 ln D(G(z))를 키우라고 권합니다. 위 코드처럼 −ln D(G(z))를 줄이면 ln D(G(z))가 커집니다.

학습 초반에는 판별기가 가짜 사진을 쉽게 가려내서 D(G(z))가 0 가까이 나옵니다. 아래에서는 D(G(z))를 D로 줄여 적습니다. D가 0.01일 때, 논문이 처음 적은 식 ln(1 − D)와 위 코드의 생성기 손실 −ln D를 D로 미분한 값의 크기를 비교해 봅니다.

- ln(1 − D)의 미분값 크기는 1 ÷ 0.99입니다. 이 값은 1.0101입니다.
- −ln D의 미분값 크기는 1 ÷ 0.01입니다. 이 값은 100입니다.

−ln D를 쓰면 미분값이 훨씬 커서, 생성기가 아직 진짜 같은 사진을 만들지 못하는 학습 초반에도 생성기 쪽으로 큰 기울기가 전달됩니다.

```figure
파일: assets/a7a-3.png
캡션: 그림 3. 판별기 출력 D가 0 근처일 때 ln(1 − D) 곡선은 거의 평평하고 −ln D 곡선은 가파릅니다.
내용: 가로축은 D(0~1), 세로축은 손실입니다. 회색 곡선 ln(1 − D)와 파란 곡선 −ln D가 있습니다. D = 0.01 자리에 세로 점선이 있고, 회색 곡선의 접선 옆에 1.0101, 파란 곡선의 접선 옆에 100이 적혀 있습니다.
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r3", "q": "판별기가 가짜 사진에 0.1을 냈습니다. 생성기 손실은 소수 넷째 자리까지 ____ 입니다.", "answer": ["2.3026"], "mode": "number", "places": 4}
```
```ai-why
{"q": "생성기 손실을 계산할 때 real_labels 대신 fake_labels를 쓰면 어떻게 될까요?", "a": "생성기는 판별기가 가짜 사진에 0을 내는 쪽으로 갱신됩니다. 그러면 생성기는 판별기가 쉽게 가려내는 사진을 만드는 쪽으로 바뀝니다."}
```


### 판별기가 모든 사진에 0.5를 내는 균형
<!-- facts: FA07-a6 -->

4단계의 생성기 손실은 판별기가 가짜 사진에 내는 값이 1에 가까울수록 작아집니다. 3단계의 판별기 손실은 그 값이 0에 가까울수록 작아집니다. 두 신경망이 같은 값을 서로 반대쪽으로 끌어당기므로 두 손실이 함께 0이 되지 않습니다.

Goodfellow 등의 논문은 생성기가 만드는 사진의 분포가 진짜 사진의 분포와 같아지면, 가장 좋은 판별기가 모든 사진에 1/2을 낸다는 것을 보였습니다. 판별기가 모든 사진에 0.5를 내면 두 손실은 다음 값이 됩니다.

- 생성기 손실은 −ln 0.5 = ln 2입니다. 이 값은 0.6931입니다.
- 판별기 손실은 진짜 쪽 −ln 0.5와 가짜 쪽 −ln(1 − 0.5)를 더한 2 ln 2입니다. 이 값은 1.3863입니다.

넷째 단원 5단계에서는 합성곱 층을 쓰는 GAN인 DCGAN을 학습합니다. 이 학습 코드는 판별기 손실을 진짜 쪽과 가짜 쪽의 평균으로 계산합니다. 이 학습을 한 번 돌린 기록의 첫 줄에서 생성기 손실은 0.6957, 판별기 손실은 0.6942였습니다. 학습 전의 판별기는 사진을 가려내지 못해 0.5 근처를 내므로, 두 손실이 ln 2 = 0.6931 근처에서 시작합니다.

```figure
파일: assets/a7a-4.png
캡션: 그림 4. 판별기가 진짜 사진과 가짜 사진에 같은 값 p를 낼 때의 두 손실입니다. p = 0.5에서 판별기 손실 합은 1.3863, 생성기 손실은 0.6931입니다.
내용: 가로축은 판별기 출력 p(0~1), 세로축은 손실입니다. 보라 곡선은 판별기 손실 합 −ln p − ln(1 − p)이고 p = 0.5에서 가장 낮은 1.3863입니다. 파란 곡선은 생성기 손실 −ln p이고 p = 0.5에서 0.6931입니다. p = 0.5에 세로 점선이 있습니다.
```
```ai-reveal
{"guess": "g2"}
```
```ai-recall
{"id": "r4", "q": "판별기 손실을 진짜 쪽과 가짜 쪽의 평균으로 계산하는 코드에서 판별기가 모든 사진에 0.5를 내면, 판별기 손실은 소수 넷째 자리까지 ____ 입니다.", "answer": ["0.6931"], "mode": "number", "places": 4}
```


### 외울 것
<!-- facts: FA07-a3 FA07-a4 FA07-a5 FA07-a6 -->

```ai-memo
[{"q": "판별기 손실에서 진짜 사진과 가짜 사진의 정답 레이블은 무엇인가요?", "a": "진짜 사진은 1, 가짜 사진은 0입니다. 진짜 출력 0.8, 가짜 출력 0.3이면 −ln 0.8 + (−ln 0.7) = 0.2231 + 0.3567 = 0.5798입니다.", "cards": ["a07-b01", "a07-b04"]}, {"q": "생성기 손실은 판별기 출력을 어떤 정답과 비교하나요?", "a": "가짜 사진에 대한 판별기 출력을 정답 1(real_labels)과 비교합니다. 판별기가 0.3을 내면 생성기 손실은 −ln 0.3 = 1.2040입니다.", "cards": ["a07-b02", "a07-b03"]}, {"q": "원 논문이 ln(1 − D(G(z)))를 줄이는 대신 ln D(G(z))를 키우라고 한 까닭은 무엇인가요?", "a": "학습 초반에 ln(1 − D(G(z)))를 줄이면 생성기 쪽으로 전달되는 기울기가 작기 때문입니다. 이 시기에는 판별기가 가짜 사진을 쉽게 가려내서 D(G(z))가 0 가까이 나옵니다. D(G(z))를 D로 줄여 적습니다. D가 0.01일 때 D로 미분한 값의 크기는 ln(1 − D)가 1.0101이고 −ln D가 100입니다.", "cards": ["a07-c02"]}, {"q": "판별기가 모든 사진에 0.5를 내면 두 손실은 얼마인가요?", "a": "생성기 손실은 ln 2 = 0.6931, 판별기 손실 합은 2 ln 2 = 1.3863입니다. 두 손실이 함께 0이 되지 않습니다.", "cards": ["a07-c01"]}]
```


## detach와 옵티마이저 둘로 한쪽 신경망만 갱신하기


### 먼저 풀어 보기
<!-- facts: FA07-b1 -->

```ai-guess
{"id": "g1", "q": "판별기 단계에서 생성기가 만든 가짜 사진을 detach() 없이 판별기에 넣고, 판별기 손실에 backward()를 부릅니다. 생성기 첫 층의 grad는 어떻게 될까요?", "options": ["값이 채워집니다.", "None으로 남습니다."], "answer": 0, "reveal_step": 2, "cards": ["a07-c03"]}
```


### 판별기 단계에서 detach()로 생성기 쪽 기울기 끊기
<!-- facts: FA07-b1 -->

첫 단원 3단계의 판별기 손실 코드는 가짜 사진을 `fake_images.detach()`로 판별기에 넣었습니다. `fake_images`는 생성기가 노이즈로 계산한 텐서라서 계산 기록이 생성기의 층까지 이어져 있습니다. `detach()`는 값은 같고 계산 기록에서 떼어 낸 새 텐서를 돌려줍니다.

```python
noise = torch.randn(current_batch_size, 100)
fake_images = generator(noise)
outputs_fake = discriminator(fake_images.detach())
loss_D_fake = criterion(outputs_fake, fake_labels)
loss_D = loss_D_real + loss_D_fake

optimizer_D.zero_grad()
loss_D.backward()          # 기울기는 판별기 층까지만 계산됨
optimizer_D.step()
```

detach()한 텐서로 계산한 loss_D에 backward()를 부르면 기울기는 판별기의 층까지만 계산됩니다. 생성기 첫 층의 grad는 None으로 남습니다. 판별기 단계에서는 생성기의 가중치를 바꾸지 않으므로 생성기 쪽 기울기를 계산하지 않아도 됩니다.

detach()를 빼면 backward()가 판별기를 지나 생성기의 층까지 기울기를 계산해 생성기의 grad를 채웁니다. 이 기울기는 판별기 손실을 줄이는 쪽의 기울기라서 생성기를 갱신하는 데 쓸 값이 아닙니다.

```figure
파일: assets/a7b-1.gif
캡션: 그림 5. 판별기 단계에서 detach()가 있으면 기울기가 판별기 층에서 멈추고, 없으면 생성기 층까지 갑니다.
내용: 왼쪽부터 노이즈, 생성기 층, fake_images, 판별기 층, loss_D 상자가 한 줄로 있습니다. 층마다 아래에 grad 이름표가 있습니다.
프레임:
1. 노이즈가 생성기를 지나 fake_images가 되고, fake_images.detach()가 판별기로 들어가 loss_D가 나옵니다. (2200ms)
2. loss_D.backward()의 화살표가 판별기 층까지 가고 판별기 grad 이름표가 채워집니다. 생성기 층의 grad 이름표는 None입니다. (2400ms)
3. detach()를 뺀 줄에서는 화살표가 생성기 층까지 가고 생성기 grad 이름표도 채워집니다. (2400ms)
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r1", "q": "detach()한 가짜 사진으로 계산한 판별기 손실에 backward()를 부르면 생성기 첫 층의 grad는 ____ 입니다.", "answer": ["None"], "mode": "code"}
```


### 생성기 단계의 backward()가 채운 판별기 grad 지우기
<!-- facts: FA07-b2 FA07-b4 -->

2단계에서 판별기를 갱신한 뒤 생성기 단계로 넘어갑니다. 생성기 단계는 첫 단원 4단계처럼 새 노이즈로 가짜 사진을 다시 만들고, 이 사진을 detach() 없이 판별기에 넣습니다.

```python
noise = torch.randn(current_batch_size, 100)
fake_images = generator(noise)
loss_G = criterion(discriminator(fake_images), real_labels)

optimizer_G.zero_grad()
loss_G.backward()          # 생성기와 판별기의 grad 가 모두 채워짐
optimizer_G.step()
```

loss_G의 기울기는 판별기를 지나 생성기에 닿습니다. 그래서 `loss_G.backward()`는 생성기의 grad와 함께 판별기의 grad도 채웁니다. optimizer_G는 만들 때 `generator.parameters()`만 받았습니다. 그래서 `optimizer_G.step()`은 생성기의 가중치만 바꾸고 판별기의 가중치는 바꾸지 않습니다.

판별기에 남은 grad는 다음 배치의 판별기 단계에서 지웁니다. 2단계 코드에서 `loss_D.backward()` 앞에 있는 `optimizer_D.zero_grad()`가 판별기의 grad를 None으로 만듭니다. zero_grad()의 set_to_none 기본값이 True이기 때문입니다.

생성기를 먼저 갱신하고 판별기를 나중에 갱신하는 코드도 있습니다. 넷째 단원 5단계에서 볼 DCGAN 학습 코드가 이 순서입니다. 옵티마이저마다 자기 신경망의 파라미터만 받았으므로 두 순서 모두 다른 신경망의 가중치를 바꾸지 않습니다.

```ai-code-help
{"title": "zero_grad()", "explanation": "zero_grad()는 옵티마이저가 받은 파라미터의 grad를 지웁니다. set_to_none 기본값이 True라서 grad가 None이 됩니다.", "reference": {"course": "intro", "lesson": "l04", "unit": "4c", "step": 6, "title": "코드 읽기: zero_grad의 자리와 None"}}
```

```figure
파일: assets/a7b-2.png
캡션: 그림 6. 생성기 단계 뒤에는 두 신경망의 grad가 모두 채워지지만 가중치는 생성기만 바뀝니다. 다음 배치의 optimizer_D.zero_grad()가 판별기 grad를 None으로 지웁니다.
내용: 세 열 표입니다. 열은 시점, 생성기, 판별기이고 행은 loss_G.backward() 뒤, optimizer_G.step() 뒤, 다음 배치 optimizer_D.zero_grad() 뒤입니다. 판별기 열은 grad 채움, 가중치 그대로, grad None 순서로 적혀 있습니다.
```
```ai-recall
{"id": "r2", "q": "optimizer_G.step()이 가중치를 바꾸는 신경망은 ____ 입니다.", "answer": ["생성기", "generator", "G"], "mode": "word"}
```
```ai-why
{"q": "생성기 단계에서는 가짜 사진을 detach()하지 않는 까닭은 무엇일까요?", "a": "생성기 손실의 기울기가 판별기를 지나 생성기 층까지 와야 생성기의 grad가 채워집니다. detach()하면 생성기의 grad가 None으로 남아서 optimizer_G.step()이 생성기를 바꾸지 못합니다."}
```


### Adam의 betas를 (0.5, 0.999)로 낮추기
<!-- facts: FA07-b3 -->

2단계의 optimizer_D와 3단계의 optimizer_G는 같은 설정의 Adam입니다.

```python
optimizer_G = optim.Adam(generator.parameters(), lr=0.0002, betas=(0.5, 0.999))
optimizer_D = optim.Adam(discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999))
```

`optim.Adam`의 기본값은 lr 0.001, betas (0.9, 0.999)입니다. betas의 두 수는 Adam이 기울기의 평균과 기울기 제곱의 평균을 계산할 때 쓰는 계수입니다. 앞 수 β1은 기울기 평균에 쓰고, 뒤 수 β2는 기울기 제곱 평균에 씁니다.

DCGAN을 낸 Radford 등의 2015년 논문은 Adam의 권장 학습률 0.001이 너무 커서 0.0002를 썼다고 적었습니다. 같은 논문은 β1을 0.9로 두면 학습이 흔들려서 0.5로 낮췄다고 적었습니다. 위 코드의 lr=0.0002와 betas=(0.5, 0.999)가 이 값입니다. 넷째 단원 5단계에서 볼 DCGAN 학습 코드는 논문 값 대신 lr 0.001과 기본 betas를 씁니다.

```ai-code-help
{"title": "Adam", "explanation": "Adam은 기울기 평균으로 갱신 방향을 정하고, 기울기 제곱 평균으로 갱신 크기를 조절합니다.", "reference": {"course": "intro", "lesson": "l12", "unit": "12b", "step": 4, "title": "Adam에서 평균과 제곱 평균 함께 기록하기"}}
```

```figure
파일: assets/a7b-3.png
캡션: 그림 7. Adam 기본값, DCGAN 논문 값, 넷째 단원 DCGAN 학습 코드 값의 lr와 betas입니다.
내용: 세 행 표입니다. 열은 설정, lr, β1, β2이고 행은 Adam 기본값(0.001, 0.9, 0.999), DCGAN 논문(0.0002, 0.5, 0.999), 넷째 단원 학습 코드(0.001, 0.9, 0.999)입니다. 논문 행의 0.0002와 0.5 칸에 색이 칠해져 있습니다.
```
```ai-recall
{"id": "r3", "q": "`optim.Adam`의 betas 기본값에서 첫째 수 β1은 ____ 입니다.", "answer": ["0.9"], "mode": "number"}
```


### 마지막 배치 96장과 current_batch_size
<!-- facts: FA07-a7 FA07-b4 -->

2단계와 3단계의 코드는 배치마다 되풀이합니다. MNIST 학습 사진 60,000장을 batch_size=128로 나누면 배치는 469개입니다. 앞의 468개 배치에는 128장씩 들어갑니다. 마지막 배치에 남는 사진은 60,000 − 128 × 468 = 96장입니다.

그래서 레이블의 크기를 배치마다 그 배치의 사진 수로 정합니다.

```python
fixed_noise = torch.randn(16, 100)

for real_images, _ in train_loader:
    current_batch_size = real_images.size(0)
    real_images = real_images.view(current_batch_size, -1)
    real_labels = torch.ones(current_batch_size, 1)
    fake_labels = torch.zeros(current_batch_size, 1)
```

`real_images.size(0)`은 배치에 든 사진 수입니다. 마지막 배치에서 current_batch_size는 96입니다. `real_images.view(current_batch_size, -1)`은 (96, 1, 28, 28) 사진을 (96, 784)로 펴서 Linear 층에 넣을 수 있게 합니다. 레이블을 `torch.ones(128, 1)`로 고정하면 마지막 배치에서 판별기 출력 (96, 1)과 레이블 (128, 1)의 모양이 맞지 않습니다.

`fixed_noise`는 학습 전에 한 번만 만든 노이즈 16개입니다. 학습 중간에 이 노이즈를 생성기에 넣어 사진 16장을 그리고, 앞서 그린 사진과 비교합니다.

```figure
파일: assets/a7b-4.png
캡션: 그림 8. 60,000장을 128장씩 나눈 배치 469개입니다. 마지막 배치에는 96장이 들어갑니다.
내용: 가로로 배치 막대가 늘어서 있고 앞 막대마다 128, 마지막 막대에 96이 적혀 있습니다. 아래에 60,000 − 128 × 468 = 96이 있습니다. 오른쪽에 마지막 배치의 real_labels 모양 (96, 1)이 있습니다.
```
```ai-recall
{"id": "r4", "q": "같은 60,000장을 batch_size=64로 나누면 마지막 배치의 사진 수는 ____ 입니다.", "answer": ["32"], "mode": "number"}
```
```ai-why
{"q": "중간 결과를 그릴 때 새 노이즈 대신 학습 전에 만든 fixed_noise를 쓰는 까닭은 무엇일까요?", "a": "노이즈가 매번 같으므로 그린 사진이 달라진 까닭은 생성기의 가중치가 바뀐 것뿐입니다. 그래서 학습이 진행되며 생성기가 어떻게 바뀌었는지 비교할 수 있습니다."}
```


### 외울 것
<!-- facts: FA07-a7 FA07-b1 FA07-b2 FA07-b3 -->

```ai-memo
[{"q": "판별기 단계에서 가짜 사진에 detach()를 붙이는 까닭은 무엇인가요?", "a": "판별기 손실의 backward()가 판별기 층까지만 기울기를 계산하게 합니다. 생성기 첫 층의 grad는 None으로 남습니다.", "cards": ["a07-b07", "a07-c03"]}, {"q": "생성기 단계의 backward()가 판별기 grad도 채우는데 판별기 가중치가 바뀌지 않는 까닭은 무엇인가요?", "a": "optimizer_G는 generator.parameters()만 받아서 생성기 가중치만 바꿉니다. 판별기에 남은 grad는 다음 배치의 optimizer_D.zero_grad()가 None으로 지웁니다.", "cards": ["a07-b08"]}, {"q": "DCGAN 논문의 Adam 설정은 무엇인가요?", "a": "lr 0.0002, betas (0.5, 0.999)입니다. 기본값 lr 0.001, β1 0.9에서 둘 다 낮췄습니다.", "cards": ["a07-b06", "a07-c04"]}, {"q": "60,000장을 128장씩 나누면 마지막 배치는 몇 장인가요?", "a": "60,000 − 128 × 468 = 96장입니다. 그래서 레이블을 current_batch_size로 만듭니다.", "cards": ["a07-b05"]}]
```


## DCGAN 생성기에서 16×16을 64×64로 키우기


### 먼저 풀어 보기
<!-- facts: FA07-c1 -->

```ai-guess
{"id": "g1", "q": "숫자 64개로 된 노이즈를 `nn.Linear(64, 128 * 16 * 16)`에 넣습니다. 이 층이 노이즈 하나마다 내는 값은 몇 개일까요?", "options": ["32,768개", "2,048개", "4,096개"], "answer": 0, "reveal_step": 2, "cards": ["a07-b09"]}
```


### Linear 출력을 view로 (2, 128, 16, 16)에 맞추기
<!-- facts: FA07-c1 FA07-c6 -->

첫 단원의 생성기는 Linear 층만 써서 픽셀 784개를 한 줄로 냈습니다. DCGAN(Deep Convolutional GAN)은 생성기와 판별기에 합성곱 층을 쓰는 GAN입니다. 이 단원의 DCGAN 생성기는 숫자 64개로 된 노이즈 하나로 채널 1개, 가로세로 64픽셀인 사진 한 장을 만듭니다. 노이즈 2개가 든 배치 (2, 64)를 끝까지 따라갑니다.

```python
image_sz = 64
lat_dimension = 64
self.inp_sz = image_sz // 4
self.lin = nn.Linear(lat_dimension, 128 * self.inp_sz * self.inp_sz)
```

`self.inp_sz`는 64 // 4 = 16입니다. Linear 층은 노이즈마다 128 × 16 × 16 = 32,768개를 냅니다. 그래서 배치 (2, 64)를 넣으면 `self.lin`의 출력은 (2, 32768)입니다. 이 층의 파라미터는 64 × 32,768 + 32,768 = 2,129,920개입니다. 생성기 전체의 파라미터 2,352,513개 가운데 이 층 하나가 2,129,920개를 차지합니다.

```python
x = self.lin(x)
x = x.view(x.shape[0], 128, self.inp_sz, self.inp_sz)
```

`view`는 (2, 32768)을 (2, 128, 16, 16)으로 바꿉니다. 이 텐서는 채널 128개, 가로세로 16인 특징 맵 2장입니다. `x.shape[0]`은 배치 크기 2입니다. 배치 크기를 숫자로 적지 않았으므로 배치 크기가 바뀌어도 같은 줄을 씁니다.

```figure
파일: assets/a7c-1.gif
캡션: 그림 9. 노이즈 배치 (2, 64)가 DCGAN 생성기를 지나며 바뀌는 모양입니다.
내용: 왼쪽부터 (2, 64), (2, 32768), (2, 128, 16, 16), (2, 128, 32, 32), (2, 128, 64, 64), (2, 64, 64, 64), (2, 1, 64, 64) 상자가 화살표로 이어집니다. 화살표 위에 lin, view, up1·cn1, up2, cn2, cn3·Tanh가 적혀 있습니다.
프레임:
1. Linear 층이 노이즈 (2, 64)를 (2, 32768)로 바꿉니다. (2200ms)
2. view가 (2, 32768)을 채널 128개, 가로세로 16인 (2, 128, 16, 16)으로 바꿉니다. (2200ms)
3. Upsample과 합성곱을 두 번 지나 가로세로가 16에서 32, 64로 커집니다. (2400ms)
4. 마지막 합성곱이 채널을 64개에서 1개로 줄이고 Tanh가 값을 −1과 1 사이로 만듭니다. (2400ms)
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r1", "q": "`nn.Linear(100, 64 * 8 * 8)`이 입력 하나마다 내는 값은 ____ 개입니다.", "answer": ["4096"], "mode": "number"}
```


### Upsample로 16을 32, 64로 키우기
<!-- facts: FA07-c2 FA07-c6 FA07-a2 -->

2단계의 (2, 128, 16, 16)은 가로세로가 16입니다. 가로세로를 64까지 키우려고 Upsample과 합성곱을 두 번 지납니다.

```python
self.up1 = nn.Upsample(scale_factor=2)
self.cn1 = nn.Conv2d(128, 128, 3, stride=1, padding=1)
self.up2 = nn.Upsample(scale_factor=2)
self.cn2 = nn.Conv2d(128, 64, 3, stride=1, padding=1)
self.cn3 = nn.Conv2d(64, 1, 3, stride=1, padding=1)
self.act = nn.Tanh()
```

`nn.Upsample(scale_factor=2)`는 가로세로를 두 배로 키웁니다. mode 기본값이 'nearest'라서 새 칸마다 가장 가까운 원래 칸의 값을 복사합니다. 가로세로 2인 [[1, 2], [3, 4]]를 넣으면 가로세로 4인 결과가 나옵니다. 결과의 첫 두 줄은 1, 1, 2, 2이고 아래 두 줄은 3, 3, 4, 4입니다.

`nn.Conv2d(128, 128, 3, stride=1, padding=1)`은 커널 크기 3, stride 1, padding 1인 합성곱입니다. 이 층에는 up1을 지나 가로세로가 32가 된 텐서가 들어옵니다. 출력 크기는 (32 + 2 × 1 − 3) ÷ 1 + 1 = 32라서 가로세로가 바뀌지 않습니다. 배치 (2, 64)로 시작하면 모양이 다음 순서로 바뀝니다.

- up1: (2, 128, 32, 32)
- cn1: (2, 128, 32, 32)
- up2: (2, 128, 64, 64)
- cn2: (2, 64, 64, 64)
- cn3과 Tanh: (2, 1, 64, 64)

마지막 `nn.Tanh()`는 값을 −1과 1 사이로 만듭니다. 첫 단원에서 진짜 사진을 `transforms.Normalize([0.5], [0.5])`로 −1과 1 사이에 맞춘 것과 같은 범위입니다.

```ai-code-help
{"title": "합성곱 출력 크기", "explanation": "출력 크기는 (입력 크기 + 2 × padding − 커널 크기) ÷ stride + 1입니다. 커널 3, stride 1, padding 1이면 출력 크기가 입력 크기와 같습니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11b", "step": 3, "title": "바깥을 채운 길이에서 출력 크기 계산하기"}}
```

```figure
파일: assets/a7c-2.png
캡션: 그림 10. 가로세로 2인 숫자 격자를 nearest 방식으로 가로세로 4인 격자로 키운 결과입니다.
내용: 왼쪽 2×2 격자에 1, 2, 3, 4가 있습니다. 오른쪽 4×4 격자에서 왼쪽 위 네 칸은 1, 오른쪽 위 네 칸은 2, 왼쪽 아래 네 칸은 3, 오른쪽 아래 네 칸은 4이고 같은 값끼리 같은 색입니다.
```
```ai-recall
{"id": "r2", "q": "모양이 (2, 64, 8, 8)인 텐서를 `nn.Upsample(scale_factor=2)`에 넣으면 출력 모양은 ____ 입니다.", "answer": ["(2, 64, 16, 16)"], "mode": "shape"}
```
```ai-why
{"q": "Upsample 뒤에 3×3 합성곱을 두는 까닭은 무엇일까요?", "a": "Upsample은 값을 복사만 해서 키운 직후에는 같은 값이 네 칸씩 붙어 있습니다. 뒤의 합성곱은 이웃한 칸들을 커널 가중치로 곱해 더하므로, 복사된 칸들이 서로 다른 값이 될 수 있습니다."}
```

```ai-levels
{"id": "v1", "concept": "Upsample", "levels": [{"level": 7, "text": "가로 2칸, 세로 2칸인 격자에 1, 2, 3, 4가 적혀 있습니다. 이 격자를 가로 4칸, 세로 4칸인 격자로 키웁니다. 원래 칸 하나는 새 격자에서 칸 네 개가 되고, 네 칸 모두 원래 칸의 수를 똑같이 받습니다. 그래서 1은 왼쪽 위 네 칸에, 2는 오른쪽 위 네 칸에 들어갑니다.", "figure": {"file": "assets/a7c-31.png", "caption": "작은 격자의 칸 하나가 큰 격자의 네 칸으로 복사되는 모습입니다.", "content": "왼쪽 작은 격자에 1, 2, 3, 4가 있고 오른쪽 큰 격자에 같은 수가 네 칸씩 모여 있습니다. 1이 적힌 칸에서 큰 격자의 왼쪽 위 네 칸으로 화살표가 갑니다."}, "q": "가로 3칸, 세로 3칸인 격자도 칸 하나가 칸 네 개가 되도록 키웁니다. 키운 격자의 칸 수는 ____ 입니다.", "answer": ["36"], "mode": "number", "why": "가로 3칸, 세로 3칸인 격자에는 칸이 9개 있습니다. 칸 하나가 칸 네 개가 되므로 키운 격자의 칸은 9의 네 배인 36개입니다."}, {"level": 15, "text": "가로세로를 두 배로 키우면 칸 수는 가로로 두 배, 세로로 두 배가 됩니다. 이 단계의 특징 맵은 가로세로 16에서 시작합니다. 한 번 키우면 16 × 2 = 32이고, 한 번 더 키우면 32 × 2 = 64입니다. 칸 수는 16 × 16 = 256에서 64 × 64 = 4,096이 됩니다.", "figure": {"file": "assets/a7c-32.png", "caption": "가로세로가 16에서 32, 64로 커질 때의 한 변 길이와 칸 수 표입니다.", "content": "세 행 표입니다. 열은 단계, 한 변, 칸 수이고 행은 처음 16과 256, 한 번 키운 뒤 32와 1,024, 두 번 키운 뒤 64와 4,096입니다."}, "q": "한 변이 8인 격자를 두 번 키우면 한 변은 ____ 입니다.", "answer": ["32"], "mode": "number", "why": "8 × 2 = 16이고 16 × 2 = 32입니다."}, {"level": 20, "text": "`nn.Upsample(scale_factor=2)`는 mode 기본값이 'nearest'라서 출력의 (i, j) 칸에 입력의 (i // 2, j // 2) 칸 값을 넣습니다. 아래 코드는 이 단계의 [[1, 2], [3, 4]]를 키웁니다.", "code": "up = nn.Upsample(scale_factor=2)\nx = torch.tensor([[[[1., 2.], [3., 4.]]]])\ny = up(x)\nprint(y.shape)        # torch.Size([1, 1, 4, 4])\nprint(y[0, 0, 0])     # tensor([1., 1., 2., 2.])", "mistake": "Upsample이 채널 수도 두 배로 늘린다고 보는 착각입니다. scale_factor=2는 마지막 두 축인 가로세로만 키우고 배치 축과 채널 축은 바꾸지 않습니다.", "figure": {"file": "assets/a7c-33.png", "caption": "출력 칸의 위치를 2로 나눈 몫이 입력 칸의 위치가 되는 대응입니다.", "content": "왼쪽 4×4 출력 격자에 (2, 1) 칸이 강조되어 있고, 그 칸에서 오른쪽 2×2 입력 격자의 (1, 0) 칸으로 화살표가 갑니다. 화살표 위에 2 // 2 = 1, 1 // 2 = 0이 적혀 있습니다."}, "q": "위 입력에서 오른쪽 위 값만 2에서 5로 바꿉니다. 같은 방식으로 두 배 키우면 y[0, 0, 1, 3]은 ____ 입니다.", "answer": ["5", "5.0"], "mode": "number", "why": "출력의 (1, 3) 좌표를 2로 나눈 몫은 (0, 1)입니다. 입력의 오른쪽 위 값을 5로 바꿨으므로 그 칸에서 5를 가져옵니다."}]}
```


### BatchNorm2d(128, 0.8)의 0.8은 eps
<!-- facts: FA07-c3 -->

생성기에는 2단계의 lin과 3단계의 층 말고도 배치 정규화 층 셋과 Leaky ReLU 층 둘이 있습니다. bn1은 view 바로 뒤에 놓이고, 나머지 넷은 cn1 뒤와 cn2 뒤에 둘씩 놓입니다.

```python
self.bn1 = nn.BatchNorm2d(128)
self.bn2 = nn.BatchNorm2d(128, 0.8)
self.rl1 = nn.LeakyReLU(0.2, inplace=True)
self.bn3 = nn.BatchNorm2d(64, 0.8)
self.rl2 = nn.LeakyReLU(0.2, inplace=True)
```

forward는 lin, view, bn1, up1, cn1, bn2, rl1, up2, cn2, bn3, rl2, cn3, act 순서로 층을 지납니다. `nn.BatchNorm2d`의 위치 인자는 num_features, eps, momentum 순서입니다. 그래서 `nn.BatchNorm2d(128, 0.8)`에서 둘째 자리의 0.8은 eps입니다. momentum은 적지 않았으므로 기본값 0.1로 남습니다.

배치 정규화는 값에서 배치 평균을 빼고 √(분산 + eps)로 나눕니다. eps는 제곱근 안에서 분산에 더하는 수입니다. 분산이 0.04인 채널에서 평균보다 0.2 큰 값을 정규화해 봅니다.

- eps가 기본값 0.00001이면 0.2 ÷ √(0.04 + 0.00001)입니다. 이 값은 약 0.9999입니다.
- eps가 0.8이면 0.2 ÷ √(0.04 + 0.8)입니다. 이 값은 약 0.2182입니다.

0.8을 momentum으로 쓰려면 `nn.BatchNorm2d(128, momentum=0.8)`처럼 인자 이름을 붙여 넘깁니다.

```ai-code-help
{"title": "배치 정규화의 계산", "explanation": "배치 정규화는 배치 평균을 빼고, 분산에 작은 수 eps를 더한 값의 제곱근으로 나눕니다. 그다음 채널마다 학습하는 배율 γ를 곱하고 이동 값 β를 더합니다. 이 β는 Adam의 betas와 다른 값입니다.", "reference": {"course": "intro", "lesson": "l05", "unit": "5f", "step": 2, "title": "배치 정규화의 계산: 평균을 빼고 나눈 뒤 γ, β"}}
```

```figure
파일: assets/a7c-3.png
캡션: 그림 11. 분산 0.04인 채널에서 평균보다 0.2 큰 값을 eps 0.00001과 eps 0.8로 정규화한 결과입니다.
내용: 막대 두 개가 있습니다. 왼쪽 막대는 eps 0.00001, 높이 0.9999이고 오른쪽 막대는 eps 0.8, 높이 0.2182입니다. 위에 BatchNorm2d(128, 0.8)의 인자 자리 num_features = 128, eps = 0.8, momentum = 0.1이 적혀 있습니다.
```
```ai-recall
{"id": "r3", "q": "`nn.BatchNorm2d(64, 0.8)`의 momentum은 ____ 입니다.", "answer": ["0.1"], "mode": "number"}
```
```ai-why
{"q": "BatchNorm2d(128, 0.8)을 쓴 코드가 오류 없이 실행되는 까닭은 무엇일까요?", "a": "0.8은 eps 자리에 들어가는 실수라서 인자 꼴이 맞습니다. 오류는 나지 않고, 정규화할 때 분산에 0.8을 더하는 계산만 바뀝니다."}
```


### ConvTranspose2d로 4를 8로 키우기
<!-- facts: FA07-c4 FA07-c5 -->

3단계는 Upsample로 크기를 키운 뒤 합성곱으로 값을 계산했습니다. DCGAN 논문의 생성기는 전치 합성곱 하나로 크기를 키우면서 값을 계산합니다. 전치 합성곱은 입력 한 칸의 값에 커널 가중치를 곱해 출력의 여러 칸에 더합니다. 커널 크기가 4이면 출력 4 × 4 칸에 더합니다. 입력 칸이 한 칸 옆으로 옮겨 가면 출력에서 더하는 자리는 stride 칸 옆으로 옮겨 갑니다. 그래서 stride가 2이면 출력 가로세로가 입력의 약 두 배가 됩니다. PyTorch의 전치 합성곱 층은 `nn.ConvTranspose2d`이고, 공식 문서는 이 층을 fractionally-strided convolution이라고도 부릅니다.

```python
up = nn.ConvTranspose2d(512, 256, 4, 2, 1)
```

인자는 차례로 입력 채널 512, 출력 채널 256, 커널 크기 kernel_size 4, stride 2, padding 1입니다. 공식 문서의 출력 가로세로 식에는 dilation과 output_padding도 들어갑니다. dilation은 커널 칸 사이의 간격을 정하는 인자입니다. 기본값 1이면 커널 칸이 빈칸 없이 붙어 놓입니다. 2로 바꾸면 커널 칸 사이에 빈칸이 하나씩 생깁니다. output_padding은 출력의 한쪽 끝에 더할 크기를 정하는 인자입니다. 이 층은 두 인자를 적지 않아 기본값 1과 0을 씁니다. 두 인자가 기본값이면, 입력 가로세로를 H라고 할 때 출력 가로세로는 (H − 1) × stride − 2 × padding + kernel_size입니다. 가로세로 4인 입력을 넣으면 (4 − 1) × 2 − 2 × 1 + 4를 계산합니다. 출력 가로세로는 8입니다. 같은 층에 8을 넣으면 16이 나옵니다.

노이즈에서 시작하는 생성기를 전치 합성곱으로만 만든다면 첫 층으로 `nn.ConvTranspose2d(100, 512, 4, 1, 0)`을 둘 수 있습니다. 숫자 100개로 된 노이즈를 (배치, 100, 1, 1) 모양으로 바꾸면, 노이즈 하나가 채널 100개, 가로세로 1인 입력이 됩니다. 이 층은 stride 1, padding 0이라 가로세로 1인 입력을 (1 − 1) × 1 − 2 × 0 + 4 = 4로 키웁니다. 그래서 노이즈마다 채널 512개, 가로세로 4인 특징 맵이 나옵니다.

DCGAN 논문은 생성기와 판별기를 만드는 지침도 적었습니다.

- 풀링 층을 쓰지 않고, 판별기는 stride 합성곱으로 줄이고 생성기는 전치 합성곱으로 키웁니다.
- 생성기의 출력층과 판별기의 입력층에는 배치 정규화를 두지 않습니다.
- 생성기는 출력층에만 Tanh를 쓰고 나머지 층에는 ReLU를 씁니다. 판별기는 모든 층에 음수 입력에 0.2를 곱하는 Leaky ReLU를 씁니다.
- 모든 가중치를 평균 0, 표준편차 0.02인 정규분포로 초기화합니다.

이 단원의 생성기는 전치 합성곱 대신 Upsample을 쓰고, ReLU 대신 Leaky ReLU를 씁니다. 출력층에만 Tanh를 두고 출력층에 배치 정규화를 두지 않는 것은 논문 지침과 같습니다.

```figure
파일: assets/a7c-4.png
캡션: 그림 12. ConvTranspose2d(512, 256, 4, 2, 1)이 가로세로 4인 입력을 8로 키우는 계산입니다.
내용: 왼쪽에 4칸 줄, 오른쪽에 8칸 줄이 있고 가운데에 (4 − 1) × 2 − 2 × 1 + 4 = 8이 적혀 있습니다. 아래 줄에는 1칸이 ConvTranspose2d(100, 512, 4, 1, 0)을 지나 4칸이 되는 그림이 있습니다.
```
```ai-recall
{"id": "r4", "q": "`nn.ConvTranspose2d(256, 128, 4, 2, 1)`에 가로세로 16인 특징 맵을 넣으면 출력 가로세로는 ____ 입니다.", "answer": ["32"], "mode": "number"}
```


### 외울 것
<!-- facts: FA07-c1 FA07-c2 FA07-c3 FA07-c4 FA07-c6 -->

```ai-memo
[{"q": "DCGAN 생성기의 Linear 출력은 어떤 모양으로 바뀌나요?", "a": "image_sz 64면 inp_sz = 16이고 Linear는 128 × 16 × 16 = 32,768개를 냅니다. view(x.shape[0], 128, 16, 16)이 (2, 32768)을 (2, 128, 16, 16)으로 바꿉니다.", "cards": ["a07-b09", "a07-b11"]}, {"q": "16을 64로 키우는 층의 순서와 마지막 모양은 무엇인가요?", "a": "Upsample(scale_factor=2)와 3×3·padding 1 합성곱을 두 번 지나 16 → 32 → 64가 됩니다. 마지막 합성곱과 Tanh 뒤 모양은 (2, 1, 64, 64)이고 값은 −1과 1 사이입니다.", "cards": ["a07-b10", "a07-b12"]}, {"q": "BatchNorm2d(128, 0.8)의 0.8은 무엇인가요?", "a": "둘째 위치 인자라 eps입니다. momentum은 기본값 0.1입니다.", "cards": ["a07-c05"]}, {"q": "ConvTranspose2d(512, 256, 4, 2, 1)에 가로세로 4를 넣으면 출력은 얼마인가요?", "a": "(4 − 1) × 2 − 2 × 1 + 4 = 8입니다. ConvTranspose2d는 커널 가중치로 값을 계산하며 키우고, Upsample은 가장 가까운 칸의 값을 복사해 키웁니다.", "cards": ["a07-c06"]}]
```


## DCGAN 판별기에서 64를 4로 줄이고 2,048로 펴기


### 먼저 풀어 보기
<!-- facts: FA07-d1 -->

```ai-guess
{"id": "g1", "q": "파이썬에서 `64 // 2 ** 4`를 계산하면 얼마일까요?", "options": ["4", "1,048,576"], "answer": 0, "reveal_step": 3, "cards": ["a07-b15"]}
```


### stride 2 합성곱 블록 넷으로 64를 4로 줄이기
<!-- facts: FA07-d1 FA07-c5 -->

셋째 단원의 생성기가 만든 (2, 1, 64, 64) 사진은 판별기로 들어갑니다. 판별기는 합성곱 블록 넷으로 가로세로를 줄인 뒤 Linear 층에서 확률 하나를 냅니다. 블록 하나는 아래 함수가 만듭니다.

```python
def disc_module(ip_chnls, op_chnls, bnorm=True):
    mod = [nn.Conv2d(ip_chnls, op_chnls, 3, 2, 1),
           nn.LeakyReLU(0.2, inplace=True),
           nn.Dropout2d(0.25)]
    if bnorm:
        mod += [nn.BatchNorm2d(op_chnls, 0.8)]
    return mod

self.disc_model = nn.Sequential(
    *disc_module(1, 16, bnorm=False),
    *disc_module(16, 32),
    *disc_module(32, 64),
    *disc_module(64, 128))
```

`disc_module`은 층 객체를 담은 리스트를 돌려줍니다. 리스트 앞의 `*`는 리스트를 풀어서 원소를 하나씩 `nn.Sequential`에 넘깁니다. 블록 하나는 합성곱, Leaky ReLU, Dropout2d, 배치 정규화 순서이고, 첫 블록은 bnorm=False라 배치 정규화가 없습니다. DCGAN 논문도 판별기의 입력층에는 배치 정규화를 두지 않고, 풀링 대신 stride 합성곱으로 크기를 줄입니다.

`nn.Conv2d(ip_chnls, op_chnls, 3, 2, 1)`은 커널 크기 3, stride 2, padding 1입니다. 가로세로 64를 넣으면 (64 + 2 × 1 − 3) ÷ 2의 몫이 31이고, 31 + 1 = 32가 출력 크기입니다. 블록 넷을 지나며 가로세로는 64 → 32 → 16 → 8 → 4가 되고 채널은 16, 32, 64, 128이 됩니다. 사진 2장을 넣으면 disc_model의 출력은 (2, 128, 4, 4)입니다.

```ai-code-help
{"title": "합성곱 출력 크기", "explanation": "출력 크기는 (입력 크기 + 2 × padding − 커널 크기) ÷ stride의 몫에 1을 더한 값입니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11b", "step": 3, "title": "바깥을 채운 길이에서 출력 크기 계산하기"}}
```

```figure
파일: assets/a7d-1.gif
캡션: 그림 13. 사진 (2, 1, 64, 64)가 판별기 블록 넷을 지나며 (2, 128, 4, 4)가 됩니다.
내용: 왼쪽부터 가로세로 64, 32, 16, 8, 4인 사각형이 차례로 작아지고 사각형 위에 채널 1, 16, 32, 64, 128이 적혀 있습니다. 첫 블록 화살표에는 배치 정규화 없음 이름표가 있습니다.
프레임:
1. 첫 블록의 stride 2 합성곱이 가로세로 64를 32로 줄이고 채널을 16개로 만듭니다. 이 블록에는 배치 정규화가 없습니다. (2200ms)
2. 둘째 블록이 32를 16으로 줄이고 채널을 32개로 만듭니다. (2000ms)
3. 셋째 블록이 16을 8로, 넷째 블록이 8을 4로 줄이고 채널은 64개, 128개가 됩니다. (2200ms)
4. disc_model의 출력은 (2, 128, 4, 4)입니다. (2000ms)
```
```ai-recall
{"id": "r1", "q": "`nn.Conv2d(1, 1, 3, 2, 1)`에 가로세로 28인 사진을 넣으면 출력 가로세로는 ____ 입니다.", "answer": ["14"], "mode": "number"}
```


### ds_size로 Linear 입력 길이 2,048 맞추기
<!-- facts: FA07-d1 -->

2단계의 disc_model은 (2, 128, 4, 4)를 냅니다. Linear 층에 넣으려면 사진마다 한 줄로 펴야 하고, Linear 층은 그 줄의 길이를 미리 알아야 합니다.

```python
ds_size = image_sz // 2 ** 4
self.adverse_lyr = nn.Sequential(
    nn.Linear(128 * ds_size ** 2, 1),
    nn.Sigmoid())
```

파이썬은 `**`를 `//`보다 먼저 계산합니다. 그래서 `image_sz // 2 ** 4`는 2 ** 4 = 16을 먼저 구하고 64 // 16 = 4를 계산합니다. 블록 하나가 가로세로를 반으로 줄이므로 블록 넷을 지나면 image_sz를 2로 네 번 나눈 값이 남습니다. ds_size는 4이고, Linear 층의 입력 길이는 128 × 4 × 4 = 2,048입니다.

```python
x = self.disc_model(x)
x = x.view(x.shape[0], -1)
out = self.adverse_lyr(x)
```

`x.view(x.shape[0], -1)`은 크기가 2인 배치 축을 남기고 나머지 축을 한 줄로 펴서 (2, 2048)을 만듭니다. Linear 층과 Sigmoid를 지난 out의 모양은 (2, 1)입니다. 판별기 전체의 파라미터는 99,649개입니다.

```ai-code-help
{"title": "Linear 입력 길이", "explanation": "합성곱 층의 마지막 출력에서 채널 × 높이 × 너비가 Linear 층의 입력 길이가 됩니다.", "reference": {"course": "intro", "lesson": "l11", "unit": "11e", "step": 3, "title": "앞 층의 공간 크기로 Linear 입력 정하기"}}
```

```figure
파일: assets/a7d-2.png
캡션: 그림 14. 채널 128개, 가로세로 4인 특징 맵 한 장을 길이 2,048인 한 줄로 펴서 Linear 층에 넣습니다.
내용: 왼쪽에 채널 128개를 겹친 4×4 특징 맵이 있고, 오른쪽으로 화살표가 가서 길이 2,048인 긴 막대가 됩니다. 막대 아래에 128 × 4 × 4 = 2,048, 그 오른쪽에 Linear(2048, 1)과 Sigmoid 상자가 있습니다.
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r2", "q": "image_sz가 32이면 `image_sz // 2 ** 4`는 ____ 입니다.", "answer": ["2"], "mode": "number"}
```
```ai-why
{"q": "ds_size를 4로 적지 않고 image_sz로 계산하는 까닭은 무엇일까요?", "a": "image_sz를 바꾸면 블록 넷을 지난 가로세로도 바뀝니다. 식으로 두면 image_sz가 32일 때 ds_size가 2가 되어 Linear 층의 입력 길이 128 × 2 × 2 = 512가 실제 출력 길이와 맞습니다."}
```


### 이미지 크기 128에서 블록을 다섯으로 늘리기
<!-- facts: FA07-d1 -->

3단계의 식은 블록이 넷이라 2 ** 4를 썼습니다. 이미지 크기를 128로 키우고 블록을 다섯으로 늘리면 가로세로는 128 → 64 → 32 → 16 → 8 → 4가 됩니다. 이때 ds_size는 128 // 2 ** 5 = 4입니다.

Linear 층의 입력 길이는 다섯째 블록의 출력 채널에 따라 정해집니다.

- 다섯째 블록이 `disc_module(128, 128)`이면 입력 길이는 128 × 4 × 4 = 2,048입니다.
- 다섯째 블록이 `disc_module(128, 256)`이면 입력 길이는 256 × 4 × 4 = 4,096입니다. 그래서 `nn.Linear(128 * ds_size ** 2, 1)`의 128도 256으로 바꿉니다.

블록 수를 바꿨는데 ds_size 식의 지수를 그대로 두면 ds_size가 실제 가로세로와 달라집니다. 그러면 Linear 층의 입력 길이가 펼친 줄의 길이와 맞지 않습니다. 블록을 더하거나 뺄 때는 블록 수, ds_size의 지수, Linear 층 앞의 채널 수를 함께 확인합니다.

```figure
파일: assets/a7d-3.png
캡션: 그림 15. 이미지 크기 128에서 블록 다섯을 지난 뒤 다섯째 블록의 출력 채널이 128일 때와 256일 때의 Linear 입력 길이입니다.
내용: 위 줄은 128 → 64 → 32 → 16 → 8 → 4로 작아지는 사각형입니다. 아래에 두 갈래가 있고 왼쪽은 채널 128, 128 × 4 × 4 = 2,048, 오른쪽은 채널 256, 256 × 4 × 4 = 4,096입니다. 오른쪽 갈래의 Linear 상자에 256으로 바꿈 표시가 있습니다.
```
```ai-recall
{"id": "r3", "q": "image_sz가 256이고 블록이 다섯이면 ds_size는 ____ 입니다.", "answer": ["8"], "mode": "number"}
```
```ai-why
{"q": "블록을 다섯으로 늘릴 때 ds_size만 고치고 Linear 앞의 128을 그대로 두면 어떤 경우에 길이가 맞지 않을까요?", "a": "다섯째 블록의 출력 채널이 128이 아닐 때입니다. 출력 채널이 256이면 펼친 줄의 길이는 4,096인데 Linear 층은 128 × 4 × 4 = 2,048을 받습니다."}
```


### MNIST를 64로 키워 학습하고 200 배치마다 기록하기
<!-- facts: FA07-d4 FA07-a2 FA07-b3 FA07-b4 FA07-a3 FA07-a6 FA07-d2 FA07-d3 -->

셋째 단원의 생성기는 가로세로 64인 사진을 만들고, 2단계의 판별기도 가로세로 64인 사진을 받습니다. MNIST 사진은 가로세로 28이라서 학습에 넣기 전에 크기를 64로 키웁니다.

```python
transform = transforms.Compose([
    transforms.Resize((image_sz, image_sz)),   # 28 × 28 을 64 × 64 로 키움
    transforms.ToTensor(),                     # 픽셀 값을 0~1 로 바꿈
    transforms.Normalize([0.5], [0.5])])       # 0~1 을 −1~1 로 바꿈
dloader = DataLoader(datasets.MNIST('data', transform=transform), batch_size=32, shuffle=True)
optimizer_G = optim.Adam(generator.parameters(), lr=0.001)
optimizer_D = optim.Adam(discriminator.parameters(), lr=0.001)
```

`transforms.Resize((image_sz, image_sz))`는 사진 크기를 64 × 64로 바꿉니다. dloader는 이 transform을 거친 사진을 32장씩 묶어 내줍니다. `Normalize([0.5], [0.5])`는 ToTensor가 만든 0~1 값에서 0.5를 빼고 0.5로 나눕니다. 그래서 진짜 사진의 픽셀 값도 생성기 마지막 Tanh의 출력처럼 −1~1 범위에 들어갑니다.

두 옵티마이저에는 lr=0.001만 주고 betas는 적지 않았습니다. 그래서 betas는 기본값 (0.9, 0.999)입니다. 이 코드는 둘째 단원 4단계에서 본 DCGAN 논문 값 lr 0.0002, betas (0.5, 0.999)를 쓰지 않습니다.

학습 사진 60,000장을 모두 한 번씩 꺼내 쓰는 것을 1 에폭(epoch)이라고 부릅니다. 아래 반복은 num_eps = 10 에폭 동안 MNIST 학습 사진을 배치마다 꺼내 두 신경망을 갱신합니다. criterion은 첫 단원 3단계의 `nn.BCELoss()`입니다.

```python
for ep in range(num_eps):
    for idx, (real_images, _) in enumerate(dloader):
        current_batch_size = real_images.size(0)
        real_labels = torch.ones(current_batch_size, 1)
        fake_labels = torch.zeros(current_batch_size, 1)

        fake_images = generator(torch.randn(current_batch_size, lat_dimension))
        loss_G = criterion(discriminator(fake_images), real_labels)
        optimizer_G.zero_grad()
        loss_G.backward()
        optimizer_G.step()                     # 생성기를 먼저 갱신함

        loss_D_real = criterion(discriminator(real_images), real_labels)
        loss_D_fake = criterion(discriminator(fake_images.detach()), fake_labels)
        loss_D = (loss_D_real + loss_D_fake) / 2
        optimizer_D.zero_grad()
        loss_D.backward()                      # 판별기 grad 만 채워짐
        optimizer_D.step()
```

real_labels와 fake_labels의 크기는 둘째 단원 5단계처럼 배치에 든 사진 수 current_batch_size로 정합니다. DCGAN 판별기는 (배치, 1, 64, 64) 모양을 받으므로 real_images를 view로 펴지 않습니다.

이 반복은 생성기를 먼저 갱신하고 판별기를 나중에 갱신합니다. 둘째 단원 2·3단계 코드와 순서가 반대입니다. 판별기 단계는 새 노이즈를 뽑지 않고, 생성기 단계에서 만든 fake_images를 detach()해서 다시 넣습니다. 판별기 손실은 진짜 쪽과 가짜 쪽을 더해 2로 나눈 평균입니다. 첫 단원 3단계의 판별기 손실은 두 값을 더하기만 했습니다.

배치 크기가 32라서 한 에폭은 60,000 ÷ 32 = 1,875 배치입니다. 아래 세 줄은 위 반복 안에서 `optimizer_D.step()` 다음에 이어집니다.

```python
batches_completed = ep * len(dloader) + idx
if batches_completed % logging_intv == 0:
    print(f'epoch number {ep} | batch number {idx} | ...')
```

ep는 에폭 번호, idx는 그 에폭 안의 배치 번호이고 logging_intv는 200입니다. batches_completed는 학습을 시작한 뒤 처음부터 센 배치 번호라서 에폭이 바뀌어도 이어집니다. 10 에폭은 18,750 배치이고, 그 가운데 200의 배수는 0, 200, …, 18,600으로 94개입니다. 그래서 기록은 94줄입니다. 마지막 줄의 18,600은 9 × 1,875 + 1,725라서 에폭 9, 배치 1725로 찍힙니다.

이 학습을 한 번 돌린 기록에서 첫 줄은 에폭 0, 배치 0이고, 생성기 손실 0.6957과 판별기 손실 0.6942가 찍혔습니다. 첫 단원 5단계는 이 두 값을 ln 2 = 0.6931과 비교했습니다.

기록할 때마다 그 순간의 가짜 사진을 batches_completed를 이름으로 한 PNG 파일로 저장합니다. 파일 이름은 '0.png', '200.png', …, '18600.png'입니다. 이 이름을 `sorted`로 정렬하면 글자를 앞에서부터 비교하므로 '1000.png'가 '200.png'보다 앞에 옵니다. 숫자 크기 순서로 놓으려면 `natsort.natsorted`처럼 이름 안의 숫자를 수로 비교하는 정렬을 씁니다.

```figure
파일: assets/a7d-4.png
캡션: 그림 16. 파일 이름 '0.png', '200.png', '1000.png'를 sorted와 natsort.natsorted로 정렬한 결과입니다.
내용: 왼쪽 열은 sorted 결과 '0.png', '1000.png', '200.png'이고 둘째 줄에 빨간 표시가 있습니다. 오른쪽 열은 natsorted 결과 '0.png', '200.png', '1000.png'입니다.
```
```ai-recall
{"id": "r4", "q": "같은 학습에서 logging_intv를 500으로 바꾸면 기록 줄 수는 ____ 입니다.", "answer": ["38"], "mode": "number"}
```


### 외울 것
<!-- facts: FA07-d1 FA07-d2 FA07-d3 -->

```ai-memo
[{"q": "판별기 블록 넷은 가로세로 64를 얼마로 줄이고 Linear 입력 길이는 얼마인가요?", "a": "kernel 3, stride 2, padding 1 합성곱이 64 → 32 → 16 → 8 → 4로 줄입니다. ds_size = 64 // 2 ** 4 = 4이고 Linear 입력은 128 × 4 × 4 = 2,048입니다.", "cards": ["a07-b13", "a07-b15", "a07-b16"]}, {"q": "블록을 하나 더 넣으면 함께 고칠 곳은 어디인가요?", "a": "ds_size 식의 지수와 Linear 앞의 채널 수입니다. 이미지 128, 블록 다섯, 마지막 채널 256이면 ds_size = 4, 입력 길이는 256 × 4 × 4 = 4,096입니다.", "cards": ["a07-b14", "a07-c07"]}, {"q": "sorted가 '1000.png'를 '200.png' 앞에 두는 까닭은 무엇인가요?", "a": "글자를 앞에서부터 비교해서 '1'이 '2'보다 앞이기 때문입니다. 숫자 순서로 놓으려면 natsort.natsorted를 씁니다.", "cards": ["a07-c08"]}]
```


## VAE 인코더가 평균과 로그 분산을 내고 z 뽑기


### 먼저 풀어 보기
<!-- facts: FA07-e2 FA07-e4 -->

```ai-guess
{"id": "g1", "q": "VAE 인코더는 사진을 받아 잠재 차원마다 평균과 로그 분산을 냅니다. 잠재 차원은 사진을 줄여 나타낸 숫자 묶음 z에서 숫자 하나가 놓인 자리입니다. 로그 분산은 분산에 자연로그를 씌운 값입니다. 어느 잠재 차원의 로그 분산이 0이면 이 차원의 표준편차는 얼마일까요?", "options": ["0", "1"], "answer": 1, "reveal_step": 3, "cards": ["a07-b19"]}
```

```ai-guess
{"id": "g2", "q": "인코더가 낸 값으로 평균 μ와 표준편차 σ를 정합니다. ε는 평균 0, 표준편차 1인 정규분포에서 무작위로 뽑은 수입니다. z = μ + σ × ε로 z를 만든 뒤 z를 backward 하면 μ에 기울기가 생길까요?", "options": ["생깁니다. μ의 기울기는 1입니다.", "생기지 않습니다. ε를 무작위로 뽑았기 때문입니다."], "answer": 0, "reveal_step": 4, "cards": ["a07-b18"]}
```


### 784개 픽셀을 평균 200개와 로그 분산 200개로 줄이기
<!-- facts: FA07-e1 FA07-e3 -->

MNIST 손글씨 숫자 사진 한 장은 28 × 28 = 784개 픽셀입니다. 픽셀 784개를 그보다 적은 숫자로 줄이는 신경망을 인코더라고 부릅니다. 줄인 숫자에서 픽셀 784개를 다시 만드는 신경망은 디코더라고 부릅니다. 이 단원의 디코더는 숫자 200개를 받습니다. 디코더가 받는 숫자 200개를 z로 적습니다. z가 놓이는 200차원 공간은 잠재 공간이라고 부릅니다.

인코더가 z 값 200개를 바로 내는 신경망도 있습니다. 그런 신경망에서는 같은 사진이 늘 같은 z가 됩니다. VAE(variational autoencoder)의 인코더는 z 값을 바로 내지 않습니다. 잠재 차원마다 정규분포 하나를 정할 평균과 로그 분산을 내므로, 평균 200개와 로그 분산 200개가 나옵니다. z의 숫자 200개는 차원마다 그 정규분포에서 하나씩 뽑습니다. 그래서 같은 사진을 넣어도 뽑을 때마다 z가 조금씩 달라집니다.

```python
import torch
import torch.nn as nn

class Encoder(nn.Module):
    def __init__(self, x_dim=784, h_dim=400, z_dim=200):
        super().__init__()
        self.fc1 = nn.Linear(x_dim, h_dim)
        self.fc2 = nn.Linear(h_dim, h_dim)
        self.fc_mean = nn.Linear(h_dim, z_dim)
        self.fc_log_var = nn.Linear(h_dim, z_dim)
        self.act = nn.LeakyReLU(0.2)

    def forward(self, x):                      # x: (100, 784)
        h = self.act(self.fc1(x))              # (100, 400)
        h = self.act(self.fc2(h))              # (100, 400)
        return self.fc_mean(h), self.fc_log_var(h)   # (100, 200), (100, 200)
```

forward는 은닉층 두 개를 지난 h를 fc_mean과 fc_log_var에 똑같이 넣습니다. fc_mean은 평균 μ를, fc_log_var는 로그 분산 log σ²를 냅니다. 로그 분산은 분산 σ²에 자연로그를 씌운 값입니다. 이 노트에서 log와 ln은 같은 자연로그입니다. 코드 주석의 100은 배치 크기라서 배치 하나에 사진 100장이 들어옵니다. 두 출력의 모양은 같은 (100, 200)입니다. 사진마다 잠재 차원 200개의 μ와 log σ²가 하나씩 나옵니다.

인코더의 파라미터는 Linear 층 넷의 가중치와 편향을 더한 값입니다. fc1은 784 × 400 + 400 = 314,000개이고, fc2는 400 × 400 + 400 = 160,400개입니다. fc_mean과 fc_log_var는 400 × 200 + 200 = 80,200개씩입니다. 모두 더하면 인코더의 파라미터는 634,800개입니다.

```figure
파일: assets/a7e-1.gif
캡션: 그림 17. 사진 한 장이 인코더를 지나 평균과 로그 분산이 되고, 그 둘로 뽑은 z가 디코더를 지나 사진으로 돌아옵니다.
내용: 784칸 사진이 인코더를 지나 평균 200칸과 로그 분산 200칸으로 갈라집니다. 로그 분산은 표준편차가 되고 무작위 ε와 함께 z 200칸을 만듭니다. z는 디코더를 지나 784칸 사진이 됩니다.
프레임:
1. 784개 픽셀인 사진 한 장이 인코더로 들어갑니다. (2000ms)
2. 인코더는 은닉층 두 개를 지나 평균 μ 200개와 로그 분산 log σ² 200개를 냅니다. (2200ms)
3. 로그 분산을 표준편차 σ로 바꾸고, 무작위로 뽑은 ε와 함께 z 200개를 만듭니다. (2200ms)
4. 디코더가 z 200개를 받아 784개 픽셀인 사진을 다시 만듭니다. (2000ms)
```
```ai-recall
{"id": "r1", "q": "평균을 내는 층 nn.Linear(400, 200)의 파라미터는 ____ 개입니다.", "answer": ["80200"], "mode": "number"}
```
```ai-why
{"q": "VAE 인코더가 잠재 차원마다 숫자 하나가 아니라 평균과 로그 분산 두 개를 내는 까닭은 무엇일까요?", "a": "z를 정규분포에서 뽑기 때문입니다. 정규분포 하나를 정하려면 평균과 퍼진 정도 두 값이 있어야 합니다. 퍼진 정도는 로그 분산으로 내고, 3단계에서 표준편차로 바꿉니다."}
```


### 로그 분산에서 표준편차 구하기
<!-- facts: FA07-e2 -->

2단계의 fc_log_var는 로그 분산 log σ²를 냈습니다. z를 뽑을 때는 표준편차 σ가 필요합니다. 분산 σ²는 exp(log σ²)이고, 표준편차는 분산의 제곱근입니다. 두 계산을 합치면 σ = exp(0.5 × log σ²)입니다.

```python
std = torch.exp(0.5 * log_var)    # (100, 200)
```

잠재 차원 하나의 μ가 1이고 log σ²가 ln 4 = 1.3863이라고 해 봅니다. 0.5 × 1.3863 = 0.6931이고 exp(0.6931) = 2입니다. 그래서 σ는 2입니다. log σ²가 0이면 exp(0) = 1이라 σ는 1입니다. log σ²가 −2이면 exp(−1)이라 σ는 0.368입니다.

Linear 층의 출력은 음수도 됩니다. 출력을 바로 표준편차로 쓰면 음수 표준편차가 나올 수 있습니다. 출력을 로그 분산으로 두고 exp를 씌우면 어떤 출력이 나와도 σ는 0보다 큽니다.

```figure
파일: assets/a7e-2.png
캡션: 그림 18. 로그 분산이 −2, 0, ln 4일 때 표준편차는 0.368, 1, 2입니다.
내용: 가로축은 로그 분산, 세로축은 표준편차인 곡선 exp(0.5 × log σ²)입니다. 로그 분산 −2, 0, ln 4 자리에 점을 찍고 표준편차 0.368, 1, 2를 적었습니다. 곡선은 가로축 아래로 내려가지 않습니다.
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r2", "q": "log σ²가 ln 9이면 표준편차는 ____ 입니다.", "answer": ["3"], "mode": "number"}
```
```ai-why
{"q": "fc_log_var의 출력을 로그 분산으로 두면 표준편차가 음수가 되지 않는 까닭은 무엇일까요?", "a": "σ = exp(0.5 × log σ²)에서 exp는 어떤 수를 넣어도 0보다 큰 값을 냅니다. 그래서 출력이 −2처럼 음수여도 σ는 0.368처럼 양수입니다."}
```

```ai-levels
{"id": "v1", "concept": "로그 분산에서 표준편차", "levels": [{"level": 7, "text": "로그 분산이 0이면 표준편차는 1입니다. 로그 분산이 0보다 크면 표준편차는 1보다 커집니다. 로그 분산이 0보다 작으면 표준편차는 1보다 작아집니다. 어느 경우에도 표준편차는 0보다 큽니다.", "q": "로그 분산이 1, 5, 2인 세 칸 가운데 표준편차가 가장 큰 칸의 로그 분산은 ____ 입니다.", "answer": ["5"], "mode": "number", "why": "로그 분산이 클수록 표준편차가 커집니다. 세 칸 가운데 로그 분산이 가장 큰 칸은 5입니다.", "figure": {"file": "assets/a7e-31.png", "caption": "로그 분산이 커질수록 표준편차가 커지는 모습입니다.", "content": "로그 분산 칸 세 개에 0보다 작은 수, 0, 0보다 큰 수를 적고, 아래 칸에 1보다 작은 수, 1, 1보다 큰 수를 화살표로 이었습니다."}}, {"level": 15, "text": "표준편차 = e^(0.5 × 로그 분산)입니다. 로그 분산이 −2이면 0.5 × (−2) = −1이고 e^(−1) = 0.3679입니다. 로그 분산이 ln 4이면 0.5 × ln 4 = ln 2이고 e^(ln 2) = 2입니다.", "q": "로그 분산이 2이면 표준편차는 소수 넷째 자리까지 ____ 입니다.", "answer": ["2.7183"], "mode": "number", "places": 4, "why": "0.5 × 2 = 1이고 e^1 = 2.7183입니다.", "figure": {"file": "assets/a7e-32.png", "caption": "로그 분산 −2와 ln 4를 표준편차로 바꾸는 계산을 두 줄 표로 적었습니다.", "content": "첫 줄은 로그 분산 −2, 절반 −1, 표준편차 0.3679입니다. 둘째 줄은 로그 분산 ln 4, 절반 ln 2, 표준편차 2입니다."}}, {"level": 20, "text": "fc_log_var의 출력은 로그 분산입니다. 표준편차는 exp(0.5 * log_var)로 구합니다.", "code": "log_var = torch.tensor([-2.0, 0.0, 1.3863])\nstd = torch.exp(0.5 * log_var)   # 0.3679, 1, 2\nbad = torch.sqrt(log_var)         # nan, 0, 1.1774", "mistake": "fc_log_var의 출력을 분산으로 보고 제곱근을 씌우는 착각입니다. 출력이 음수인 첫 칸은 nan이 됩니다. 출력은 로그 분산이라 exp(0.5 * log_var)로 표준편차를 구합니다.", "q": "log_var가 −4인 칸의 std는 소수 넷째 자리까지 ____ 입니다.", "answer": ["0.1353"], "mode": "number", "places": 4, "why": "0.5 × (−4) = −2이고 exp(−2) = 0.1353입니다.", "figure": {"file": "assets/a7e-33.png", "caption": "같은 세 출력에 exp(0.5 * log_var)와 sqrt를 각각 씌운 결과입니다.", "content": "출력 −2, 0, 1.3863 아래에 std 줄 0.3679, 1, 2와 bad 줄 nan, 0, 1.1774를 나란히 적었습니다. bad 줄의 nan 칸에 빨간 테두리를 그렸습니다."}}]}
```


### ε를 따로 뽑아 z를 만들고 기울기 흘리기
<!-- facts: FA07-e3 FA07-e4 -->

3단계에서 σ를 구했습니다. 이제 평균 μ, 표준편차 σ인 정규분포에서 z를 뽑습니다. 먼저 평균 0, 표준편차 1인 표준 정규분포에서 ε를 뽑습니다. 그다음 z = μ + σ × ε를 계산합니다. 이렇게 뽑는 방법을 재매개변수화(reparameterization)라고 부릅니다.

```python
def sample_z(mean, log_var):
    std = torch.exp(0.5 * log_var)
    epsilon = torch.randn_like(std)    # std와 같은 모양, 평균 0, 표준편차 1
    return mean + std * epsilon        # (100, 200)
```

`torch.randn_like(std)`는 std와 같은 모양의 텐서를 표준 정규분포에서 뽑은 수로 채웁니다. 그래서 사진 100장의 잠재 차원 200개마다 ε가 하나씩 따로 나옵니다.

3단계의 μ = 1, σ = 2에 ε 다섯 개를 넣어 봅니다. ε가 −1.5이면 z = 1 + 2 × (−1.5) = −2입니다. ε가 −0.5, 0, 0.5, 1.5이면 z는 0, 1, 2, 4입니다. ε가 0이면 z는 μ와 같습니다. ε가 같을 때 σ가 클수록 z가 μ에서 멀리 떨어집니다.

무작위로 뽑는 일은 ε에만 있습니다. μ와 σ는 더하기와 곱하기로만 z에 들어갑니다. 그래서 z를 backward 하면 기울기가 μ와 log σ²를 거쳐 인코더까지 갑니다. ε = 0.5로 고정하고 z.sum()을 backward 하면 μ의 기울기는 1입니다. σ = exp(0.5 × log σ²)를 log σ²로 미분하면 0.5 × σ입니다. z = μ + σ × ε를 σ로 미분하면 ε가 됩니다. 두 미분값을 곱하면 log σ²의 기울기는 0.5 × σ × ε입니다. 값을 넣으면 0.5 × 2 × 0.5 = 0.5입니다.

```ai-code-help
{"title": "torch.randn_like", "explanation": "randn_like는 넘긴 텐서와 같은 모양과 자료형의 새 텐서를 평균 0, 표준편차 1인 정규분포에서 뽑은 수로 채웁니다. 넘긴 텐서의 값은 쓰지 않습니다.", "reference": {"course": "intro", "lesson": "l03", "unit": "3b", "step": 4, "title": "같은 값이나 난수로 채워 만들기"}}
```

```figure
파일: assets/a7e-3.png
캡션: 그림 19. μ = 1, σ = 2일 때 ε 다섯 개로 뽑은 z를 수직선에 찍었습니다.
내용: 위 수직선에 ε −1.5, −0.5, 0, 0.5, 1.5를 찍고, 아래 수직선에 z −2, 0, 1, 2, 4를 찍어 같은 ε끼리 화살표로 이었습니다. z 수직선의 1 자리에 μ를 적었습니다.
```
```ai-reveal
{"guess": "g2"}
```
```ai-recall
{"id": "r3", "q": "μ = 0, σ = 3이고 ε = −1이면 z는 ____ 입니다.", "answer": ["-3"], "mode": "number"}
```
```ai-why
{"q": "z를 N(μ, σ²)에서 바로 뽑지 않고 ε를 따로 뽑아 μ + σ × ε로 만드는 까닭은 무엇일까요?", "a": "무작위로 뽑는 일을 ε에만 두면 z는 μ와 σ의 더하기와 곱하기로 정해집니다. 그래서 z에서 μ로 가는 기울기가 1, σ로 가는 기울기가 ε처럼 식으로 정해지고, 손실의 기울기가 인코더까지 갑니다."}
```


### 디코더로 z를 784개 픽셀로 되돌리고 노이즈로 새 사진 만들기
<!-- facts: FA07-e1 FA07-e5 -->

4단계에서 뽑은 z는 (100, 200) 모양입니다. 디코더는 이 z를 받아 사진 100장을 다시 만듭니다. 층은 인코더를 거꾸로 놓은 200 → 400 → 400 → 784입니다.

```python
class Decoder(nn.Module):
    def __init__(self, z_dim=200, h_dim=400, x_dim=784):
        super().__init__()
        self.fc1 = nn.Linear(z_dim, h_dim)
        self.fc2 = nn.Linear(h_dim, h_dim)
        self.fc_out = nn.Linear(h_dim, x_dim)
        self.act = nn.LeakyReLU(0.2)

    def forward(self, z):                         # z: (100, 200)
        h = self.act(self.fc1(z))
        h = self.act(self.fc2(h))
        return torch.sigmoid(self.fc_out(h))      # (100, 784), 값은 0~1
```

마지막 줄의 시그모이드는 784개 출력을 모두 0~1로 바꿉니다. 그래서 디코더 출력 하나하나를 픽셀 밝기로 읽습니다.

디코더의 파라미터도 Linear 층 셋의 가중치와 편향을 더해 셉니다. fc1은 200 × 400 + 400 = 80,400개이고, fc2는 400 × 400 + 400 = 160,400개입니다. fc_out은 400 × 784 + 784 = 314,384개입니다. 셋을 더한 디코더의 파라미터는 555,184개입니다.

새 사진을 만들 때는 인코더를 쓰지 않습니다. 평균 0, 표준편차 1인 정규분포에서 z 모양의 노이즈를 뽑아 디코더에 바로 넣습니다. 이렇게 뽑은 노이즈를 넣어도 디코더가 학습 때와 비슷한 z를 받는 까닭은 여섯째 단원 3단계의 KL 항에서 다룹니다.

```python
with torch.no_grad():
    noise = torch.randn(100, 200)              # 사진 100장, 잠재 차원 200
    images = decoder(noise).view(100, 1, 28, 28)
```

`torch.randn(100, 200)`은 사진 100장에 쓸 z를 한 번에 뽑습니다. 디코더 출력 (100, 784)를 view로 (100, 1, 28, 28)로 바꾸면 흑백 사진 100장의 모양이 됩니다.

```figure
파일: assets/a7e-4.png
캡션: 그림 20. 학습할 때는 사진에서 시작해 인코더와 디코더를 모두 지나고, 새 사진을 만들 때는 노이즈에서 시작해 디코더만 지납니다.
내용: 윗줄은 학습 경로로 사진 (100, 784) → 인코더 → z (100, 200) → 디코더 → (100, 784)입니다. 아랫줄은 생성 경로로 torch.randn(100, 200) → 디코더 → (100, 784) → (100, 1, 28, 28)입니다. 아랫줄의 인코더 자리는 회색 점선입니다.
```
```ai-recall
{"id": "r4", "q": "디코더 마지막 층 nn.Linear(400, 784)의 파라미터는 ____ 개입니다.", "answer": ["314384"], "mode": "number"}
```
```ai-why
{"q": "새 사진을 만들 때 torch.randn(100, 200)에서 둘째 숫자를 200으로 맞추는 까닭은 무엇일까요?", "a": "디코더의 첫 층 nn.Linear(200, 400)은 사진 한 장에 쓸 숫자 200개를 받습니다. 학습 때 인코더 쪽에서 뽑은 z도 잠재 차원이 200개였습니다. 첫째 숫자 100은 한 번에 만들 사진 수입니다. 이 수를 바꿀 때는 다음 줄 view(100, 1, 28, 28)의 100도 같은 수로 바꿉니다."}
```


### 외울 것
<!-- facts: FA07-e1 FA07-e2 FA07-e3 FA07-e5 -->

```ai-memo
[{"q": "VAE 인코더와 디코더는 각각 무엇을 하나요?", "a": "인코더는 잠재 차원마다 평균 μ와 로그 분산 log σ²를 냅니다. 디코더는 z를 받아 시그모이드로 0~1 픽셀 값을 냅니다. 새 사진을 만들 때는 인코더 없이 torch.randn(100, 200) 같은 노이즈를 디코더에 넣습니다.", "cards": ["a07-b17"]}, {"q": "로그 분산에서 표준편차를 구하는 식은 무엇인가요?", "a": "σ = exp(0.5 × log σ²)입니다. 코드로는 torch.exp(0.5 * log_var)이고, log σ²가 ln 4이면 σ는 2입니다.", "cards": ["a07-b19", "a07-c09"]}, {"q": "재매개변수화로 z를 뽑는 식은 무엇인가요?", "a": "z = μ + σ × ε이고 ε는 평균 0, 표준편차 1인 정규분포에서 뽑습니다. μ = 1, σ = 2, ε = 0.5이면 z는 2입니다.", "cards": ["a07-b18", "a07-b20", "a07-c10"]}]
```


## VAE 손실의 복원 항과 KL 항 계산하기


### 먼저 풀어 보기
<!-- facts: FA07-f1 FA07-f2 -->

```ai-guess
{"id": "g1", "q": "잠재 차원 하나에서 μ = 1, log σ² = 0이면 KL 항은 얼마일까요?", "options": ["0", "0.5", "1"], "answer": 1, "reveal_step": 3, "cards": ["a07-b21"]}
```

```ai-guess
{"id": "g2", "q": "전처리에 Normalize([0.5], [0.5])를 넣어 MNIST 픽셀을 −1~1로 바꿉니다. 이 픽셀을 BCE의 정답으로 쓰면 어떻게 될까요?", "options": ["손실이 계산되고 학습이 그대로 진행됩니다.", "정답이 0~1 밖에 있어 오류가 납니다."], "answer": 1, "reveal_step": 2, "cards": ["a07-c11"]}
```


### 784개 픽셀의 BCE를 모두 더한 복원 항
<!-- facts: FA07-f2 -->

다섯째 단원 5단계의 디코더는 시그모이드를 거쳐 0~1 픽셀 값 x̂를 냅니다. VAE 손실의 첫째 항은 x̂가 원래 사진 x와 얼마나 다른지 잽니다. 이 항을 복원 항이라고 부릅니다. 복원 항은 픽셀마다 이진 교차 엔트로피를 구해 784개를 모두 더한 값입니다.

픽셀 셋으로 줄여 계산해 봅니다. 원래 픽셀 x가 [1, 0, 1]이고 디코더 출력 x̂가 [0.8, 0.1, 0.9]입니다. 정답이 1인 첫 픽셀은 −ln 0.8 = 0.2231입니다. 정답이 0인 둘째 픽셀은 −ln(1 − 0.1) = 0.1054입니다. 셋째 픽셀은 −ln 0.9 = 0.1054입니다. 셋을 더한 복원 항은 0.4339입니다.

```python
import torch.nn.functional as F

recon = F.binary_cross_entropy(x_hat, x, reduction='sum')   # 픽셀마다 BCE를 구해 모두 더함
```

`F.binary_cross_entropy`의 reduction 기본값은 'mean'입니다. 기본값으로 두면 픽셀 셋의 예는 0.4339 ÷ 3 = 0.1446이 됩니다. `reduction='sum'`은 배치에 든 사진 100장의 픽셀 784개씩, 모두 78,400개의 BCE를 더합니다.

BCE의 정답 x는 0과 1 사이에 있어야 합니다. 그래서 MNIST 사진은 ToTensor로 0~1로만 바꾸고 Normalize를 쓰지 않습니다. Normalize([0.5], [0.5])를 넣으면 픽셀 0이 (0 − 0.5) ÷ 0.5 = −1이 됩니다. 이 값을 정답으로 넣으면 PyTorch가 정답이 0과 1 사이에 있어야 한다는 RuntimeError를 냅니다.

```ai-code-help
{"title": "BCE", "explanation": "정답이 1인 픽셀은 −ln x̂, 정답이 0인 픽셀은 −ln(1 − x̂)를 손실로 씁니다. 복원 항은 이 값을 픽셀마다 구해 더합니다.", "reference": {"course": "intro", "lesson": "l06", "unit": "6c", "step": 2, "title": "BCE는 정답이 1이면 −log p, 0이면 −log(1 − p)"}}
```

```ai-code-help
{"title": "reduction 인자", "explanation": "reduction='mean'은 원소마다 구한 손실의 평균을 내고, 복원 항이 쓰는 reduction='sum'은 합을 냅니다.", "reference": {"course": "intro", "lesson": "l06", "unit": "6f", "step": 3, "title": "reduction 인자와 직접 만든 손실 코드 읽기"}}
```

```figure
파일: assets/a7f-1.png
캡션: 그림 21. 픽셀 셋의 정답 x와 디코더 출력 x̂로 구한 BCE를 더하면 0.4339, 평균을 내면 0.1446입니다.
내용: 세 줄 표에 픽셀마다 x 1, 0, 1과 x̂ 0.8, 0.1, 0.9, BCE 0.2231, 0.1054, 0.1054를 적었습니다. 표 아래에 reduction='sum' 0.4339와 reduction='mean' 0.1446을 나란히 적었습니다.
```
```ai-reveal
{"guess": "g2"}
```
```ai-recall
{"id": "r1", "q": "정답 픽셀이 1이고 디코더 출력이 0.5이면 그 픽셀의 BCE는 소수 넷째 자리까지 ____ 입니다.", "answer": ["0.6931"], "mode": "number", "places": 4}
```
```ai-why
{"q": "VAE 학습 데이터에 ToTensor만 쓰고 Normalize([0.5], [0.5])를 쓰지 않는 까닭은 무엇일까요?", "a": "복원 항의 BCE는 정답 픽셀이 0과 1 사이에 있어야 계산됩니다. Normalize([0.5], [0.5])를 쓰면 픽셀 0이 −1이 되어 오류가 납니다. 디코더 출력도 시그모이드를 거친 0~1 값이라 정답과 범위가 맞습니다."}
```


### KL 항으로 잠재 분포를 N(0, 1) 쪽으로 당기기
<!-- facts: FA07-f1 FA07-e5 -->

복원 항만 줄이면 인코더는 사진마다 μ와 σ를 마음대로 정합니다. VAE 손실의 둘째 항은 잠재 차원마다 인코더가 정한 정규분포 N(μ, σ²)가 표준 정규분포 N(0, 1)과 얼마나 다른지 KL divergence로 잽니다. 이 항을 KL 항이라고 부릅니다. 두 분포가 모두 정규분포라 KL 항은 식 하나로 계산됩니다.

KL 항 = −0.5 × Σ(1 + log σ² − μ² − σ²)

괄호 안은 잠재 차원마다 따로 계산하고, Σ로 모든 차원의 값을 더합니다. 한 차원에서 μ = 0, log σ² = 0이면 σ² = 1이라 1 + 0 − 0 − 1 = 0이고 KL 항은 0입니다. 인코더가 N(0, 1)을 그대로 내면 KL 항이 0이 됩니다.

μ = 1, log σ² = 0이면 괄호 안은 1 + 0 − 1 − 1 = −1이고 KL 항은 0.5입니다. 다섯째 단원 3단계의 μ = 1, log σ² = ln 4는 σ² = 4입니다. 괄호 안은 1 + 1.3863 − 1 − 4 = −2.6137이고 KL 항은 1.3069입니다. 평균만 0에서 벗어나도, 분산만 1에서 벗어나도 KL 항이 커집니다. μ = 0, log σ² = ln 4이면 0.8069이고, μ = 0, log σ² = ln 0.25이면 0.3181입니다.

```python
kld = -0.5 * torch.sum(1 + log_var - mean.pow(2) - log_var.exp())
```

`log_var.exp()`는 σ²이고 `mean.pow(2)`는 μ²입니다. `torch.sum`에 축을 주지 않아서 배치에 든 사진 100장과 잠재 차원 200개의 값을 모두 더한 숫자 하나가 나옵니다. 잠재 차원 두 개가 (μ, log σ²) = (1, 0), (0, ln 4)이면 0.5 + 0.8069 = 1.3069입니다. 이 값은 μ = 1, log σ² = ln 4인 차원 하나의 KL 항과 같습니다. 한 차원의 KL 항은 0.5 × μ²와 −0.5 × (1 + log σ² − σ²)의 합으로 나눠 적을 수 있습니다. 앞부분은 μ로만 정해지고, 뒷부분은 log σ²로만 정해집니다. (1, 0) 차원의 0.5는 앞부분에서 나오고, 이 차원의 뒷부분은 0입니다. (0, ln 4) 차원의 0.8069는 뒷부분에서 나오고, 이 차원의 앞부분은 0입니다. (1, ln 4) 차원 하나는 앞부분 0.5와 뒷부분 0.8069를 함께 가집니다. 그래서 이 차원 하나의 KL 항도 0.5 + 0.8069 = 1.3069입니다.

KL 항을 줄이면 인코더가 내는 μ는 0 쪽으로, σ²는 1 쪽으로 당겨집니다. 그러면 학습하는 동안 디코더가 받는 z도 N(0, 1) 근처에 모입니다. 그래서 다섯째 단원 5단계처럼 인코더 없이 torch.randn(100, 200)으로 뽑은 노이즈를 넣어도, 디코더는 학습 때와 비슷한 z를 받습니다.

```ai-code-help
{"title": "KL divergence", "explanation": "개론 9차시는 클래스가 셋인 두 확률 분포에서 클래스마다 P × log(P ÷ Q)를 더했습니다. 여기서는 두 분포가 정규분포라 같은 KL divergence가 μ와 log σ²로 된 식 하나가 됩니다.", "reference": {"course": "intro", "lesson": "l09", "unit": "9d", "step": 2, "title": "정답 분포와 예측 분포의 차이를 KL divergence로 재기"}}
```

```figure
파일: assets/a7f-2.gif
캡션: 그림 22. μ와 log σ²를 바꾸면 N(μ, σ²) 곡선이 N(0, 1) 곡선에서 벗어나고 KL 항이 커집니다.
내용: 회색 곡선은 N(0, 1)이고 파란 곡선은 인코더가 낸 N(μ, σ²)입니다. 장마다 μ와 log σ²를 바꾸고 오른쪽 위에 KL 항을 적었습니다.
프레임:
1. μ = 0, log σ² = 0이면 두 곡선이 겹치고 KL 항은 0입니다. (2000ms)
2. μ = 1, log σ² = 0이면 곡선이 오른쪽으로 1 옮겨 가고 KL 항은 0.5입니다. (2200ms)
3. μ = 0, log σ² = ln 4이면 곡선이 넓게 퍼지고 KL 항은 0.8069입니다. (2200ms)
4. μ = 0, log σ² = ln 0.25이면 곡선이 좁아지고 KL 항은 0.3181입니다. (2200ms)
5. 두 차원 (1, 0)과 (0, ln 4)의 KL 항을 더하면 1.3069입니다. (2400ms)
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r2", "q": "잠재 차원 하나에서 μ = 2, log σ² = 0이면 KL 항은 ____ 입니다.", "answer": ["2"], "mode": "number"}
```
```ai-why
{"q": "μ = 0일 때 σ²를 1보다 작은 0.25로 줄여도 KL 항이 0이 아니라 0.3181로 커지는 까닭은 무엇일까요?", "a": "σ² = 0.25이면 log σ²는 ln 0.25 = −1.386294입니다. 이때 괄호 안은 1 − 1.386294 − 0 − 0.25 = −0.636294입니다. 여기에 −0.5를 곱한 KL 항은 0.318147입니다. 괄호 안은 σ² = 1일 때 가장 크고, 1에서 멀어지면 어느 쪽이든 작아집니다. 그래서 KL 항은 μ = 0, σ² = 1일 때만 0입니다."}
```

```ai-levels
{"id": "v1", "concept": "KL 항", "levels": [{"level": 7, "text": "가운데 자리가 0이고 퍼진 정도가 1인 산 모양을 기준으로 둡니다. 퍼진 정도는 두고 산의 가운데 자리만 옮겨 봅니다. 가운데를 멀리 옮길수록 기준으로 둔 산에서 벗어난 정도를 재는 값이 커집니다. 가운데를 1로 옮기면 0.5이고, 2로 옮기면 2입니다. 옮긴 수를 두 번 곱한 값의 반입니다.", "q": "가운데를 3으로 옮기면 값은 ____ 입니다.", "answer": ["4.5"], "mode": "number", "why": "3을 두 번 곱하면 9이고, 9의 반은 4.5입니다.", "figure": {"file": "assets/a7f-31.png", "caption": "가운데 자리를 0, 1, 2로 옮길 때 생기는 값입니다.", "content": "수직선 위 0, 1, 2 자리에 같은 모양의 산을 세 개 그리고, 산 아래에 값 0, 0.5, 2를 적었습니다."}}, {"level": 15, "text": "KL 항 = −0.5 × (1 + log σ² − μ² − σ²)입니다. μ = 1, log σ² = ln 4 = 1.3863이면 σ² = 4입니다. −0.5 × (1 + 1.3863 − 1 − 4) = −0.5 × (−2.6137) = 1.30685입니다. 소수 넷째 자리까지 반올림하면 1.3069입니다.", "q": "μ = 0, log σ² = ln 9 = 2.1972이면 KL 항은 소수 넷째 자리까지 ____ 입니다.", "answer": ["2.9014"], "mode": "number", "places": 4, "why": "σ² = 9입니다. −0.5 × (1 + 2.1972 − 0 − 9) = −0.5 × (−5.8028) = 2.9014입니다.", "figure": {"file": "assets/a7f-32.png", "caption": "μ = 1, log σ² = ln 4를 KL 식의 네 항에 넣은 표입니다.", "content": "표의 칸에 1, log σ² 1.3863, μ² 1, σ² 4를 적고, 괄호 안 합 −2.6137과 KL 항 1.3069를 아래에 적었습니다."}}, {"level": 20, "text": "KL 항 코드는 torch.sum에 축을 주지 않아 배치의 모든 데이터와 모든 잠재 차원을 더합니다.", "code": "mean = torch.tensor([[1.0, 0.0], [1.0, 0.0]])\nlog_var = torch.tensor([[0.0, 1.3863], [0.0, 1.3863]])\nkld = -0.5 * torch.sum(1 + log_var - mean.pow(2) - log_var.exp())", "mistake": "torch.sum이 데이터마다 KL 항을 따로 돌려준다고 보는 착각입니다. 축을 주지 않으면 배치 전체를 더한 숫자 하나가 나옵니다.", "q": "이 코드에서 mean의 첫 행을 [2.0, 0.0]으로 바꾸면 kld는 소수 넷째 자리까지 ____ 입니다.", "answer": ["4.1137"], "mode": "number", "places": 4, "why": "torch.sum은 칸 넷의 괄호 안 값을 모두 더합니다. 첫 데이터의 μ = 2, log σ² = 0인 칸은 괄호 안이 1 + 0 − 4 − 1 = −4입니다. 둘째 데이터의 μ = 1, log σ² = 0인 칸은 1 + 0 − 1 − 1 = −1입니다. μ = 0, log σ² = 1.3863인 두 칸은 σ²가 4라 괄호 안이 1 + 1.3863 − 0 − 4 = −1.6137입니다. 칸 넷을 더하면 −4 − 1.6137 − 1 − 1.6137 = −8.2274입니다. 여기에 −0.5를 곱하면 4.1137이 됩니다.", "figure": {"file": "assets/a7f-33.png", "caption": "데이터 두 개, 잠재 차원 두 개의 괄호 안 값을 칸마다 적고 torch.sum이 모두 더하는 모습입니다.", "content": "2행 2열 표에 괄호 안 값 −1, −1.6137, −1, −1.6137을 적고, 표 전체를 감싼 괄호 옆에 torch.sum이 네 칸을 더해 숫자 하나를 낸다고 적었습니다."}}]}
```


### 에폭 평균 손실을 데이터 수로 나누기
<!-- facts: FA07-f3 -->

3단계까지 배치 하나의 손실을 이루는 두 항을 구했습니다. VAE 손실은 복원 항과 KL 항을 더한 값이고, 두 항 모두 배치 안의 값을 더했습니다. 에폭마다 손실을 모아 평균을 낼 때는 모은 값을 데이터 수로 나눕니다.

아래 코드의 model은 다섯째 단원의 Encoder로 mean과 log_var를 내고, sample_z로 z를 뽑고, Decoder로 x_hat을 냅니다. 그래서 `model(x)`는 x_hat, mean, log_var 셋을 돌려줍니다.

```python
for epoch in range(epochs):
    total = 0.0
    for batch_idx, (x, _) in enumerate(train_loader):   # 배치 100, 600번
        x = x.view(-1, 784)
        x_hat, mean, log_var = model(x)
        recon = F.binary_cross_entropy(x_hat, x, reduction='sum')
        kld = -0.5 * torch.sum(1 + log_var - mean.pow(2) - log_var.exp())
        loss = recon + kld
        optimizer.zero_grad()
        loss.backward()                         # 인코더와 디코더의 grad 가 함께 채워짐
        optimizer.step()
        total += loss.item()
    print(epoch + 1, total / len(train_loader.dataset))   # 사진 한 장당 손실
```

MNIST 학습 데이터는 60,000장이고 배치는 100장이라 한 에폭에 배치가 600번 나옵니다. enumerate가 batch_idx를 0부터 세서 마지막 batch_idx는 599입니다. `len(train_loader.dataset)`은 60,000이라, total을 이 값으로 나누면 사진 한 장당 손실이 됩니다.

평균을 `total / (batch_idx * batch_size)`로 구하면 반복이 끝난 뒤의 batch_idx 599를 씁니다. 나누는 수가 599 × 100 = 59,900이라 60,000보다 100 작습니다. 60,000 ÷ 59,900 = 1.00167이라 평균이 0.167% 크게 나옵니다.

```figure
파일: assets/a7f-3.png
캡션: 그림 23. batch_idx 0부터 599까지 배치 600개가 사진 60,000장을 덮고, 599 × 100 = 59,900은 마지막 배치 100장을 빼고 셉니다.
내용: 가로 막대를 600칸으로 나누고 칸 아래에 batch_idx 0, 1, …, 599를 적었습니다. 막대 끝에 60,000을, 마지막 칸 앞에 59,900을 표시하고 그 사이 100장을 주황으로 칠했습니다.
```
```ai-recall
{"id": "r3", "q": "60,000장을 배치 200으로 나눠 학습하면 마지막 batch_idx는 ____ 입니다.", "answer": ["299"], "mode": "number"}
```
```ai-why
{"q": "에폭에 모은 loss.item()을 데이터 수 60,000으로 나누면 사진 한 장당 손실이 되는 까닭은 무엇일까요?", "a": "복원 항과 KL 항이 모두 배치 안의 사진 100장 값을 더한 합입니다. 배치 600번의 합을 모으면 사진 60,000장의 합이 되고, 60,000으로 나누면 한 장당 값이 됩니다."}
```


### VAE 손실과 GAN 손실을 읽는 법 비교하기
<!-- facts: FA07-a6 FA07-f4 FA07-f5 -->

4단계 코드는 복원 항과 KL 항을 더해 loss를 만들었습니다. 2단계의 픽셀 셋 복원 항은 0.4339였습니다. 3단계에서 (μ, log σ²)가 (1, 0), (0, ln 4)인 두 차원의 KL 항은 1.3069였습니다. 둘을 더하면 0.4339 + 1.3069 = 1.7408입니다. 옵티마이저는 이 loss를 줄이도록 인코더와 디코더를 함께 갱신합니다. 그래서 학습이 잘 되면 이 손실이 에폭마다 줄어듭니다.

GAN은 손실이 둘이고 두 신경망이 서로 반대 방향을 노립니다. 판별기는 진짜와 가짜를 가려내려 하고 생성기는 판별기를 속이려 합니다. 생성기가 만든 사진의 분포가 진짜 사진의 분포와 같아지면 판별기는 모든 입력에 0.5를 냅니다. 이때 생성기 손실은 첫 단원 5단계에서 구한 −ln 0.5 = 0.6931이고, 판별기 손실은 진짜와 가짜 두 BCE를 더한 1.3863입니다. 그래서 GAN의 두 손실은 0으로 줄지 않고 이 값 근처에 머뭅니다.

GAN 원 논문은 판별기를 갱신하지 않고 생성기만 너무 많이 학습하면, 서로 다른 노이즈 여럿을 넣어도 생성기가 같은 사진 하나를 만든다고 경고합니다. 이러면 만든 사진의 다양성이 줄어듭니다.

VAE에서는 만든 사진이 흐릿해지기 쉽습니다. 디코더가 받는 z는 인코더가 사진마다 정한 정규분포에서 뽑습니다. 정규분포는 가운데에서 먼 값도 뽑힐 수 있어서, 서로 다른 두 사진의 정규분포는 겹치는 부분이 있습니다. 3단계에서 본 것처럼 KL 항은 μ를 0 쪽으로 당깁니다. 그러면 사진마다 정한 정규분포의 가운데가 서로 가까워져 겹치는 부분이 커집니다. 그래서 학습하는 동안 거의 같은 z가 서로 다른 사진의 정규분포에서 뽑혀 디코더에 들어옵니다.

VAE의 복원 항은 2단계처럼 픽셀마다 BCE를 구해 더한 손실입니다. 디코더가 거의 같은 z를 받았을 때 맞춰야 할 정답 사진이 여러 장일 수 있습니다. 이때 복원 항을 가장 작게 하는 디코더 출력은 그 정답 사진들을 픽셀마다 평균한 사진입니다.

픽셀 하나로 따라가 봅니다. 맞춰야 할 정답 사진이 넷이고, 이 픽셀 값이 1인 사진이 하나, 0인 사진이 셋이라고 해 봅니다. 네 사진의 이 픽셀 값을 평균하면 0.25입니다.

- 디코더가 이 픽셀에 0.25를 내면 네 사진의 BCE 합은 −ln 0.25 − 3 × ln 0.75입니다. 이 값은 2.2493입니다.
- 0.5를 내면 BCE 합은 −4 × ln 0.5입니다. 이 값은 2.7726입니다.
- 0.1을 내면 BCE 합은 −ln 0.1 − 3 × ln 0.9입니다. 이 값은 2.6187입니다.

0과 1 사이에서 0.25가 아닌 값을 내면 BCE 합은 2.2493보다 커집니다. 그래서 학습하는 동안 디코더 출력은 픽셀마다 정답 사진들의 평균 쪽으로 바뀝니다. 서로 다른 사진을 평균하면 흐릿해집니다.

```figure
파일: assets/a7f-4.png
캡션: 그림 24. 왼쪽은 복원 항 0.4339와 KL 항 1.3069를 쌓은 VAE 손실 1.7408이고, 오른쪽은 균형에서 GAN 생성기 손실 0.6931과 판별기 손실 1.3863입니다.
내용: 왼쪽 막대는 아래 파랑 복원 항 0.4339, 위 주황 KL 항 1.3069이고 꼭대기에 1.7408을 적었습니다. 오른쪽에는 막대 두 개에 생성기 0.6931, 판별기 1.3863을 적고 균형에서 판별기 출력은 0.5라고 적었습니다.
```
```ai-recall
{"id": "r4", "q": "복원 항이 0.4339이고 KL 항이 0.5이면 VAE 손실은 ____ 입니다.", "answer": ["0.9339"], "mode": "number"}
```
```ai-why
{"q": "GAN 학습에서 생성기 손실이 0에 가까워지지 않고 0.6931 근처에 머무는 까닭은 무엇일까요?", "a": "생성기가 진짜와 같은 분포를 만들면 판별기는 진짜와 가짜를 가리지 못해 모든 입력에 0.5를 냅니다. 생성기 손실은 정답 1에 대한 BCE라 −ln 0.5 = 0.6931이 됩니다."}
```


### 외울 것
<!-- facts: FA07-f1 FA07-f2 FA07-f3 FA07-a6 -->

```ai-memo
[{"q": "VAE 손실의 두 항은 무엇인가요?", "a": "784개 픽셀의 BCE를 더한 복원 항과, N(μ, σ²)가 N(0, 1)과 다른 정도를 재는 KL 항입니다. 복원 항은 reduction='sum'으로 더합니다.", "cards": ["a07-b23"]}, {"q": "KL 항의 식은 무엇인가요?", "a": "−0.5 × Σ(1 + log σ² − μ² − σ²)입니다. (μ, log σ²) = (1, 0)이면 0.5, (0, ln 4)이면 0.8069입니다.", "cards": ["a07-b21", "a07-b24"]}, {"q": "VAE 데이터에 Normalize([0.5], [0.5])를 쓰지 않는 까닭은 무엇인가요?", "a": "BCE의 정답은 0과 1 사이여야 합니다. Normalize([0.5], [0.5])는 픽셀 0을 −1로 바꿔 오류를 냅니다.", "cards": ["a07-c11"]}, {"q": "에폭 평균 손실은 무엇으로 나누나요?", "a": "len(train_loader.dataset) = 60,000으로 나눕니다. batch_idx × batch_size는 599 × 100 = 59,900이라 평균이 커집니다.", "cards": ["a07-b22"]}, {"q": "균형에 이른 GAN의 손실은 어디에 머무나요?", "a": "판별기가 모든 입력에 0.5를 내서 생성기 손실은 0.6931, 판별기 손실은 1.3863 근처에 머뭅니다.", "cards": ["a07-c12"]}]
```


## U-Net 건너뛰기 연결과 pix2pix 판별기 입력


### 먼저 풀어 보기
<!-- facts: FA07-g1 -->

```ai-guess
{"id": "g1", "q": "(1, 512, 32, 32) 특징 맵을 전치 합성곱으로 (1, 256, 64, 64)로 키웠습니다. 이 결과를 인코더 쪽 특징 맵 (1, 256, 64, 64)와 채널 축으로 이어 붙이면 채널은 몇 개일까요?", "options": ["256", "512", "768"], "answer": 1, "reveal_step": 2, "cards": ["a07-b25"]}
```


### 전치 합성곱으로 키우고 건너뛰기 특징 맵과 이어 붙이기
<!-- facts: FA07-g1 FA07-g3 FA07-c4 -->

U-Net은 사진을 받아 입력 사진과 가로세로가 같은 출력을 내는 신경망입니다. U-Net의 앞쪽 절반도 인코더라고 부릅니다. 이 인코더는 다섯째 단원의 VAE 인코더와 달리 평균과 로그 분산을 내지 않고 특징 맵을 냅니다. U-Net 인코더의 블록은 DoubleConv를 씁니다. DoubleConv는 padding 1인 3×3 합성곱을 두 번 지나는 블록입니다. 인코더의 첫 블록은 DoubleConv로 3채널 입력을 64채널로 바꾸고 가로세로는 그대로 둡니다. 다음 블록 넷은 최대 풀링으로 가로세로를 반으로 줄인 뒤, DoubleConv로 채널을 두 배로 늘립니다. 이 인코더의 최대 풀링은 2 × 2 칸마다 가장 큰 값 하나만 남깁니다. 그래서 3채널 256 × 256 입력은 64, 128, 256, 512, 1024채널을 거치며 16 × 16까지 줄어듭니다. 뒤쪽 절반인 디코더는 가로세로를 두 배로 키우며 다시 256 × 256으로 돌아갑니다.

디코더의 블록 하나를 Up이라고 부릅니다. Up은 두 입력을 받습니다. x1은 Up 바로 앞의 블록이 낸 특징 맵입니다. x2는 인코더가 낸 특징 맵 가운데 가로세로가 x1의 두 배인 특징 맵입니다. 인코더의 특징 맵을 디코더로 바로 넘기는 이 길을 건너뛰기 연결(skip connection)이라고 부릅니다.

```python
class Up(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, kernel_size=2, stride=2)
        self.conv = DoubleConv(in_ch, out_ch)   # 3×3 합성곱 두 번, padding 1

    def forward(self, x1, x2):
        x1 = self.up(x1)                   # (1, 512, 32, 32) → (1, 256, 64, 64)
        x = torch.cat([x2, x1], dim=1)     # (1, 512, 64, 64)
        return self.conv(x)                # (1, 256, 64, 64)
```

Up(512, 256)에 x1 (1, 512, 32, 32)와 x2 (1, 256, 64, 64)를 넣어 따라갑니다. 이 x1은 바로 앞의 Up(1024, 512) 블록이 낸 특징 맵입니다. 이 블록은 인코더 끝의 1024채널 16 × 16 특징 맵을 32 × 32로 키우고 채널을 512로 줄였습니다. `nn.ConvTranspose2d(512, 256, kernel_size=2, stride=2)`는 전치 합성곱입니다. kernel_size 2, stride 2이면 입력 한 칸이 출력 2 × 2칸이 됩니다. 셋째 단원 5단계의 출력 가로세로 식에 32를 넣어 봅니다. 이 층은 padding을 적지 않아 기본값 0을 씁니다. 출력 가로세로는 (32 − 1) × 2 − 2 × 0 + 2 = 64입니다. 그래서 32 × 32가 64 × 64가 되고 채널은 512에서 절반인 256이 됩니다.

`torch.cat([x2, x1], dim=1)`은 두 특징 맵을 1번 축으로 이어 붙입니다. 1번 축은 채널 축이라 256 + 256 = 512채널이 됩니다. 가로세로는 둘 다 64라 이어 붙인 뒤에도 64 × 64입니다. 마지막 DoubleConv(512, 256)이 채널을 256으로 줄입니다.

인코더와 디코더의 DoubleConv는 모두 padding 1인 3×3 합성곱이라 가로세로를 바꾸지 않습니다. 가로세로는 인코더에서는 최대 풀링에서만 반이 되고, 디코더에서는 전치 합성곱에서만 두 배가 됩니다. 그래서 x2와 커진 x1의 크기가 64 × 64로 같습니다. 원래 U-Net 논문은 padding 없는 합성곱을 썼습니다. 3×3 합성곱마다 한 변의 길이가 2씩 줄어서 572 × 572 입력이 388 × 388 출력이 되었습니다. 이 구조에서는 이어 붙일 두 특징 맵의 크기가 다릅니다. 논문 인코더의 첫 블록이 낸 특징 맵은 568 × 568입니다. 이 특징 맵과 이어 붙일 디코더 쪽 특징 맵은 두 배로 키운 뒤에도 392 × 392입니다. 그래서 논문은 인코더 쪽 특징 맵을 392 × 392로 잘라서 이어 붙였습니다.

```ai-code-help
{"title": "채널 축으로 이어 붙이기", "explanation": "torch.cat에 dim=1을 주면 배치, 높이, 너비가 같은 두 특징 맵이 채널 축으로 이어지고 채널 수끼리 더해집니다.", "reference": {"course": "intro", "lesson": "l13", "unit": "13f", "step": 3, "title": "갈래의 공간을 맞춘 뒤 채널 이어 붙이기"}}
```

```figure
파일: assets/a7g-1.gif
캡션: 그림 25. U-Net 인코더가 256 × 256을 16 × 16으로 줄이고, 디코더가 다시 키우며 같은 크기의 인코더 특징 맵을 이어 붙입니다.
내용: 왼쪽 위에서 아래로 인코더 특징 맵이 64, 128, 256, 512, 1024채널로 줄어들고, 오른쪽 아래에서 위로 디코더 특징 맵이 커집니다. 같은 높이에 놓인 두 특징 맵 사이를 가로 화살표로 잇고 채널 수를 더한 값을 적었습니다.
프레임:
1. 인코더가 3채널 256 × 256 입력을 64, 128, 256, 512, 1024채널로 바꾸며 16 × 16까지 줄입니다. (2400ms)
2. Up(1024, 512) 블록이 16 × 16 특징 맵을 키워 (1, 512, 32, 32)를 내고, Up(512, 256)의 전치 합성곱이 이 특징 맵을 (1, 256, 64, 64)로 키웁니다. (2200ms)
3. 같은 64 × 64인 인코더 특징 맵 256채널을 이어 붙여 512채널이 됩니다. (2200ms)
4. DoubleConv가 512채널을 256채널로 줄이고, 다음 Up이 같은 일을 되풀이해 256 × 256까지 돌아갑니다. (2400ms)
```
```ai-reveal
{"guess": "g1"}
```
```ai-recall
{"id": "r1", "q": "Up(256, 128)에 x1 (1, 256, 64, 64)와 x2 (1, 128, 128, 128)을 넣으면 이어 붙인 뒤 모양은 ____ 입니다.", "answer": ["(1, 256, 128, 128)"], "mode": "shape"}
```
```ai-why
{"q": "torch.cat([x2, x1], dim=1)에서 두 특징 맵의 가로세로가 같아야 하는 까닭은 무엇일까요?", "a": "dim=1로 이으면 채널 축만 길어지고 나머지 축은 그대로 둡니다. 그래서 배치, 높이, 너비가 다르면 이어 붙일 수 없습니다. Up은 전치 합성곱으로 x1을 x2와 같은 64 × 64로 먼저 키웁니다."}
```


### 출력층을 바꿔 pix2pix 생성기로 쓰기
<!-- facts: FA07-g1 FA07-g2 -->

2단계의 Up을 넷 쌓은 U-Net은 마지막에 64채널 특징 맵을 1×1 합성곱 `nn.Conv2d(64, 2, kernel_size=1)`에 넣습니다. 출력은 픽셀마다 그 픽셀이 배경인지 물체인지 가르는 두 클래스의 점수입니다. 이 U-Net 전체의 파라미터는 31,037,698개입니다.

1×1 합성곱의 파라미터는 출력 채널마다 입력 64채널의 가중치 64개와 편향 1개입니다. 출력이 2채널이면 64 × 2 + 2 = 130개가 됩니다.

pix2pix는 입력 사진 x를 받아 x와 짝이 되는 사진을 만드는 GAN입니다. 스케치를 받아 사진을 만드는 일이 한 예입니다. 이 U-Net을 pix2pix 생성기로 쓰려면 픽셀마다 두 클래스의 점수 대신 컬러 사진을 내야 합니다. 출력층을 `nn.Conv2d(64, 3, kernel_size=1)`과 Tanh로 바꾸면 이 층의 파라미터는 64 × 3 + 3 = 195개입니다. 차이는 195 − 130 = 65개라서 전체는 31,037,763개가 됩니다. Tanh는 출력을 −1~1로 맞춥니다. 그래서 출력을 −1~1로 정규화한 컬러 사진으로 읽습니다.

위처럼 출력층만 바꾼 U-Net은 3채널 256 × 256 사진을 냅니다. pix2pix 논문의 생성기는 이 U-Net과 구조가 다릅니다. 인코더가 4×4, stride 2 합성곱 여덟 층이고 채널은 64, 128, 256, 512, 512, 512, 512, 512입니다. 첫 64채널 층에는 배치 정규화를 두지 않습니다.

```figure
파일: assets/a7g-2.png
캡션: 그림 26. 1×1 합성곱 출력층의 파라미터는 2채널일 때 130개, 3채널일 때 195개입니다.
내용: 64채널 특징 맵에서 출력으로 가는 1×1 합성곱을 두 줄로 그렸습니다. 윗줄은 출력 2채널과 64 × 2 + 2 = 130, 아랫줄은 출력 3채널과 Tanh, 64 × 3 + 3 = 195입니다. 오른쪽에 전체 31,037,698과 31,037,763을 적었습니다.
```
```ai-recall
{"id": "r2", "q": "출력층을 nn.Conv2d(64, 5, kernel_size=1)로 바꾸면 이 층의 파라미터는 ____ 개입니다.", "answer": ["325"], "mode": "number"}
```
```ai-why
{"q": "출력 채널을 2에서 3으로 하나 늘렸을 때 파라미터가 65개 늘어나는 까닭은 무엇일까요?", "a": "1×1 합성곱의 출력 채널 하나는 입력 64채널마다 가중치 하나와 편향 하나를 씁니다. 그래서 출력 채널이 하나 늘면 64 + 1 = 65개가 늘어나고, 나머지 층의 파라미터는 바뀌지 않습니다."}
```


### pix2pix 판별기에 입력 사진과 결과 사진을 쌍으로 넣기
<!-- facts: FA07-g2 -->

3단계의 pix2pix 생성기는 입력 사진 x로 결과 사진 G(x)를 만듭니다. pix2pix 판별기는 결과 사진만 받지 않습니다. 입력 사진 x와 진짜 결과 y를 채널 축으로 이어 붙인 쌍 (x, y)를 받거나, x와 생성 결과 G(x)를 이어 붙인 쌍 (x, G(x))를 받습니다. x와 y가 모두 3채널이면 판별기 첫 층은 3 + 3 = 6채널을 받습니다.

사진의 작은 정사각형 영역을 패치라고 부릅니다. pix2pix 판별기는 사진 전체에 숫자 하나를 내지 않고 여러 자리의 패치마다 진짜인지 판정합니다. 이런 판별기를 PatchGAN이라고 부릅니다. 판별기 출력은 패치마다 판정한 값을 모은 지도이고, 손실에는 이 지도의 평균을 씁니다. 논문은 패치 크기를 따로 적은 실험을 빼고는 모두 70 × 70 패치를 씁니다. 이 판별기에 256 × 256 쌍을 넣으면 출력은 30 × 30 판정 지도입니다. 지도의 칸 하나가 입력의 70 × 70 영역 하나를 판정하고, 이웃한 칸이 보는 영역은 서로 겹칩니다.

G(x)와 y의 픽셀 차이를 절댓값으로 잰 손실을 L1 손실이라고 부릅니다. 생성기 손실은 판별기를 속이는 GAN 손실에 L1 손실을 λ배 해서 더한 값입니다. 논문은 λ = 100을 씁니다.

```figure
파일: assets/a7g-3.png
캡션: 그림 27. 판별기는 (x, y) 쌍이나 (x, G(x)) 쌍을 6채널로 받아 30 × 30 판정 지도를 냅니다. 손실에는 이 지도의 평균을 씁니다.
내용: 윗줄은 입력 사진 x 3채널과 진짜 y 3채널을 이어 붙인 6채널 입력, 아랫줄은 x와 G(x)를 이어 붙인 6채널 입력입니다. 두 입력이 판별기를 지나 30 × 30 격자가 되고, 격자 칸 하나가 입력의 70 × 70 영역을 본다고 점선으로 표시했습니다.
```
```ai-recall
{"id": "r3", "q": "입력 사진 x가 1채널 흑백이고 결과 y가 3채널 컬러이면 판별기 첫 층이 받는 채널은 ____ 개입니다.", "answer": ["4"], "mode": "number"}
```
```ai-why
{"q": "pix2pix 판별기가 결과 사진만 받지 않고 입력 사진 x를 함께 받는 까닭은 무엇일까요?", "a": "결과 사진만 보면 진짜처럼 보이는지만 판정할 수 있습니다. x를 함께 받으면 그 결과가 입력 사진 x와 짝이 맞는지도 판정합니다. 그래서 생성기는 x에 맞는 결과를 만들어야 판별기를 속입니다."}
```


### 외울 것
<!-- facts: FA07-g1 FA07-g2 -->

```ai-memo
[{"q": "U-Net의 Up 블록은 어떤 순서로 계산하나요?", "a": "전치 합성곱으로 x1의 가로세로를 두 배로 키우고 채널을 절반으로 줄입니다. 그다음 torch.cat([x2, x1], dim=1)로 건너뛰기 특징 맵과 이어 붙이고 DoubleConv를 지납니다.", "cards": ["a07-b25", "a07-b27"]}, {"q": "U-Net 출력층을 64 → 2에서 64 → 3으로 바꾸면 파라미터는 얼마나 늘어나나요?", "a": "1×1 합성곱이 130개에서 195개가 되어 65개 늘어납니다. 전체는 31,037,698개에서 31,037,763개가 됩니다.", "cards": ["a07-b26"]}, {"q": "pix2pix 판별기는 무엇을 받나요?", "a": "입력 사진 x와 진짜 y의 쌍, 또는 x와 생성 결과 G(x)의 쌍을 채널 축으로 이어 붙여 받습니다.", "cards": ["a07-c13"]}, {"q": "PatchGAN은 어떻게 판정하나요?", "a": "패치마다 진짜인지 판정해 판정 지도를 냅니다. 손실을 구할 때는 판정 지도의 칸마다 나온 값을 평균합니다. 논문은 70 × 70 패치를 쓰고, 256 × 256 쌍이면 30 × 30 판정 지도가 나옵니다.", "cards": ["a07-c14"]}]
```
