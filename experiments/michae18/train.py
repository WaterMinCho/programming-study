from experiments.michae18.model import SmallLSTM
from experiments.michae18.input_check import load_data
from experiments.michae18.constants import(
    SEED, Trainconfig, Modelconfig
)
from experiments.michae18.evaluate import(
    save_predictions, validate_predictions, run_score
)
from experiments.michae18.constants import DATASET_PATH
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
import copy


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda") # Google Colab (NVIDIA GPU)
    elif torch.backends.mps.is_available():
        return torch.device("mps")  # MacBook M3 (Apple Silicon GPU)
    else:
        return torch.device("cpu")  # GPU 없을 때

def set_seed():
    seed = SEED
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed)

    return seed

# 과적합 방지를 위한 수단: early_stopping, weight_decay, dropout, embeding_num, hidden_num 수정
# SmallLSTM 학습 모델 생성
def train_model(
    train_inputs,
    train_targets,
    val_inputs,
    val_targets,
    num_questions: int,
    num_concepts: int,
    device: torch.device,
    config: Trainconfig,
    model_config: Modelconfig
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
    model = SmallLSTM(num_questions, num_concepts, config = model_config).to(device)
    # 데이터 많아진 만큼 embeding_num, hidden_num 수정 필요?

    # 손실 함수 정의
    criterion = nn.BCEWithLogitsLoss()

    # 최적화 정의
    # 가중치 과도한 상승을 막기 위한 weight_decay 비교하기(0, 1e-5, 1e-4,1e-3)
    # 최적화 함수 비교하기(Adam  VS  AdamW)
    optimizer = optim.Adam(model.parameters(), lr = config.lr, weight_decay = config.weight_decay)

    # 기록
    history = []

    # early stopping 변수 정의
    # best_val_loss 정의
    best_val_loss = float('inf')
    # best_epoch 초기화
    best_epoch = 0
    # 얼마까지 봐줄래?
    patience = config.patience
    # loss가 변하지 않은 횟수
    counter = 0
    # best_epoch일 때의 파라미터 값 저장하기
    best_model_state = None
    best_history = None

    # 상수값 확인하기
    print()
    print("=== Model Config ===")
    print("Embedding Dim:", model.embedding.embedding_dim)
    print("Hidden Size:", model.lstm.hidden_size)
    print("Dropout Rate:", model.dropout.p)

    print("=== Train Config ===")
    print("Learning Rate:", optimizer.param_groups[0]["lr"])
    print("Weight Decay:", optimizer.param_groups[0]["weight_decay"])
    print("Max Epoch:", config.max_epoch)
    print("Patience:", config.patience)
    print("Prediction Threshold:", config.prediction_threshold)
    print()

    # 학습 시작
    for epoch in range(config.max_epoch):
        # 학습 한다~
        model.train()
        # 이전 학습 단계에서 누적된 기울기 초기화
        optimizer.zero_grad()
        # train 입력값 넣은 모델의 출력 값 = logit 값
        logits = model(train_inputs)
        # 손실값 정의
        loss = criterion(logits, train_targets)
        # 기울기 계산
        loss.backward()

        # optimizer 전 
        if epoch == 0:
            weight_before = model.fc.weight.detach().clone()

        # 가중치 업데이트
        optimizer.step()

        # optim 후
        if epoch == 0:
            weight_after = model.fc.weight.detach().clone()

            weight_change = (
                weight_after - weight_before
            ).abs()

            print("=== Optimizer Step Comparison ===")
            print("Before:", weight_before.flatten()[:5])
            print("After :", weight_after.flatten()[:5])
            print("Max weight change:", weight_change.max().item())
            print("Mean weight change:", weight_change.mean().item())
            
        # 예측할거야~!
        model.eval()
        # 학습 안한다~!
        with torch.no_grad():
            # 모델의 입력 값으로 train 데이터 넣어 불러오기
            logits = model(train_inputs)
            # 손실값 확인
            train_loss = criterion(logits, train_targets).item()
            
            # 확률로 변환
            predicted = (torch.sigmoid(logits) >= config.prediction_threshold).float()
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
            
            val_predicted = (torch.sigmoid(val_logit) >= config.prediction_threshold).float()
    
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
                print(f'''epoch: {epoch} | train_loss: {train_loss:.4f} | val_loss: {val_loss:.4f} 
                | train_acc: {train_acc:.4f} | val_acc: {val_acc:.4f} \n''')

    # best_model_state가 존재한다면 최적의 가중치 뽑기
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        best_history = history[best_epoch - 1]

    return model, history, best_history

# eval () 전후 비교 명령
def compare_train_eval(model, inputs, device):
    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    # Train 모드
    model.train()

    with torch.no_grad():
        train_logits = model(inputs)

    # Eval 모드
    model.eval()

    with torch.no_grad():
        eval_logits = model(inputs)

    difference = (
        train_logits - eval_logits
    ).abs()

    print("=== Train vs Eval ===")
    print("Train:", train_logits[:5])
    print("Eval :", eval_logits[:5])
    print("Max difference:", difference.max().item())
    print("Mean difference:", difference.mean().item())

    return train_logits, eval_logits

def predict_probabilities(model, inputs, device):
    model.eval()

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        logits = model(inputs)
        probabilities = torch.sigmoid(logits)
        
    return probabilities.cpu().numpy()

def make_plt(history):
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

def main():

    print("PyTorch:", torch.__version__)
    print("CUDA 사용 가능:", torch.cuda.is_available())
    print("PyTorch CUDA 버전:", torch.version.cuda)

    device = get_device()    
    seed = set_seed()
    print(seed)

    train_config = Trainconfig()
    model_config = Modelconfig()

    # input_check에서 텐서변화된 데이터들(train, validation, test) 불러오기. vocabulary는 동일하여 _ 처리
    train_inputs, train_targets, train_vocabulary = load_data('train')
    val_inputs, val_targets, _, val_event_ids = load_data('validation', return_event_ids=True)
    # test_inputs, test_targets, _ = load_data('test')

    # vocabulary의 크기로 Embedding 크기 설정 (수정 후)
    num_questions = len(train_vocabulary["questions"])
    num_concepts = len(train_vocabulary["concepts"])

    model, history, best_history = train_model(
        train_inputs=train_inputs,
        train_targets=train_targets,
        val_inputs=val_inputs,
        val_targets=val_targets,
        num_questions=num_questions,
        num_concepts=num_concepts,
        device=device,
        config=train_config,
        model_config=model_config
    )

    compare_train_eval(
        model,
        val_inputs,
        device
    )

    # 1. Validation 확률 예측
    probabilities = predict_probabilities(
        model,
        val_inputs,
        device
    )

    assert len(probabilities) == len(val_event_ids)
    assert len(probabilities) == len(val_targets)

    # 2. 파일 경로 설정
    predictions_path = "../preds/lstm-validation.csv"

    # 3. CSV 저장
    save_predictions(
        event_ids=val_event_ids,
        probabilities=probabilities,
        output_path=predictions_path,
        model_version="small-lstm-v1"
    )

    # 4. CSV 검증
    validate_predictions(
        csv_path=predictions_path,
        expected_event_ids=val_event_ids
    )

    # 5. 로컬 채점
    run_score(
        dataset_path=DATASET_PATH,
        predictions_path=predictions_path,
        output_path="../preds/lstm-score-v1.json"
    )


    # print(model, history[-1], best_history)
    print(model, history[-1])
    print(f"Best Epoch : {best_history['epoch']}")
    print(f"Best valid loss : {best_history['val_loss']}")

    print("예측 확률 shape:", probabilities.shape)
    print("예측 확률 상위 5개:", probabilities[:5])
    print("Validation 정답 개수:", len(val_targets))

    print("예측 확률 개수:", len(probabilities))
    print("event_id 개수:", len(val_event_ids))



    make_plt(history)

    return model, history, best_history

if __name__ == "__main__":
    main()