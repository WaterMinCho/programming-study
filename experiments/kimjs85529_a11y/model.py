from pathlib import Path

import torch
import torch.nn as nn

from experiments.michae18.model import SmallLSTM
from .inspect_gaps import build_time_features_batch


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = (
    PROJECT_ROOT.parent
    / "study-data"
    / "common-input-f8-20261118"
    / "recorded"
)

TRACK = "ai"
SPLIT = "train"
SEED = 42
HISTORY_LENGTH = 32


def make_model_inputs(raw_inputs, device):
    device = torch.device(device)

    types = {
        "questions": torch.long,
        "concepts": torch.float32,
        "results": torch.float32,
        "lengths": torch.long,
        "query_question": torch.long,
        "query_concepts": torch.float32,
    }

    inputs = {
        key: torch.as_tensor(
            raw_inputs[key],
            dtype=dtype,
            device=device
        )
        for key, dtype in types.items()
    }

    seconds = torch.as_tensor(
        raw_inputs["query_gap_seconds"],
        dtype=torch.float32,
        device=device
    )

    known = torch.as_tensor(
        raw_inputs["query_gap_known"],
        dtype=torch.bool,
        device=device
    )

    inputs["time_features"] = build_time_features_batch(
        inputs["query_concepts"],
        seconds,
        known
    )

    return inputs


class TimeGapLSTM(SmallLSTM):
    def __init__(
        self,
        num_questions,
        num_concepts,
        embeding_num=16,
        hidden_num=16
    ):
        # 팀원이 작성한 기본 LSTM의 임베딩과 LSTM을 그대로 사용
        super().__init__(
            num_questions,
            num_concepts,
            embeding_num,
            hidden_num
        )

        self.time_feature_num = 2

        # 최종 예측 계층에 시간 특성 두 개만 추가
        self.fc = nn.Linear(
            hidden_num + embeding_num + num_concepts + 2,
            1
        )

    def forward(self, inputs):
        # 과거 학습 상태는 팀원의 encode_history()를 그대로 사용
        history_state = self.encode_history(inputs)

        query_emb = self.embedding(
            inputs["query_question"]
        )

        query_vector = torch.cat(
            [
                query_emb,
                inputs["query_concepts"]
            ],
            dim=-1
        )

        time_features = inputs["time_features"]

        if (
            not isinstance(time_features, torch.Tensor)
            or time_features.shape != (query_vector.size(0), 2)
        ):
            raise ValueError(
                "시간 특성은 (batch_size, 2) 형태여야 합니다."
            )

        if time_features.dtype != torch.float32:
            raise ValueError(
                "시간 특성은 torch.float32여야 합니다."
            )

        if time_features.device != query_vector.device:
            raise ValueError(
                "시간 특성과 모델 입력의 장치가 다릅니다."
            )

        combined = torch.cat(
            [
                history_state,
                query_vector,
                time_features
            ],
            dim=-1
        )

        return self.fc(combined).squeeze(-1)


def copy_baseline_weights(baseline_model, timegap_model):
    # 비교 시작 시 두 모델의 공통 가중치를 동일하게 설정
    if (
        not isinstance(baseline_model, SmallLSTM)
        or not isinstance(timegap_model, TimeGapLSTM)
    ):
        raise TypeError(
            "SmallLSTM과 TimeGapLSTM을 전달해야 합니다."
        )

    with torch.no_grad():
        timegap_model.embedding.load_state_dict(
            baseline_model.embedding.state_dict()
        )

        timegap_model.lstm.load_state_dict(
            baseline_model.lstm.state_dict()
        )

        if (
            timegap_model.fc.in_features
            != baseline_model.fc.in_features + 2
        ):
            raise ValueError(
                "두 모델의 예측 계층 차원이 일치하지 않습니다."
            )

        timegap_model.fc.weight[:, :-2].copy_(
            baseline_model.fc.weight
        )

        # 추가된 시간 특성 두 개의 초기 가중치는 0으로 설정
        timegap_model.fc.weight[:, -2:].zero_()

        timegap_model.fc.bias.copy_(
            baseline_model.fc.bias
        )

    return timegap_model
