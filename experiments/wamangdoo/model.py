import torch
from torch import nn

class SmallTransformer(nn.Module):

    def __init__(
        self,
        num_questions,
        num_concepts,
        embed_num = 16,
        hidden_num = 16,
        nhead = 4,          # 16의 약수 중에 골라야함
        num_layers = 2,
        max_len = 128,
        dropout = 0.1,
    ):
        super().__init__()
        self.hidden_num = hidden_num

        # 1) embed_num 차원 벡터로 변환
        # padding_idx=0: 빈 자리 0 벡터로 고정
        self.embedding = nn.Embedding(num_questions, embed_num, padding_idx=0)

        # 2) 과거 결합 벡터를 Transformer 차원으로 Linear
        self.input_proj = nn.Linear(embed_num + num_concepts + 1, hidden_num)

        # 3) 풀이 순서 정보 임베딩 (위치 정보)
        self.position_embedding = nn.Embedding(max_len, hidden_num)

        # 4) TransformerEncoder 층 구성
        # 전체 이력을 한 번에 요약한 뒤 이진 예측 점수 1개만 뽑으면 되기 때문에 Encoder만 썼다
        encoder_layer = nn.TransformerEncoderLayer(
            d_model = hidden_num,
            nhead = nhead,
            dim_feedforward = hidden_num * 2,   ## 기본 배율은 4배, 데이터가 작아서 파라미터가 많아지면 과적합 위험이 있어서 2배
            dropout = dropout,
            batch_first = True,
        )

        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers = num_layers,
            enable_nested_tensor = False,   ## enable_nested_tensor=False: PyTorch 2.x에서 src_key_padding_mask를 쓸 때 경고나 미세 오차가 날 수 있어, 이를 꺼서 패딩 값을 바꿔도 예측값이 완전히 똑같이(0.0 오차) 나오게 보장합니다.
        )

        # 5) logit 계산
        self.fc = nn.Linear(hidden_num + embed_num + num_concepts, 1)

    def encode_history(self, inputs):
        # 과거 풀이 기록을 읽어 빈 이력(lengths==0)과 빈 자리(패딩)를 제외한 요약 상태를 반환함
        device = self.embedding.weight.device
        dtype = self.embedding.weight.dtype

        questions = torch.as_tensor(inputs["questions"], dtype=torch.long, device=device)
        concepts = torch.as_tensor(inputs["concepts"], dtype=dtype, device=device)
        results = torch.as_tensor(inputs["results"], dtype=dtype, device=device)
        mask = torch.as_tensor(inputs["mask"], dtype=torch.bool, device=device)

        # 과거 문제 번호 임베딩 후 개념, 정오답과 하나로 결합
        ## unsqueeze 옆으로 이어 붙일 수 있게.
        question_embedding = self.embedding(questions)
        history_input = torch.cat(
            [question_embedding, concepts, results.unsqueeze(-1)],
            dim=-1,
        )

        # 위치(순서) 인덱스 생성 후 투영된 과거 특성에 위치 임베딩을 더함
        positions = torch.arange(questions.size(1), device=device).unsqueeze(0)
        history_embedding = self.input_proj(history_input) + self.position_embedding(positions)

        # 과거 풀이 기록이 없는 학생을 위해 기본 상태 벡터를 0으로 먼저 초기화함
        batch_size = questions.size(0)
        history_state = history_embedding.new_zeros(batch_size, self.hidden_num)

        # 실제 과거 풀이가 1개라도 있는 학생만 골라서 Transformer
        has_history = mask.any(dim=1)
        if has_history.any().item():
            valid_embedding = history_embedding[has_history]
            valid_mask = mask[has_history]

            # 공통 입력의 mask=True는 '실제 자리'이지만, PyTorch src_key_padding_mask=True는 '가릴 자리'이므로 ~valid_mask로 반전시킴
            padding_mask = ~valid_mask
            encoded = self.transformer(valid_embedding, src_key_padding_mask=padding_mask)

            ## 그냥 평균을 내면 뒤쪽 빈 칸 자리에서 나온 가짜 값들까지 평균에 섞입니다.
            ## 빈 칸(False=0)을 곱해 0으로 날린 뒤, 실제 푼 개수(mask_float.sum)로만 나누어 순수한 요약 벡터를 만듭니다.
            mask_float = valid_mask.unsqueeze(-1).to(encoded.dtype)
            history_state[has_history] = (encoded * mask_float).sum(dim=1) / mask_float.sum(dim=1)

        return history_state

    def forward(self, inputs):
        history_state = self.encode_history(inputs)
        device = history_state.device
        dtype = history_state.dtype

        # 이번에 풀 문제(Query) 정보 변환 (이번 정오답 targets는 데이터 누수 방지를 위해 절대 입력에 포함하지 않음)
        query_question = torch.as_tensor(inputs["query_question"], dtype=torch.long, device=device)
        query_concepts = torch.as_tensor(inputs["query_concepts"], dtype=dtype, device=device)

        query_embedding = self.embedding(query_question)
        query_vector = torch.cat([query_embedding, query_concepts], dim=-1)

        # logits 계산
        ## 추후 학습 시 nn.BCEWithLogitsLoss가 내부에서 시그모이드를 처리하므로 여기서는 logit 그대로 반환함.
        ## 모양 맞추기 squeeze
        combined = torch.cat([history_state, query_vector], dim=-1)
        logits = self.fc(combined).squeeze(-1)
        return logits
