import torch

from learning_server.input_example import load, batch
from experiments.michae18.model import SmallLSTM

torch.manual_seed(2026)

# 데이터 로딩
rows, vocabulary = load("../study-data/common-input-f4-20261112/recorded-python", "python", "train")
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

# 문제 ID의 최댓값을 이용해 Embedding 크기 설정
num_questions = max(
    inputs["questions"].max().item(),
    inputs["query_question"].max().item()
) + 1

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