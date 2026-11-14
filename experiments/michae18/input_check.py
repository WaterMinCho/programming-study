import numpy as np
import re, math, random, numpy as np
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader
from learning_server.input_example import load, batch

# 라이브러리 임포트 & 시드 고정
SEED = 2026
random.seed(SEED); np.random.seed(SEED), torch.manual_seed(SEED)
# 1. 합성 데이터 로딩
rows, vocabulary = load(
    "../study-data/common-input-f4-20261112/recorded-python",
    "python",
    "train"
)

# rows, vocabulary = load(
#     "../learning-demo-f4",
#     "python",
#     "train"
# )
print('rows의 데이터 확인하기',rows)
# 2. 첫 4개 사례를 배치로 변환
example = batch(rows[:4], vocabulary, length=32)
raw_inputs = example['inputs']
# inputs = example["inputs"]
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
targets = example["targets"]
questions = inputs['questions']

print('inputs의 데이터 확인하기', inputs)
print('\n','*' * 80)
# 3. 입력 구조 확인
print("=== INPUT TYPES ===")
print(type(inputs), type(targets))

# 4. 첫 번째 사례의 입력값 확인
print("\n=== FIRST SAMPLE ===")
print(list(inputs.keys()))

print('\n','*'*40)
for name, value in inputs.items():
    print(f"{name}: {value}")
    print('\n')

# 5. 네 사례의 실제 정답
print("\n=== TARGETS ===")
print(targets)

print('\n ====QUESTIONS====')
print(questions)

