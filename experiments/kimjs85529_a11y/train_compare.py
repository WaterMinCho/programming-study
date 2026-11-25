import copy
import csv
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt

from learning_server.input_example import load, batch
from learning_server.score import render, score_validation
from experiments.michae18.model import SmallLSTM
from experiments.kimjs85529_a11y.inspect_gaps import get_device, set_seed
from experiments.kimjs85529_a11y.model import (
    TimeGapLSTM, make_model_inputs, copy_baseline_weights,
    DATASET_PATH, TRACK, HISTORY_LENGTH, SEED
)

LR = 0.001
NUM_EPOCH = 500
WEIGHT_DECAY = 1e-3
PATIENCE = 20
OUTPUT_DIR = Path(__file__).resolve().parent / 'comparison_results'


def load_data(split, vocabulary, device):
    rows, current_vocabulary = load(str(DATASET_PATH), TRACK, split)
    if current_vocabulary != vocabulary:
        raise ValueError(f'{split} Vocabulary가 Train과 일치하지 않습니다.')

    # 팀원의 train.py와 동일하게 분할 전체를 Full Batch로 변환
    data = batch(rows, vocabulary, length=HISTORY_LENGTH)
    inputs = make_model_inputs(data['inputs'], device)
    targets = torch.as_tensor(data['targets'], dtype=torch.float32, device=device)

    # 공식 검증 채점에 사용할 풀이 기록 ID
    event_ids = data['event_ids']

    return inputs, targets, len(rows), event_ids


def evaluate(model, inputs, targets, criterion):
    model.eval()
    with torch.no_grad():
        logits = model(inputs)
        loss = criterion(logits, targets).item()
        predicted = (torch.sigmoid(logits) >= 0.5).float()
        accuracy = (predicted == targets).float().mean().item()
    return loss, accuracy


def train_model(model, train_inputs, train_targets, val_inputs, val_targets, lr, num_epoch, name):
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=WEIGHT_DECAY)

    history = []
    best_val_loss = float('inf')
    best_epoch = 0
    patience = PATIENCE
    counter = 0
    best_model_state = None

    for epoch in range(num_epoch):
        model.train()
        optimizer.zero_grad()
        logits = model(train_inputs)
        loss = criterion(logits, train_targets)
        loss.backward()
        optimizer.step()

        train_loss, train_acc = evaluate(model, train_inputs, train_targets, criterion)
        val_loss, val_acc = evaluate(model, val_inputs, val_targets, criterion)

        history.append({
            'epoch': epoch + 1,
            'train_loss': train_loss,
            'train_acc': train_acc,
            'val_loss': val_loss,
            'val_acc': val_acc,
        })

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch + 1
            best_model_state = copy.deepcopy(model.state_dict())
            counter = 0
        else:
            counter += 1

        if epoch % 100 == 0:
            print(
                f'{name} epoch: {epoch} | train_loss: {train_loss:.4f} | '
                f'val_loss: {val_loss:.4f} | train_acc: {train_acc:.4f} | val_acc: {val_acc:.4f}'
            )

        if counter >= patience:
            print(f'{name} early stopping at epoch {epoch + 1}')
            break

    if best_model_state is not None:
        model.load_state_dict(best_model_state)

    return model, history, best_epoch, best_val_loss


def save_results(name, model, history):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), OUTPUT_DIR / f'{name}_best.pt')
    with (OUTPUT_DIR / f'{name}_history.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(
            f, fieldnames=['epoch', 'train_loss', 'train_acc', 'val_loss', 'val_acc']
        )
        writer.writeheader()
        writer.writerows(history)


def score_model_validation(model, inputs, targets, event_ids, model_name):
    # Dropout 비활성화 및 최적 모델의 Validation 정답 확률 계산
    model.eval()

    with torch.no_grad():
        logits = model(inputs)
        probabilities = torch.sigmoid(logits).cpu().tolist()

    # 풀이 기록 ID, 예측 확률, 실제 정답의 개수 확인
    if not (
        len(probabilities) == len(event_ids) == len(targets)
    ):
        raise ValueError('Validation 예측 확률, event_id, 정답 개수가 일치하지 않습니다.')

    # 공통 검증 채점 모듈을 사용하여 공식 채점 및 결과 저장
    result, run_dir = score_validation(
        dataset_path=DATASET_PATH,
        track=TRACK,
        event_ids=event_ids,
        probabilities=probabilities,
        model_name=model_name,
    )

    print(f'\n===== {model_name} 공식 Validation 채점 =====')
    print(render(result))
    print(f'검증 결과 저장: {run_dir}')

    return result, run_dir


