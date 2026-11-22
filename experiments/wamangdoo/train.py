from pathlib import Path

import torch
from torch import nn

from experiments.wamangdoo.model import SmallTransformer
from experiments.wamangdoo.run import get_device, set_seed, to_model_inputs
from learning_server.input_example import batch, load


def train_one_epoch(model, rows, vocabulary, loss_fn, optimizer, device, batch_size=4, length=32):
    # 학습 모드 켜기 (Dropout 활성화)
    model.train()
    total_loss = 0.0

    # 전체 데이터를 batch_size개씩 잘라서 순서대로 학습
    for start in range(0, len(rows), batch_size):
        slice_rows = rows[start : start + batch_size]
        example = batch(slice_rows, vocabulary, length=length)

        # 배치 단위로 텐서를 만들고 한 번에 device로 이동
        inputs = to_model_inputs(example["inputs"])
        inputs = {key: value.to(device) for key, value in inputs.items()}
        # 이번 정답표(targets)는 모델 입력에 넣지 않고 손실 계산에만 사용
        targets = torch.as_tensor(example["targets"], dtype=torch.float32, device=device)

        optimizer.zero_grad()
        logits = model(inputs)
        loss = loss_fn(logits, targets)
        loss.backward()
        optimizer.step()

        # 마지막 배치 크기가 다를 수 있으므로 행 개수를 곱해 누적
        total_loss += float(loss.item()) * len(slice_rows)

    return total_loss / len(rows)


def evaluate_one_epoch(model, rows, vocabulary, loss_fn, device, batch_size=4, length=32):
    # 평가 모드 켜기 (Dropout 끄기)
    model.eval()
    total_loss = 0.0

    # 검증 때는 기울기를 계산하지 않고 가중치도 바꾸지 않음
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            slice_rows = rows[start : start + batch_size]
            example = batch(slice_rows, vocabulary, length=length)

            inputs = to_model_inputs(example["inputs"])
            inputs = {key: value.to(device) for key, value in inputs.items()}
            targets = torch.as_tensor(example["targets"], dtype=torch.float32, device=device)

            logits = model(inputs)
            loss = loss_fn(logits, targets)
            total_loss += float(loss.item()) * len(slice_rows)

    return total_loss / len(rows)


def predict_probabilities(model, rows, vocabulary, device, batch_size=4, length=32):
    # 평가 모드에서 0~1 사이 예측 확률을 계산
    model.eval()
    all_probabilities = []

    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            slice_rows = rows[start : start + batch_size]
            example = batch(slice_rows, vocabulary, length=length)

            inputs = to_model_inputs(example["inputs"])
            inputs = {key: value.to(device) for key, value in inputs.items()}

            logits = model(inputs)
            probabilities = torch.sigmoid(logits)
            all_probabilities.append(probabilities.cpu())

    return torch.cat(all_probabilities, dim=0)


def save_model(path, model, num_questions, num_concepts):
    # 가중치(state_dict)와 모델을 다시 만들 때 필요한 문제 수·개념 수를 함께 저장
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "num_questions": num_questions,
        "num_concepts": num_concepts,
    }
    torch.save(checkpoint, path)


def load_model(path, device=None):
    if device is None:
        device = torch.device("cpu")

    # map_location=device: GPU에서 저장한 파일도 CPU에서 문제없이 불러오기 위함
    checkpoint = torch.load(path, map_location=device)
    model = SmallTransformer(
        num_questions=checkpoint["num_questions"],
        num_concepts=checkpoint["num_concepts"],
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def main():
    set_seed(42)
    device = get_device()

    # 공통 합성 데이터(learning-demo-f8) 불러오기
    dataset_path = Path(__file__).resolve().parents[3] / "learning-demo-f8"
    train_rows, vocabulary = load(str(dataset_path), "python", "train")
    val_rows, _ = load(str(dataset_path), "python", "validation")

    num_questions = len(vocabulary["questions"])
    num_concepts = len(vocabulary["concepts"])

    # 모델이 확률이 아닌 logit을 반환하므로 BCEWithLogitsLoss 사용
    loss_fn = nn.BCEWithLogitsLoss()

    # 1) 소량(최대 32건) 학습 손실이 내려가는지 먼저 확인
    small_rows = train_rows[:32]
    check_model = SmallTransformer(num_questions=num_questions, num_concepts=num_concepts).to(device)
    check_optimizer = torch.optim.Adam(check_model.parameters(), lr=1e-2)

    first_loss = None
    last_loss = None
    for epoch in range(1, 51):
        loss = train_one_epoch(
            check_model,
            small_rows,
            vocabulary,
            loss_fn,
            check_optimizer,
            device,
        )
        if epoch == 1:
            first_loss = loss
        last_loss = loss

    print(f"[1] 소량({len(small_rows)}건) 과적합 확인: epoch 1 손실 {first_loss:.6f} -> epoch 50 손실 {last_loss:.6f}")

    # 2) 전체 학습·검증 루프 실행
    set_seed(42)
    model = SmallTransformer(num_questions=num_questions, num_concepts=num_concepts).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    print(f"\n[2] 학습·검증 시작 (device={device}, train={len(train_rows)}건, validation={len(val_rows)}건)")
    for epoch in range(1, 21):
        train_loss = train_one_epoch(model, train_rows, vocabulary, loss_fn, optimizer, device)
        val_loss = evaluate_one_epoch(model, val_rows, vocabulary, loss_fn, device)
        if epoch in (1, 5, 10, 15, 20):
            print(f"  epoch {epoch:2d} | train_loss: {train_loss:.6f} | val_loss: {val_loss:.6f}")

    # 3) 저장·불러오기 확인 (같은 CPU·평가 모드에서 최대 오차 <= 1e-6 확인)
    cpu_device = torch.device("cpu")
    model_cpu = model.to(cpu_device)
    before_probs = predict_probabilities(model_cpu, val_rows, vocabulary, cpu_device)

    # Git 저장소 밖에 임시로 저장했다가 확인이 끝나면 삭제 (저장소에 .pt 파일 남기지 않기 위함)
    checkpoint_path = Path(__file__).resolve().parents[3] / "temp_small_transformer.pt"
    save_model(checkpoint_path, model_cpu, num_questions, num_concepts)
    loaded_model = load_model(checkpoint_path, device=cpu_device)
    after_probs = predict_probabilities(loaded_model, val_rows, vocabulary, cpu_device)
    checkpoint_path.unlink()

    max_diff = float((before_probs - after_probs).abs().max().item())
    print("\n[3] 저장·불러오기 확인 (CPU, eval 모드)")
    print("  저장 전 예측 확률:", [round(float(p), 6) for p in before_probs])
    print("  불러온 뒤 예측 확률:", [round(float(p), 6) for p in after_probs])
    print(f"  최대 절대 차이: {max_diff:.8f} (기준 <= 0.000001)")


if __name__ == "__main__":
    main()
