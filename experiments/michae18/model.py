import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence

class SmallLSTM(nn.Module):
    def __init__(self,num_questions,num_concepts,
                 embeding_num = 16, hidden_num = 16):
        super().__init__()
        # 문제 번호를 컴퓨터를 위해 번역한다 nn.Embedding 사용
        self.embedding = nn.Embedding(num_questions, embeding_num,padding_idx=0)
        # 과거 기록을 읽는 기억 장치(문제 푼 순서를 따라가며 학습 상태를 계산), 학습 가능한 내부 벡터 생성한다.
        self.lstm = nn.LSTM(embeding_num + num_concepts + 1, hidden_num,batch_first=True)
        # 점수 계산(분류기 생성한다.)
        self.fc = nn.Linear(hidden_num + embeding_num + num_concepts,1)

    # 학생 기록 읽기(과거 기록을 숫자로 변경)
    def encode_history(self, inputs):
        # 이전 문제 번호
        questions = inputs["questions"]
        # 이전 문제 개념
        concepts = inputs["concepts"]
        # 이전 문제 정오답
        results = inputs["results"]
        #무제를 푼 개수
        lengths = inputs["lengths"]

        # 과거 풀이를 컴퓨터가 이해 가능하도록 번호를 벡터(숫자 묶음으로)로 변경
        question_emb = self.embedding(questions)

        # 번호와 개념, 정오답을 history_input으로 정의
        history_input = torch.cat(
            [question_emb, concepts, results.unsqueeze(-1)],
            dim=-1
        )

        # 과거 풀이 없는 경우
        batch_size = questions.size(0)

        # 과거 학습 상태 정의,과거 기록 없는 학생 처리 방법
        history_state = history_input.new_zeros(
            batch_size, self.lstm.hidden_size
        ) # new_zeros: history_input의 구조와 device에 맞게 0행렬 생성
        
        # 실제 과거 풀이가 있는 사람만 lstm 실행한다.
        before_tested_num = lengths > 0
        if before_tested_num.any().item():
            # pack_padded_sequence: padding을 제외한 값들만 가져옴
            packed = pack_padded_sequence(
                history_input[before_tested_num],
                lengths[before_tested_num].cpu(),
                batch_first=True,
                enforce_sorted=False
            )
            _, (h_n, _) = self.lstm(packed)
            # output , (h_n : hidden state(상태 요약), c_n : cell state(내부 벡터(기억)))
            history_state[before_tested_num] = h_n[-1] # 마지막 풀이 이후의 h_n 가져오기
        return history_state

    # 과거 학습 상태 + 현재 문제로 확률 예측
    def forward(self, inputs):
        # 과거 학습 상태 가져오기
        history_state = self.encode_history(inputs)

        # 예측할 문제 가져와 embedding 한다
        query_emb = self.embedding(
            inputs["query_question"]
        )

        # 임베딩한 예측할 문제와 개념을 query_vector로 정의
        query_vector = torch.cat(
            [query_emb, inputs["query_concepts"]],
            dim=-1
        )
        # 과거 상태 + 예측할 문제
        combined = torch.cat(
            [history_state, query_vector],
            dim=-1
        )

        #  logits 값으로 전달
        logits = self.fc(combined).squeeze(-1)
        # sigmoid로 출력
        probabilities = torch.sigmoid(logits)

        return probabilities