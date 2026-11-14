import torch

from learning_server.input_example import load, batch
from experiments.michae18.model import SmallLSTM

torch.manual_seed(2026)

# 데이터 로딩
rows, vocabulary = load("../learning-demo-f4","python","train")
example = batch(rows[:4], vocabulary, length=32)

raw = example["inputs"]
# questions: 이전 문제 번호, concepts: 개념, results : 맞았는 지, lengths: 문제 푼 개수, query_question : 예측할 문제, query_concepts: 그 개념
inputs = { 
    "questions": torch.tensor(raw["questions"], dtype=torch.long),
    "concepts": torch.tensor(raw["concepts"], dtype=torch.float32),
    "results": torch.tensor(raw["results"], dtype=torch.float32),
    "lengths": torch.tensor(raw["lengths"], dtype=torch.long),
    "query_question": torch.tensor(raw["query_question"], dtype=torch.long),
    "query_concepts": torch.tensor(raw["query_concepts"], dtype=torch.float32)
}

# 문제 ID의 최댓값을 이용해 Embedding 크기 설정 (수정 전)
# num_questions = max(
#     inputs["questions"].max().item(),
#     inputs["query_question"].max().item()
# ) + 1
# 개념 수 가져오기
# num_concepts = inputs["query_concepts"].shape[-1]

# 문제 ID의 최댓값을 이용해 Embedding 크기 설정 (수정 후)
num_questions = len(vocabulary["questions"])
# 개념 수 가져오기 (수정 후)
num_concepts = len(vocabulary["concepts"])

# 개념 수 가져오기
num_concepts = inputs["query_concepts"].shape[-1]
# SmallLSTM 모델 생성
model = SmallLSTM(num_questions, num_concepts)

# 예측할거야~!
model.eval()
# 학습 안한다~!
with torch.no_grad():
    probabilities = model(inputs)

print("예측 확률:", probabilities.tolist())
print("예측 개수:", probabilities.numel())

# 두 번째 배치 확인
second_example = batch(rows[4:8], vocabulary, length=32)

second_inputs = {
    "questions": torch.as_tensor(
        second_example["inputs"]["questions"], dtype=torch.long
    ),
    "concepts": torch.as_tensor(
        second_example["inputs"]["concepts"], dtype=torch.float32
    ),
    "results": torch.as_tensor(
        second_example["inputs"]["results"], dtype=torch.float32
    ),
    "lengths": torch.as_tensor(
        second_example["inputs"]["lengths"], dtype=torch.long
    ),
    "query_question": torch.as_tensor(
        second_example["inputs"]["query_question"], dtype=torch.long
    ),
    "query_concepts": torch.as_tensor(
        second_example["inputs"]["query_concepts"], dtype=torch.float32
    ),
}

with torch.no_grad():
    second_probabilities = model(second_inputs)

print("두 번째 배치 예측 개수:", second_probabilities.numel())