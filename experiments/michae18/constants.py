from dataclasses import dataclass
# 공통 사용 상수
SEED = 42

# input_check.py 에서 사용하는 상수
DATASET_PATH = "../study-data/common-input-f8-20261118/recorded"
TRACK = 'ai'
SEQUENCE_LENGTH = 32

# 자주 변경될 값이라 dataclass로 상수 모듈 생성
@dataclass(frozen=True)
class Modelconfig:
    embedding_num : int = 16
    hidden_num : int = 16
    dropout : float = 0.2

@dataclass(frozen=True)
class Trainconfig:
    lr : float = 1e-3
    weight_decay : float = 1e-3
    max_epoch: int = 500
    patience : int = 20
    prediction_threshold : float = 0.5