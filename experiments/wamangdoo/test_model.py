import unittest
import torch
from torch import nn
from experiments.wamangdoo.model import SmallTransformer
from experiments.wamangdoo.train import (
    evaluate_one_epoch,
    predict_probabilities,
    train_one_epoch,
)

def make_model():
    torch.manual_seed(42)
    # 테스트용 모델 생성
    model = SmallTransformer(num_questions=5, num_concepts=3)
    model.eval()
    return model

def make_inputs():
    # 과거에 푼 문제 번호
    questions = torch.tensor([
        [0, 0, 0, 0],
        [1, 0, 0, 0],
        [1, 2, 0, 0],
        [1, 2, 3, 4],
    ], dtype=torch.long)

    # 과거 문제별 개념 정보 테스트용으로 0으로 채움
    concepts = torch.zeros(4, 4, 3, dtype=torch.float32)

    # 과거 문제 정오답
    results = torch.tensor([
        [0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0],  # 2번째 칸은 오답, 3번째 칸은 빈 자리
        [1.0, 1.0, 0.0, 1.0],
    ], dtype=torch.float32)

    mask = torch.tensor([
        [False, False, False, False],
        [True,  False, False, False],
        [True,  True,  False, False],
        [True,  True,  True,  True],
    ], dtype=torch.bool)

    # 이번에 맞힐지 예측할 문제 번호와 개념
    query_question = torch.tensor([1, 2, 3, 4], dtype=torch.long)
    query_concepts = torch.zeros(4, 3, dtype=torch.float32)

    return {
        "questions": questions,
        "concepts": concepts,
        "results": results,
        "mask": mask,
        "query_question": query_question,
        "query_concepts": query_concepts,
    }

