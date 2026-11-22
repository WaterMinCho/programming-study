import math
import tempfile
import sys
from pathlib import Path

# 직접 실행 및 python -m 실행 모두 지원
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
import torch.nn as nn

from experiments.michae18.model import SmallLSTM
from experiments.kimjs85529_a11y.inspect_gaps import get_device, set_seed
from experiments.kimjs85529_a11y.model import (
    TimeGapLSTM,
    make_model_inputs,
    copy_baseline_weights,
    DATASET_PATH,
    TRACK,
    SPLIT,
    HISTORY_LENGTH,
    SEED,
)


def sample_inputs(device):
    # 빈 이력 1건, 정상 이력 1건을 포함한 인공 입력
    raw = {
        "questions": [[0, 0, 0, 0], [2, 3, 0, 0]],
        "concepts": [
            [[0.0] * 4 for _ in range(4)],
            [
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
                [0.0] * 4,
                [0.0] * 4,
            ],
        ],
        "results": [[0.0] * 4, [1.0, 0.0, 0.0, 0.0]],
        "lengths": [0, 2],
        "query_question": [2, 3],
        "query_concepts": [[0, 0, 1, 0], [0, 0, 1, 0]],
        "query_gap_seconds": [
            [0, 0, 0, 0],
            [0, 0, 86400, 0],
        ],
        "query_gap_known": [
            [False] * 4,
            [False, False, True, False],
        ],
    }

    return make_model_inputs(raw, device)


def create_model(device):
    return TimeGapLSTM(
        num_questions=10,
        num_concepts=4,
    ).to(device)


def test_baseline(device):
    # 시간 가중치가 0이면 기본 LSTM과 초기 출력이 같아야 함
    set_seed(SEED)

    baseline = SmallLSTM(
        num_questions=10,
        num_concepts=4,
    ).to(device).eval()

    model = create_model(device).eval()

    copy_baseline_weights(baseline, model)

    inputs = sample_inputs(device)

    with torch.no_grad():
        torch.testing.assert_close(
            baseline(inputs),
            model(inputs),
            rtol=1e-6,
            atol=1e-6,
        )

    print("통과: 기본 LSTM과 초기 출력 일치")


def test_model(device):
    set_seed(SEED)

    model = create_model(device).eval()
    inputs = sample_inputs(device)

    # 출력 형상, 확률 범위, 빈 이력 처리
    with torch.no_grad():
        logits = model(inputs)

        assert logits.shape == (2,)
        assert torch.isfinite(logits).all().item()

        probabilities = torch.sigmoid(logits)

        assert (
            (probabilities >= 0) & (probabilities <= 1)
        ).all().item()

        assert torch.equal(
            model.encode_history(inputs)[0],
            torch.zeros(16, device=device),
        )

        # 패딩 영역을 수정해도 출력이 동일해야 함
        modified = {
            key: value.clone()
            for key, value in inputs.items()
        }

        modified["questions"][1, 2:] = torch.tensor(
            [7, 8],
            device=device,
        )

        modified["concepts"][1, 2:, 2] = 1.0
        modified["results"][1, 2:] = 1.0

        torch.testing.assert_close(
            model(inputs)[1],
            model(modified)[1],
            rtol=0,
            atol=0,
        )

    print("통과: 출력 형상·확률·빈 이력·패딩")

    # 나머지 입력은 같게 두고 시간 특성만 변경
    pair = {
        key: value[1:2].repeat(
            (2,) + (1,) * (value.ndim - 1)
        )
        for key, value in inputs.items()
    }

    with torch.no_grad():
        model.fc.weight[0, -2:] = torch.tensor(
            [1.0, 1.0],
            device=device,
        )

        # 시간 미확인 [0, 0] vs 실제 0초 [0, 1]
        pair["time_features"] = torch.tensor(
            [[0.0, 0.0], [0.0, 1.0]],
            device=device,
        )

        logits = model(pair)
        diff_known = logits[1] - logits[0]

        torch.testing.assert_close(
            diff_known,
            torch.tensor(1.0, device=device),
            atol=1e-6,
            rtol=1e-5,
        )

        # 0일 vs 1일: log(2) 차이 확인
        pair["time_features"] = torch.tensor(
            [[0.0, 1.0], [math.log(2), 1.0]],
            device=device,
        )

        logits = model(pair)
        diff_gap = logits[1] - logits[0]

        torch.testing.assert_close(
            diff_gap,
            torch.tensor(math.log(2), device=device),
            atol=1e-6,
            rtol=1e-5,
        )

    print("통과: 시간 미확인/0초 구분")
    print("통과: gap_log의 출력 반영")

    # 인공 입력으로 역전파와 가중치 갱신 확인
    set_seed(SEED)

    model = create_model(device).train()

    optimizer = torch.optim.SGD(
        model.parameters(),
        lr=0.01,
    )

    optimizer.zero_grad()

    logits = model(inputs)

    targets = torch.zeros(
        2,
        dtype=torch.float32,
        device=device,
    )

    loss = nn.BCEWithLogitsLoss()(
        logits,
        targets,
    )

    loss.backward()

    gradient = model.fc.weight.grad[0, -2:]

    assert torch.isfinite(gradient).all().item()
    assert (gradient != 0).all().item()
    assert model.lstm.weight_ih_l0.grad is not None

    before = model.fc.weight[0, -2:].detach().clone()

    optimizer.step()

    after = model.fc.weight[0, -2:].detach().clone()

    assert not torch.equal(before, after)

    print("통과: 역전파 및 가중치 갱신")


def test_real_data(device):
    # 실제 데이터가 없는 환경에서는 건너뜀
    if not (DATASET_PATH / "manifest.json").is_file():
        print("SKIP: 실제 v8 데이터 없음")
        return

    from learning_server.input_example import load, batch

    rows, vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        SPLIT,
    )

    assert rows

    model = TimeGapLSTM(
        num_questions=len(vocabulary["questions"]),
        num_concepts=len(vocabulary["concepts"]),
    ).to(device).eval()

    count = 0

    with torch.no_grad():
        for start in range(0, len(rows), 32):
            selected_rows = rows[start:start + 32]

            example = batch(
                selected_rows,
                vocabulary,
                length=HISTORY_LENGTH,
            )

            inputs = make_model_inputs(
                example["inputs"],
                device,
            )

            logits = model(inputs)

            assert logits.shape == (len(selected_rows),)
            assert torch.isfinite(logits).all().item()

            count += len(selected_rows)

    assert count == len(rows)

    print("통과: 실제 데이터 전체 순전파", count, "건")


def test_checkpoint(device):
    # 모델 저장·복원 후 출력이 유지되는지 확인
    set_seed(SEED)

    model = create_model(device).eval()
    inputs = sample_inputs(device)

    with torch.no_grad():
        before = model(inputs)

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "timegap_test.pt"

        torch.save(
            model.state_dict(),
            path,
        )

        restored = create_model(device).eval()

        restored.load_state_dict(
            torch.load(
                path,
                map_location="cpu",
                weights_only=True,
            )
        )

        with torch.no_grad():
            after = restored(inputs)

        torch.testing.assert_close(
            after,
            before,
            rtol=0,
            atol=0,
        )

    print("통과: 모델 저장·복원 후 출력 일치")


def main():
    device = get_device()

    print("사용 장치:", device)

    test_baseline(device)
    test_model(device)
    test_real_data(device)
    test_checkpoint(device)

    print("\n기능 검증 완료")
    print("실제 학습 및 성능 평가는 미실행")


if __name__ == "__main__":
    main()