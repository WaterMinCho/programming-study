from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch
from experiments.wamangdoo.model import SmallTransformer
from experiments.wamangdoo.run import to_model_inputs


def create_test_model():
    torch.manual_seed(42)
    model = SmallTransformer(num_questions=10, num_concepts=3)
    model.eval()
    return model


def format_probs(values):
    return [round(float(v), 6) for v in values]


def make_inputs(lengths):
    """batch()가 만든 것과 같은 파이썬 리스트를 run.py의 to_model_inputs()로 변환해 모의 배치를 생성함."""
    base_questions = [
        [0, 0, 0, 0],
        [1, 2, 0, 0],
        [0, 0, 0, 0],
        [3, 4, 5, 6],
    ]
    seq_len = len(base_questions[0])
    mask = [[pos < length for pos in range(seq_len)] for length in lengths]
    questions = [
        [q if keep else 0 for q, keep in zip(row, row_mask)]
        for row, row_mask in zip(base_questions, mask)
    ]

    return to_model_inputs({
        "questions": questions,
        "concepts": [[[0.0, 0.0, 0.0] for _ in range(seq_len)] for _ in lengths],
        "results": [[0.0] * seq_len for _ in lengths],
        "mask": mask,
        "query_question": [1, 2, 3, 4],
        "query_concepts": [[0.0, 0.0, 0.0] for _ in lengths],
    })


def check_logits(logits):
    """모델 출력 로짓이 4개이며 NaN/Inf 없이 유한하고, 시그모이드 변환 시 0~1 사이 확률이 되는지 확인함."""
    assert logits.shape == (4,)
    assert torch.isfinite(logits).all().item()
    probabilities = torch.sigmoid(logits)
    assert ((probabilities >= 0.0) & (probabilities <= 1.0)).all().item()
    return probabilities


def test_mixed_empty_history():
    """일부 빈 이력 처리 + 빈 이력 학생(state=0)의 Query 반영 여부를 확인함."""
    model = create_test_model()

    # 1) 서로 다른 query_question([1, 2, 3, 4])일 때: 빈 이력인 0번·2번 행도 문제가 다르면 확률이 달라야 함
    diff_query_inputs = make_inputs([0, 2, 0, 4])
    # 2) 같은 query_question(0번·2번 모두 1번 문제)일 때: 둘 다 과거 상태가 0이므로 확률이 완전히 같아야 함
    same_query_inputs = make_inputs([0, 2, 0, 4])
    same_query_inputs["query_question"][2] = same_query_inputs["query_question"][0]

    with torch.no_grad():
        logits = model(diff_query_inputs)
        probs = check_logits(logits)

        same_query_logits = model(same_query_inputs)
        same_query_probs = check_logits(same_query_logits)

    assert abs(float(probs[0].item() - probs[2].item())) > 1e-6
    torch.testing.assert_close(same_query_probs[0], same_query_probs[2], atol=0.0, rtol=0.0)

    return {
        "probs": probs,
        "diff_query_empty_probs": (round(float(probs[0].item()), 6), round(float(probs[2].item()), 6)),
        "same_query_empty_probs": (
            round(float(same_query_probs[0].item()), 6),
            round(float(same_query_probs[2].item()), 6),
        ),
        "same_query_diff": abs(float(same_query_probs[0].item() - same_query_probs[2].item())),
    }


def test_all_empty_history():
    """배치 내 모든 샘플의 과거 이력이 비어 있어도(lengths=[0,0,0,0]) has_history 가드로 NaN 없이 예측되는지 확인함."""
    model = create_test_model()

    inputs = make_inputs([0, 0, 0, 0])
    with torch.no_grad():
        logits = model(inputs)
        probs = check_logits(logits)

    return {"probs": probs}


def test_padding_does_not_change_prediction():
    """부분 이력 행과 빈 이력 행의 빈 자리(mask=False) 값을 바꿔도 예측값이 달라지지 않는지 확인함."""
    model = create_test_model()
    inputs = make_inputs([0, 2, 0, 4])

    with torch.no_grad():
        before_logits = model(inputs).clone()
        before_probs = torch.sigmoid(before_logits)

        # 1) 부분 이력 행(인덱스 1, lengths=2)의 빈 자리(인덱스 2~3) 값을 임의로 변경
        inputs["questions"][1, 2:] = torch.tensor([7, 8])
        inputs["concepts"][1, 2:, :] = 1.0
        inputs["results"][1, 2:] = 1.0

        # 2) 빈 이력 행(인덱스 0, 2, lengths=0)의 빈 자리 전체 값도 임의로 변경
        for empty_row in (0, 2):
            inputs["questions"][empty_row, :] = torch.tensor([6, 7, 8, 9])
            inputs["concepts"][empty_row, :, :] = 1.0
            inputs["results"][empty_row, :] = 1.0

        after_logits = model(inputs)
        after_probs = torch.sigmoid(after_logits)

    torch.testing.assert_close(before_logits, after_logits, atol=1e-6, rtol=0.0)
    torch.testing.assert_close(before_probs, after_probs, atol=1e-6, rtol=0.0)

    max_diff = float((before_probs - after_probs).abs().max().item())
    return {
        "before_probs": before_probs,
        "after_probs": after_probs,
        "max_diff": max_diff,
    }