class TestSmallTransformer(unittest.TestCase):
    def test_mixed_empty_history(self):
        # 1) 일부 빈 이력(학생 0)이 섞여 있어도 0~1 사이 확률 4개가 나오는지 확인
        model = make_model()
        inputs = make_inputs()

        with torch.no_grad():
            logits = model(inputs)
            probabilities = torch.sigmoid(logits)

        # 출력 개수 4개, NaN/Inf 없음, 확률 범위 0~1 확인
        self.assertEqual(logits.shape, (4,))
        self.assertTrue(torch.isfinite(logits).all().item())
        self.assertTrue(((probabilities >= 0.0) & (probabilities <= 1.0)).all().item())
        print("\n[1] 합성 예제 4개에서 확률 4개 확인:", probabilities.tolist())

    def test_all_empty_history(self):
        # 2) 4명 전원이 빈 이력(mask 전부 False)이어도 NaN 없이 확률 4개가 나오는지 확인
        model = make_model()
        inputs = make_inputs()
        # 4명 x 4칸의 mask를 전부 False로 변경
        inputs["mask"] = torch.zeros(4, 4, dtype=torch.bool)

        with torch.no_grad():
            logits = model(inputs)
            probabilities = torch.sigmoid(logits)

        self.assertEqual(logits.shape, (4,))
        self.assertTrue(torch.isfinite(logits).all().item())
        self.assertTrue(((probabilities >= 0.0) & (probabilities <= 1.0)).all().item())
        print("\n[2] 모든 과거 자리가 비어도 유효한 확률이 나오는지 확인:", probabilities.tolist())

    def test_padding_does_not_change_prediction(self):
        # 3) 평가 모드에서 빈 자리 값만 바꿔도 예측이 같은지 확인
        model = make_model()
        inputs = make_inputs()

        with torch.no_grad():
            # 빈 자리를 바꾸기 전 예측값을 복사해 저장
            before_logits = model(inputs).clone()
            before_probabilities = torch.sigmoid(before_logits)

            # 학생 0(전체 False)의 빈 자리 값을 임의로 변경
            inputs["questions"][0, :] = torch.tensor([2, 3, 4, 1])
            inputs["concepts"][0, :, :] = 1.0
            inputs["results"][0, :] = 1.0

            # 학생 2(뒤 2칸 False)의 빈 자리 값도 임의로 변경
            inputs["questions"][2, 2:] = torch.tensor([3, 4])
            inputs["concepts"][2, 2:, :] = 1.0
            inputs["results"][2, 2:] = 1.0

            # 빈 자리를 바꾼 뒤 다시 예측
            after_logits = model(inputs)
            after_probabilities = torch.sigmoid(after_logits)

        # 변경 전후 차이가 1e-6 이하로 같은지 확인
        torch.testing.assert_close(before_logits, after_logits, atol=1e-6, rtol=0.0)
        torch.testing.assert_close(before_probabilities, after_probabilities, atol=1e-6, rtol=0.0)
        print("\n[3] 평가 모드에서 패딩 변경 전:", before_probabilities.tolist())
        print("    평가 모드에서 패딩 변경 후:", after_probabilities.tolist())

    def test_position_order_changes_prediction(self):
        # 4) 과거 풀이 순서(위치 정보) 반영 확인
        model = make_model()

        # 같은 2문제의 순서와 정오답 순서만 서로 반대로 구성
        questions = torch.tensor([
            [1, 2, 0, 0],  # 순서 A: 1번 맞힘 -> 2번 틀림
            [2, 1, 0, 0],  # 순서 B: 2번 틀림 -> 1번 맞힘
        ], dtype=torch.long)
        concepts = torch.zeros(2, 4, 3, dtype=torch.float32)
        results = torch.tensor([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ], dtype=torch.float32)
        mask = torch.tensor([
            [True, True, False, False],
            [True, True, False, False],
        ], dtype=torch.bool)
        # 두 경우 모두 같은 3번 문제를 예측하도록 설정
        query_question = torch.tensor([3, 3], dtype=torch.long)
        query_concepts = torch.zeros(2, 3, dtype=torch.float32)

        order_inputs = {
            "questions": questions,
            "concepts": concepts,
            "results": results,
            "mask": mask,
            "query_question": query_question,
            "query_concepts": query_concepts,
        }

        with torch.no_grad():
            order_probabilities = torch.sigmoid(model(order_inputs))

        # 두 순서의 예측 확률 순서가 반영됐는지 확인
        probabilities_a = float(order_probabilities[0].item())
        probabilities_b = float(order_probabilities[1].item())
        self.assertGreater(abs(probabilities_a - probabilities_b), 1e-6)
        print("\n[4] 순서 A (1번O -> 2번X):", probabilities_a)
        print("    순서 B (2번X -> 1번O):", probabilities_b)

    def test_train_one_epoch_empty_rows_raises_value_error(self):
        # 5) train_one_epoch에 빈 리스트(rows=[])를 넘기면 ZeroDivisionError 대신 ValueError가 나는지 확인
        model = make_model()
        loss_fn = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>"]}

        with self.assertRaises(ValueError):
            train_one_epoch(model, [], vocabulary, loss_fn, optimizer, torch.device("cpu"))

    def test_evaluate_one_epoch_empty_rows_raises_value_error(self):
        # 6) evaluate_one_epoch에 빈 리스트(rows=[])를 넘기면 ValueError가 나는지 확인
        model = make_model()
        loss_fn = nn.BCEWithLogitsLoss()
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>"]}

        with self.assertRaises(ValueError):
            evaluate_one_epoch(model, [], vocabulary, loss_fn, torch.device("cpu"))

    def test_predict_probabilities_empty_rows_raises_value_error(self):
        # 7) predict_probabilities에 빈 리스트(rows=[])를 넘기면 ValueError가 나는지 확인
        model = make_model()
        vocabulary = {"questions": ["<PAD>", "<UNK>"], "concepts": ["<PAD>", "<UNK>"]}

        with self.assertRaises(ValueError):
            predict_probabilities(model, [], vocabulary, torch.device("cpu"))

if __name__ == "__main__":
    # 이 파일을 직접 실행할 때 테스트를 상세 출력(verbosity=2)으로 실행
    unittest.main(verbosity=2)
