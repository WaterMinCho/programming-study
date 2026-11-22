from learning_server.input_example import load, batch
from experiments.michae18.model import SmallLSTM
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
import copy
from experiments.michae18.input_check import load_data

print("PyTorch:", torch.__version__)
print("CUDA 사용 가능:", torch.cuda.is_available())
print("PyTorch CUDA 버전:", torch.version.cuda)

def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda") # Google Colab (NVIDIA GPU)
    elif torch.backends.mps.is_available():
        return torch.device("mps")  # MacBook M3 (Apple Silicon GPU)
    else:
        return torch.device("cpu")  # GPU 없을 때

device = get_device()
print(device)

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed)

    return seed

seed = set_seed()
print(seed)

# input_check에서 텐서변화된 데이터들(train, validation, test) 불러오기. vocabulary는 동일하여 _ 처리
train_inputs, train_targets, train_vocabulary = load_data('train')
validation_inputs, validation_targets, _ = load_data('validation')
test_inputs, test_targets, _ = load_data('test')


# vocabulary의 크기로 Embedding 크기 설정 (수정 후)
num_questions = len(train_vocabulary["questions"])
num_concepts = len(train_vocabulary["concepts"])

# 과적합 방지를 위한 수단: early_stopping, weight_decay, dropout, embeding_num, hidden_num 수정
# SmallLSTM 학습 모델 생성
def train_model(
        train_inputs, train_targets, val_inputs, val_targets, lr, num_epoch,
):  
    # train 입력 값 데이터 설정
    train_inputs = {
        key: value.to(device)
        for key, value in train_inputs.items()
    }

    # train 정오답 데이터 설정
    train_targets = train_targets.to(device)

    # validation 입력 값 데이터 설정
    val_inputs = {
        key : value.to(device)
        for key, value in val_inputs.items()
    }

    # validation 정오답 데이터 설정
    val_targets = val_targets.to(device)

    
    # SmallLSTM 불러오기
    model = SmallLSTM(num_questions, num_concepts).to(device) 
    # 데이터 많아진 만큼 embeding_num, hidden_num 수정 필요?

    # 손실 함수 정의
    criterion = nn.BCEWithLogitsLoss()

    # 최적화 정의
    # 가중치 과도한 상승을 막기 위한 weight_decay 비교하기(0, 1e-5, 1e-4,1e-3)
    # 최적화 함수 비교하기(Adam  VS  AdamW)
    optimizer = optim.Adam(model.parameters(), lr = lr, weight_decay= 1e-3)

    # 기록
    history = []

    # early stopping 변수 정의
    # best_val_loss 정의
    best_val_loss = float('inf')
    # best_epoch 초기화
    best_epoch = 0
    # 얼마까지 봐줄래?
    patience = 20
    # loss가 변하지 않은 횟수
    counter = 0
    # best_epoch일 때의 파라미터 값 저장하기
    best_model_state = None

    

    # 학습 시작
    for epoch in range(num_epoch):
        # 학습 한다~
        model.train()
        # 가중치 초기화
        optimizer.zero_grad()
        # train 입력값 넣은 모델의 출력 값 = logit 값
        logits = model(train_inputs)
        # 손실값 정의
        loss = criterion(logits, train_targets)
        # 기울기 계산
        loss.backward()
        # 가중치 업데이트
        optimizer.step()

        # 예측할거야~!
        model.eval()
        # 학습 안한다~!
        with torch.no_grad():
            # 모델의 입력 값으로 train 데이터 넣어 불러오기
            logits = model(train_inputs)
            # 손실값 확인
            train_loss = criterion(logits, train_targets).item()
            # 확률로 변환
            predicted = (torch.sigmoid(logits) >= 0.5).float()
            # 
            train_acc = (
                (predicted == train_targets).float().mean().item()
            )

            # 모델의 입력 값으로 train 데이터 넣어 불러오기
            val_logit = model(val_inputs)
            # loss 값 계산
            val_loss = criterion(val_logit, val_targets).item()

            # early_stopping 구현
            # best_val_loss 보다 적을 때 업데이트
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                # 해당 epoch 저장
                best_epoch = epoch + 1
                # model.state_dict: 모델의 파라미터를 딕셔너리 형태로 변환
                best_model_state = copy.deepcopy(model.state_dict())
                counter = 0
            else:
                # best_val_loss가 변하지 않을 때 횟수 증가
                counter += 1
            
            val_predicted = (torch.sigmoid(val_logit) >= 0.5).float()
    
            val_acc = (val_predicted == val_targets).float().mean().item()
    
            history.append({
                'epoch': epoch + 1,
                'train_loss': train_loss,
                'train_acc': train_acc,
                'val_loss': val_loss,
                'val_acc': val_acc
            })

            # best_val_loss 값이 20번 이상 변화가 없다면 학습 중단
            if counter >= patience:
                print(f'early stopping at epoch {epoch + 1}')
                break

            if epoch % 100 == 0:
                print(f'''epoch: {epoch} | train_loss: {train_loss:.4f} | 
                val_loss: {val_loss:.4f} | train_acc: {train_acc:.4f} | val_acc: {val_acc:.4f}''')

    # best_model_state가 존재한다면 최적의 가중치 뽑기
    if best_model_state is not None:
        best_history = model.load_state_dict(best_model_state)

    return model, history, best_history

model, history, best_history = train_model(
    train_inputs,
    train_targets,
    validation_inputs,
    validation_targets,
    lr=0.001,
    num_epoch=500
)

print(model, history[-1], best_history)

history_name = ['epoch', 'train_loss', 'val_loss', 'train_acc', 'val_acc']
key_name = {name: [record[name] for record in history] for name in history_name}

plt.figure(figsize=(10,6))
plt.subplot(1,2,1)
plt.plot(key_name["epoch"],key_name["train_loss"],label="Train Loss")
plt.plot(key_name["epoch"],key_name["val_loss"],label="validation loss")
plt.title("Train and Validation Loss")
plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.legend()

plt.subplot(1,2,2)
plt.plot(key_name["epoch"],key_name["train_acc"],label="Train acc")
plt.plot(key_name["epoch"],key_name["val_acc"],label="validation acc")
plt.title("Train and Validation acc")
plt.xlabel("Epoch")
plt.ylabel("accuracy")
plt.legend()

plt.tight_layout()
plt.show()