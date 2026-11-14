
import torch

from experiments.michae18.model import SmallLSTM


def make_inputs(lengths):
    # batch=4, sequence length=4, concepts=3
    questions = torch.tensor([
        [0, 0, 0, 0],
        [1, 2, 0, 0],
        [0, 0, 0, 0],
        [3, 4, 5, 6],
    ], dtype=torch.long)

    concepts = torch.zeros(4, 4, 3)
    results = torch.zeros(4, 4)

    return {
        "questions": questions,
        "concepts": concepts,
        "results": results,
        "lengths": torch.tensor(lengths, dtype=torch.long),
        "query_question": torch.tensor([1, 2, 3, 4]),
        "query_concepts": torch.zeros(4, 3),
    }


def check_probabilities(output):
    assert output.shape == (4,)
    assert torch.isfinite(output).all().item()
    assert ((output >= 0) & (output <= 1)).all().item()


def test_mixed_empty_history():
    model = SmallLSTM(num_questions=10, num_concepts=3)
    model.eval()

    inputs = make_inputs([0, 2, 0, 4])

    with torch.no_grad():
        output = model(inputs)

    check_probabilities(output)


def test_all_empty_history():
    model = SmallLSTM(num_questions=10, num_concepts=3)
    model.eval()

    inputs = make_inputs([0, 0, 0, 0])

    with torch.no_grad():
        output = model(inputs)

    check_probabilities(output)


def test_padding_does_not_change_prediction():
    model = SmallLSTM(num_questions=10, num_concepts=3)
    model.eval()

    inputs = make_inputs([0, 2, 0, 4])

    with torch.no_grad():
        before = model(inputs).clone()

        # 두 번째 행의 실제 이력은 2개.
        # 따라서 3~4번째 위치만 변경한다.
        inputs["questions"][1, 2:] = torch.tensor([7, 8])
        inputs["concepts"][1, 2:, :] = 1.0
        inputs["results"][1, 2:] = 1.0

        after = model(inputs)

    torch.testing.assert_close(before, after)


if __name__ == "__main__":
    test_mixed_empty_history()
    print("PASS: 일부 빈 이력 처리")

    test_all_empty_history()
    print("PASS: 전체 빈 이력 처리")

    test_padding_does_not_change_prediction()
    print("PASS: 패딩 변경에 대한 예측 불변성")
