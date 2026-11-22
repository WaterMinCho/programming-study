from pathlib import Path
import random

import numpy as np
import torch
from experiments.wamangdoo.model import SmallTransformer
from learning_server.input_example import batch, load


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")  # Google Colab (NVIDIA GPU)
    elif torch.backends.mps.is_available():
        return torch.device("mps")   # MacBook M3 (Apple Silicon GPU)
    else:
        return torch.device("cpu")   # GPU 없을 때


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed)


def to_model_inputs(raw_inputs):
    return {
        ## torch.tensor()는 호출할 때마다 데이터를 무조건 새로 복사하지만, torch.as_tensor()는 파이썬 리스트를 텐서로 바꾸면서도 이미 같은 형식의 텐서가 들어온 경우에는 불필요한 복사를 줄여 줍니다.
        "questions": torch.as_tensor(raw_inputs["questions"], dtype=torch.long),
        "concepts": torch.as_tensor(raw_inputs["concepts"], dtype=torch.float32),
        "results": torch.as_tensor(raw_inputs["results"], dtype=torch.float32),
        "mask": torch.as_tensor(raw_inputs["mask"], dtype=torch.bool),
        "query_question": torch.as_tensor(raw_inputs["query_question"], dtype=torch.long),
        "query_concepts": torch.as_tensor(raw_inputs["query_concepts"], dtype=torch.float32),
    }


def main():
    set_seed(42)
    device = get_device()
    # (programming-study 밖에서 실행하면 파일을 못 찾음)
    dataset_path = Path(__file__).resolve().parents[3] / "learning-demo-f8"
    rows, vocabulary = load(str(dataset_path), "python", "train")

    num_questions = len(vocabulary["questions"])
    num_concepts = len(vocabulary["concepts"])

    # 모델 생성 후 device로 이동
    model = SmallTransformer(num_questions=num_questions, num_concepts=num_concepts).to(device)

    model.eval()    # Dropout(0.1) 끄기

    # 한 배치만 볼 때보다 다양한 이력 조합에서도 동작함을 보이기 위해 배치 1(rows[:4])과 배치 2(rows[4:8])를 확인함.
    for batch_idx, slice_rows in enumerate((rows[:4], rows[4:8]), start=1):
        if not slice_rows:
            continue
        example = batch(slice_rows, vocabulary, length=32)
        inputs = to_model_inputs(example["inputs"])
        inputs = {key: value.to(device) for key, value in inputs.items()}

        with torch.no_grad():
            logits = model(inputs)
            probabilities = torch.sigmoid(logits)

        print("예측 확률:", [round(float(probability), 6) for probability in probabilities])


if __name__ == "__main__":
    main()