def test_position_order_changes_prediction():
    """과거 풀이의 순서를 맞바꾸면 위치 임베딩(position_embedding)에 의해 출력이 달라지는지 확인함."""
    model = create_test_model()

    # 첫 번째 풀이와 두 번째 풀이의 문제·정오답 순서를 서로 반대로 설정
    order_a = to_model_inputs({
        "questions": [[2, 3, 0, 0]],
        "concepts": [[[0.0, 0.0, 0.0]] * 4],
        "results": [[1.0, 0.0, 0.0, 0.0]],
        "mask": [[True, True, False, False]],
        "query_question": [4],
        "query_concepts": [[0.0, 0.0, 0.0]],
    })
    order_b = to_model_inputs({
        "questions": [[3, 2, 0, 0]],
        "concepts": [[[0.0, 0.0, 0.0]] * 4],
        "results": [[0.0, 1.0, 0.0, 0.0]],
        "mask": [[True, True, False, False]],
        "query_question": [4],
        "query_concepts": [[0.0, 0.0, 0.0]],
    })

    with torch.no_grad():
        logit_a = model(order_a)
        logit_b = model(order_b)

    prob_a = float(torch.sigmoid(logit_a).item())
    prob_b = float(torch.sigmoid(logit_b).item())
    logit_diff = abs(float(logit_a.item() - logit_b.item()))
    prob_diff = abs(prob_a - prob_b)

    # 단순 부동소수점 오차(1e-6) 이상으로 뚜렷하게 달라야 위치 정보가 반영된 것으로 판정함
    assert logit_diff > 1e-6

    return {
        "prob_a": round(prob_a, 6),
        "prob_b": round(prob_b, 6),
        "logit_diff": round(logit_diff, 6),
        "prob_diff": round(prob_diff, 6),
    }


class TestSmallTransformer(unittest.TestCase):
    """unittest 실행기(python -m unittest)에서도 동일하게 검증할 수 있도록 래핑함."""

    def test_mixed_empty_history(self):
        test_mixed_empty_history()

    def test_all_empty_history(self):
        test_all_empty_history()

    def test_padding_does_not_change_prediction(self):
        test_padding_does_not_change_prediction()

    def test_position_order_changes_prediction(self):
        test_position_order_changes_prediction()


if __name__ == "__main__":
    mixed_result = test_mixed_empty_history()
    print("=== 테스트 1: 일부 빈 이력 & Query 반영 확인 ===")
    print("[검증 조건] lengths=[0, 2, 0, 4] 혼합 배치, 빈 이력 학생(0·2행)은 state=0으로 초기화 후 Query로만 예측")
    print("[예상 결과] 4개 모두 0~1 유한 확률, 같은 Query(1번)면 확률 동일(차이 0.0), 다른 Query(1 vs 3번)면 확률 상이")
    print(
        "[실제 결과] 전체 확률="
        f"{format_probs(mixed_result['probs'])}, "
        f"같은 Query(1번) 0·2행={mixed_result['same_query_empty_probs']} (차이 {mixed_result['same_query_diff']}), "
        f"다른 Query(1 vs 3) 0·2행={mixed_result['diff_query_empty_probs']}"
    )
    print("PASS: 일부 빈 이력 처리")

    all_empty_result = test_all_empty_history()
    print("\n=== 테스트 2: 전체 빈 이력 처리 ===")
    print("[검증 조건] lengths=[0, 0, 0, 0] 전원 빈 이력 시 has_history.any() 가드로 Transformer/평균 나눗셈 건너뜀")
    print("[예상 결과] NaN(0/0) 없이 4개 모두 0~1 사이 유한한 확률 출력")
    print(f"[실제 결과] 확률={format_probs(all_empty_result['probs'])}")
    print("PASS: 전체 빈 이력 처리")

    padding_result = test_padding_does_not_change_prediction()
    print("\n=== 테스트 3: 패딩 변경 불변성 ===")
    print("[검증 조건] 부분 이력 행(1행 2~3열)과 빈 이력 행(0·2행 전체)의 mask=False 빈 칸 값을 6~9, 1.0으로 변경")
    print("[예상 결과] ~valid_mask와 마스킹 평균 덕분에 변경 전/후 예측 확률이 동일(차이 <= 1e-6)")
    print(
        "[실제 결과] 변경 전="
        f"{format_probs(padding_result['before_probs'])}, "
        f"변경 후={format_probs(padding_result['after_probs'])}, "
        f"최대 차이={padding_result['max_diff']}"
    )
    print("PASS: 부분·전체 빈 이력의 패딩 변경에 대한 예측 불변성")

    order_result = test_position_order_changes_prediction()
    print("\n=== 테스트 4: 과거 풀이 순서(위치 임베딩) 반영 ===")
    print("[검증 조건] [2번 정답 -> 3번 오답] vs [3번 오답 -> 2번 정답] 순서만 반대로 입력")
    print("[예상 결과] position_embedding 덕분에 두 경우의 예측 로짓/확률이 다르게 출력됨(로짓 차이 > 1e-6)")
    print(
        "[실제 결과] 순서A(2O->3X)="
        f"{order_result['prob_a']}, "
        f"순서B(3X->2O)={order_result['prob_b']}, "
        f"확률 차이={order_result['prob_diff']}, 로짓 차이={order_result['logit_diff']}"
    )
    print("PASS: 과거 풀이 순서(위치 임베딩) 변경 반영")
