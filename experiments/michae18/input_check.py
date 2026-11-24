import random
import numpy as np
import torch

from learning_server.input_example import load, batch
from experiments.michae18.constants import(
    SEED, DATASET_PATH, SEQUENCE_LENGTH, TRACK
)



# 1. 데이터 정보 출력
def print_data_info(name, inputs, targets, vocabulary):

    print(f"\n=== {name.upper()} DATASET ===")
    print("데이터 경로:", DATASET_PATH)
    print("데이터 개수:", len(targets))

    print("\n=== INPUT SHAPES ===")
    for key, value in inputs.items():
        print(f"{key}: {tuple(value.shape)}")

    print("\n=== TARGET SHAPE ===")
    print(tuple(targets.shape))

    print("\n=== VOCABULARY SIZES ===")
    print("questions:", len(vocabulary["questions"]))
    print("concepts:", len(vocabulary["concepts"]))
    print('\n','*'*40)

# 2. 데이터 Tensor로 변환
def data_to_tensor(data):
    raw = data["inputs"]

    inputs = {
        "questions": torch.as_tensor(
            raw["questions"], dtype=torch.long
        ),
        "concepts": torch.as_tensor(
            raw["concepts"], dtype=torch.float32
        ),
        "results": torch.as_tensor(
            raw["results"], dtype=torch.float32
        ),
        "lengths": torch.as_tensor(
            raw["lengths"], dtype=torch.long
        ),
        "query_question": torch.as_tensor(
            raw["query_question"], dtype=torch.long
        ),
        "query_concepts": torch.as_tensor(
            raw["query_concepts"], dtype=torch.float32
        )
    }

    targets = torch.as_tensor(
        data["targets"], dtype=torch.float32
    )

    return inputs, targets

# 3. 데이터 불러오기
def load_data(split, return_event_ids = False):
    rows, vocabulary  = load(DATASET_PATH, TRACK, split)
    data = batch(rows, vocabulary, length=SEQUENCE_LENGTH)
    # Tensor 변환
    inputs, targets = data_to_tensor(data)

    if return_event_ids:
        return inputs, targets, vocabulary, data['event_ids']

    return inputs, targets, vocabulary

# 4. 전체 실행
def main():

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    datasets = {}

    for split in ("train", "validation", "test"):

        # 원본 데이터 로딩
        inputs, targets, vocabulary = load_data(split)

        #  데이터 정보 출력
        print_data_info(split, inputs, targets, vocabulary)

        # 이후 학습 코드에서 활용할 수 있도록 저장
        datasets[split] = {
            "inputs": inputs,
            "targets": targets,
            "vocabulary": vocabulary
        }

    return datasets


if __name__ == "__main__":
    datasets = main()