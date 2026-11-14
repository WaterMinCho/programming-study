import torch
import random, numpy as np
from learning_server.input_example import load, batch

# 라이브러리 임포트 & 시드 고정
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
# 1. 합성 데이터 로딩
DATASET_PATH = "../learning-demo-f4"
rows, vocabulary = load(
    DATASET_PATH,
    "python",
    "train"
)

print("=== DATASET ===")
print("데이터 경로:", DATASET_PATH)
print("데이터 개수:", len(rows))

# 2. 첫 4개 사례를 배치로 변환
example = batch(rows[:4], vocabulary, length=32)
raw_inputs = example['inputs']
targets = example['targets']
inputs = {
    "questions": torch.as_tensor(
        raw_inputs["questions"], dtype=torch.long
    ),
    "concepts": torch.as_tensor(
        raw_inputs["concepts"], dtype=torch.float32
    ),
    "results": torch.as_tensor(
        raw_inputs["results"], dtype=torch.float32
    ),
    "lengths": torch.as_tensor(
        raw_inputs["lengths"], dtype=torch.long
    ),
    "query_question": torch.as_tensor(
        raw_inputs["query_question"], dtype=torch.long
    ),
    "query_concepts": torch.as_tensor(
        raw_inputs["query_concepts"], dtype=torch.float32
    )
}
print("\n=== INPUT SHAPES ===")

for name, value in inputs.items():
    print(f"{name}: {tuple(value.shape)}")

print("\n=== TARGET SHAPE ===")
print(tuple(torch.as_tensor(targets).shape))

print("\n=== VOCABULARY SIZES ===")
print("questions:", len(vocabulary["questions"]))
print("concepts:", len(vocabulary["concepts"]))