def main():
    set_seed(SEED)
    device = get_device()
    print('사용 장치:', device)
    print('데이터:', DATASET_PATH)

    train_rows, vocabulary = load(str(DATASET_PATH), TRACK, 'train')

    # 두 모델에 동일한 Train·Validation Tensor 사용
    train_data = batch(train_rows, vocabulary, length=HISTORY_LENGTH)
    train_inputs = make_model_inputs(train_data['inputs'], device)
    train_targets = torch.as_tensor(train_data['targets'], dtype=torch.float32, device=device)

    validation_inputs, validation_targets, validation_count, validation_event_ids = load_data(
        'validation', vocabulary, device
    )

    print('Train:', len(train_rows), 'Validation:', validation_count)
    print('Batch: Full Batch, Seed:', SEED, 'Learning Rate:', LR)

    num_questions = len(vocabulary['questions'])
    num_concepts = len(vocabulary['concepts'])

    baseline = SmallLSTM(num_questions, num_concepts).to(device)
    timegap = TimeGapLSTM(num_questions, num_concepts).to(device)
    copy_baseline_weights(baseline, timegap)

    # 추가 시간 가중치 0일 때 동일한 초기 예측값인지 확인
    baseline.eval()
    timegap.eval()
    with torch.no_grad():
        torch.testing.assert_close(
            baseline(train_inputs), timegap(train_inputs), rtol=1e-6, atol=1e-6
        )

    print('SmallLSTM 파라미터:', sum(p.numel() for p in baseline.parameters()))
    print('TimeGapLSTM 파라미터:', sum(p.numel() for p in timegap.parameters()))

    set_seed(SEED)
    baseline, baseline_history, baseline_epoch, baseline_loss = train_model(
        baseline, train_inputs, train_targets,
        validation_inputs, validation_targets, LR, NUM_EPOCH, 'SmallLSTM'
    )

    set_seed(SEED)
    timegap, timegap_history, timegap_epoch, timegap_loss = train_model(
        timegap, train_inputs, train_targets,
        validation_inputs, validation_targets, LR, NUM_EPOCH, 'TimeGapLSTM'
    )

    save_results('SmallLSTM', baseline, baseline_history)
    save_results('TimeGapLSTM', timegap, timegap_history)

    print('\n===== 최적 Validation 결과 =====')
    for name, model, epoch in (
        ('SmallLSTM', baseline, baseline_epoch),
        ('TimeGapLSTM', timegap, timegap_epoch),
    ):
        train_loss, train_acc = evaluate(
            model, train_inputs, train_targets, nn.BCEWithLogitsLoss()
        )
        val_loss, val_acc = evaluate(
            model, validation_inputs, validation_targets, nn.BCEWithLogitsLoss()
        )
        print(
            f'{name}: best_epoch={epoch}, train_loss={train_loss:.6f}, '
            f'train_acc={train_acc:.6f}, val_loss={val_loss:.6f}, val_acc={val_acc:.6f}'
        )

    plt.figure(figsize=(10, 6))
    plt.plot([row['epoch'] for row in baseline_history],
             [row['val_loss'] for row in baseline_history], label='SmallLSTM Val Loss')
    plt.plot([row['epoch'] for row in timegap_history],
             [row['val_loss'] for row in timegap_history], label='TimeGapLSTM Val Loss')
    plt.title('Full Batch Validation Loss Comparison')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'validation_loss_comparison.png', dpi=150)
    plt.close()

    print('결과 저장 위치:', OUTPUT_DIR)
    print('Test는 모델 선택에 사용하지 않았습니다.')

    # 재학습 SmallLSTM 공식 Validation 채점
    score_model_validation(
        model=baseline,
        inputs=validation_inputs,
        targets=validation_targets,
        event_ids=validation_event_ids,
        model_name='small-lstm-retrained',
    )

    # TimeGapLSTM 공식 Validation 채점
    score_model_validation(
        model=timegap,
        inputs=validation_inputs,
        targets=validation_targets,
        event_ids=validation_event_ids,
        model_name='timegap-lstm',
    )

    print('\n===== 공통 Validation 채점 완료 =====')
    print('Validation은 최적 Epoch 선택에 사용한 구간이며 독립적인 Test 평가가 아닙니다.')


if __name__ == '__main__':
    main()