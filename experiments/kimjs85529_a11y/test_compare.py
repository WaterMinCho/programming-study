import sys
import argparse
import csv
import math
from pathlib import Path


# VSCode 직접 실행과 python -m 실행 모두 지원
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import torch
import torch.nn as nn

from learning_server.input_example import load, batch
from experiments.michae18.model import SmallLSTM
from experiments.kimjs85529_a11y.inspect_gaps import get_device
from experiments.kimjs85529_a11y.model import (
    TimeGapLSTM,
    make_model_inputs,
    DATASET_PATH,
    TRACK,
    HISTORY_LENGTH
)


# 기존 학습 결과 저장 위치
RESULT_DIR = (
    CURRENT_FILE.parent
    / "comparison_results"
)

# 공식 채점용 예측 CSV는 Git 저장소 밖에 저장
PREDICTION_DIR = (
    DATASET_PATH.parent.parent
    / "model-predictions"
)


# 1. 모델 평가 함수
def evaluate_model(model, inputs, targets):

    model.eval()

    criterion = nn.BCEWithLogitsLoss()

    with torch.no_grad():

        # 모델의 예측 결과
        logits = model(inputs)

        # 손실값 계산
        loss = criterion(logits, targets).item()

        # Logit을 정답 확률로 변환
        probabilities = torch.sigmoid(logits)

        # 확률 0.5 이상이면 정답으로 예측
        predicted = (probabilities >= 0.5).float()

        accuracy = (
            (predicted == targets).float().mean().item()
        )

        tp = int(
            ((predicted == 1) & (targets == 1)).sum().item()
        )

        tn = int(
            ((predicted == 0) & (targets == 0)).sum().item()
        )

        fp = int(
            ((predicted == 1) & (targets == 0)).sum().item()
        )

        fn = int(
            ((predicted == 0) & (targets == 1)).sum().item()
        )

        precision = (
            tp / (tp + fp)
            if (tp + fp) > 0
            else 0.0
        )

        recall = (
            tp / (tp + fn)
            if (tp + fn) > 0
            else 0.0
        )

        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

    result = {
        "loss": loss,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn
    }

    return result, probabilities.detach().cpu().tolist()


# 2. 공식 채점용 예측 CSV 저장
def save_score_predictions(
    event_ids,
    probabilities,
    model_version,
    output_path
):

    if len(event_ids) != len(probabilities):
        raise ValueError(
            "event_id와 예측 확률의 개수가 다릅니다."
        )

    if len(set(event_ids)) != len(event_ids):
        raise ValueError(
            "중복된 event_id가 있습니다."
        )

    for event_id, probability in zip(
        event_ids,
        probabilities
    ):

        if not isinstance(event_id, str) or not event_id:
            raise ValueError(
                "event_id는 비어 있지 않은 문자열이어야 합니다."
            )

        if (
            not math.isfinite(probability)
            or not 0.0 <= probability <= 1.0
        ):
            raise ValueError(
                "예측 확률은 0 이상 1 이하의 유한한 숫자여야 합니다."
            )

    # 기존 예측 파일 덮어쓰기 방지
    with output_path.open(
        "x",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "event_id",
            "probability",
            "model_version"
        ])

        for event_id, probability in zip(
            event_ids,
            probabilities
        ):

            writer.writerow([
                event_id,
                format(probability, ".17g"),
                model_version
            ])

    print("예측 CSV 저장:", output_path)
    print("저장한 예측 수:", len(probabilities))


# 3. 모델별 평가 결과 출력
def print_model_result(name, result, split):

    print(f"\n===== {name} {split.upper()} 결과 =====")

    for key, value in result.items():

        if isinstance(value, float):
            print(f"{key}: {value:.6f}")
        else:
            print(f"{key}: {value}")


# 4. 두 모델의 평가 결과 비교
def compare_evaluation_results(
    baseline_result,
    timegap_result,
    split
):

    print(f"\n===== {split.upper()} 성능 비교 =====")

    print(
        f"{'항목':<20}"
        f"{'SmallLSTM':>15}"
        f"{'TimeGapLSTM':>15}"
        f"{'차이(TimeGap-Base)':>20}"
    )

    for key in (
        "loss",
        "accuracy",
        "precision",
        "recall",
        "f1_score"
    ):

        base_value = baseline_result[key]
        gap_value = timegap_result[key]
        difference = gap_value - base_value

        print(
            f"{key:<20}"
            f"{base_value:>15.6f}"
            f"{gap_value:>15.6f}"
            f"{difference:>20.6f}"
        )


# 5. 모델 평가 결과 CSV 저장
def save_comparison_results(
    baseline_result,
    timegap_result,
    split
):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result_path = RESULT_DIR / f"{split}_comparison.csv"

    fieldnames = [
        "model",
        "loss",
        "accuracy",
        "precision",
        "recall",
        "f1_score",
        "TP",
        "TN",
        "FP",
        "FN"
    ]

    with result_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerow({
            "model": "SmallLSTM",
            **baseline_result
        })

        writer.writerow({
            "model": "TimeGapLSTM",
            **timegap_result
        })

    print("\n===== 성능 비교 결과 저장 =====")
    print("결과 CSV:", result_path)


# 6. 모델 평가 실행
def run_evaluation(split, export_predictions):

    device = get_device()

    print("===== 실행 환경 =====")
    print("사용 장치:", device)
    print("PyTorch:", torch.__version__)
    print("데이터 경로:", DATASET_PATH)
    print("평가 구간:", split)
    print("프로젝트 경로:", PROJECT_ROOT)

    if not (DATASET_PATH / "manifest.json").is_file():
        raise FileNotFoundError(
            f"실제 데이터가 없습니다: {DATASET_PATH}"
        )

    # Train Vocabulary 불러오기
    train_rows, train_vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        "train"
    )

    # 평가 데이터 불러오기
    evaluation_rows, evaluation_vocabulary = load(
        str(DATASET_PATH),
        TRACK,
        split
    )

    if evaluation_vocabulary != train_vocabulary:
        raise ValueError(
            "Train과 평가 구간의 Vocabulary가 일치하지 않습니다."
        )

    if not evaluation_rows:
        raise ValueError(
            "평가 데이터가 없습니다."
        )

    # Full Batch 입력 생성
    evaluation_data = batch(
        evaluation_rows,
        train_vocabulary,
        length=HISTORY_LENGTH
    )

    evaluation_inputs = make_model_inputs(
        evaluation_data["inputs"],
        device
    )

    evaluation_targets = torch.as_tensor(
        evaluation_data["targets"],
        dtype=torch.float32,
        device=device
    )

    print(f"\n===== {split.upper()} 데이터 =====")
    print("Train 데이터 수:", len(train_rows))
    print("평가 데이터 수:", len(evaluation_rows))
    print("Batch 방식: Full Batch")
    print("History Length:", HISTORY_LENGTH)

    # 모델 생성
    num_questions = len(train_vocabulary["questions"])
    num_concepts = len(train_vocabulary["concepts"])

    baseline = SmallLSTM(
        num_questions,
        num_concepts
    ).to(device)

    timegap = TimeGapLSTM(
        num_questions,
        num_concepts
    ).to(device)

    # 학습된 최적 가중치 경로
    baseline_path = RESULT_DIR / "SmallLSTM_best.pt"
    timegap_path = RESULT_DIR / "TimeGapLSTM_best.pt"

    if not baseline_path.is_file():
        raise FileNotFoundError(
            f"SmallLSTM 가중치 파일이 없습니다: {baseline_path}"
        )

    if not timegap_path.is_file():
        raise FileNotFoundError(
            f"TimeGapLSTM 가중치 파일이 없습니다: {timegap_path}"
        )

    # 저장된 최적 가중치 불러오기
    baseline.load_state_dict(
        torch.load(
            baseline_path,
            map_location="cpu",
            weights_only=True
        )
    )

    timegap.load_state_dict(
        torch.load(
            timegap_path,
            map_location="cpu",
            weights_only=True
        )
    )

    print("\n===== 모델 불러오기 =====")
    print("SmallLSTM:", baseline_path)
    print("TimeGapLSTM:", timegap_path)

    # 두 모델 평가
    baseline_result, baseline_probabilities = evaluate_model(
        baseline,
        evaluation_inputs,
        evaluation_targets
    )

    timegap_result, timegap_probabilities = evaluate_model(
        timegap,
        evaluation_inputs,
        evaluation_targets
    )

    # 평가 결과 출력
    print_model_result(
        "SmallLSTM",
        baseline_result,
        split
    )

    print_model_result(
        "TimeGapLSTM",
        timegap_result,
        split
    )

    compare_evaluation_results(
        baseline_result,
        timegap_result,
        split
    )

    # 평가 결과 CSV 저장
    save_comparison_results(
        baseline_result,
        timegap_result,
        split
    )

    # 공식 채점용 예측 CSV 생성
    if export_predictions:

        event_ids = evaluation_data["event_ids"]

        if event_ids != [
            row["event_id"]
            for row in evaluation_rows
        ]:
            raise ValueError(
                "event_id의 순서가 원본 데이터와 다릅니다."
            )

        PREDICTION_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        baseline_output = (
            PREDICTION_DIR
            / f"small-lstm-{split}.csv"
        )

        timegap_output = (
            PREDICTION_DIR
            / f"timegap-lstm-{split}.csv"
        )

        # 기존 공식 채점용 파일 덮어쓰기 방지
        if baseline_output.exists() or timegap_output.exists():
            raise FileExistsError(
                "공식 채점용 CSV가 이미 존재합니다.\n"
                f"{baseline_output}\n"
                f"{timegap_output}\n"
                "기존 파일을 덮어쓰지 않습니다."
            )

        print("\n===== 공식 채점용 예측 CSV 생성 =====")

        save_score_predictions(
            event_ids,
            baseline_probabilities,
            "small-lstm-v1",
            baseline_output
        )

        save_score_predictions(
            event_ids,
            timegap_probabilities,
            "timegap-lstm-v1",
            timegap_output
        )

        print("\n공식 채점용 예측 파일 생성 완료")
        print("개별 예측 데이터는 Git에 올리지 마세요.")

    print("\n추가 학습 없이 저장된 최적 모델로 평가했습니다.")


# 7. 과적합 분석용 학습 기록 읽기
def load_history(filename):

    import pandas as pd

    file_path = RESULT_DIR / filename

    if not file_path.is_file():
        raise FileNotFoundError(
            f"학습 기록 파일이 없습니다: {file_path}"
        )

    history = pd.read_csv(file_path)

    required_columns = [
        "epoch",
        "train_loss",
        "train_acc",
        "val_loss",
        "val_acc"
    ]

    for column in required_columns:

        if column not in history.columns:
            raise ValueError(
                f"학습 기록에 {column} 열이 없습니다."
            )

    if history.empty:
        raise ValueError(
            f"학습 기록이 비어 있습니다: {file_path}"
        )

    return history


# 8. 모델별 과적합 분석
def analyze_model(name, history):

    # Validation Loss가 가장 낮은 Epoch
    best_index = history["val_loss"].idxmin()
    best = history.loc[best_index]

    # 학습 종료 Epoch
    last = history.iloc[-1]

    # 최적 Epoch의 Train-Validation 격차
    loss_gap = best["val_loss"] - best["train_loss"]
    accuracy_gap = best["train_acc"] - best["val_acc"]

    # 최적 이후 Validation Loss 변화
    val_change = last["val_loss"] - best["val_loss"]

    print(f"\n===== {name} =====")

    print(f"최적 Epoch: {int(best['epoch'])}")
    print(f"종료 Epoch: {int(last['epoch'])}")

    print(f"최적 Train Loss: {best['train_loss']:.6f}")
    print(f"최적 Validation Loss: {best['val_loss']:.6f}")
    print(f"Train-Validation Loss 차이: {loss_gap:.6f}")

    print(f"최적 Train Accuracy: {best['train_acc']:.6f}")
    print(f"최적 Validation Accuracy: {best['val_acc']:.6f}")
    print(f"Train-Validation Accuracy 차이: {accuracy_gap:.6f}")

    print(f"종료 시 Train Loss: {last['train_loss']:.6f}")
    print(f"종료 시 Validation Loss: {last['val_loss']:.6f}")
    print(f"최적 이후 Validation Loss 변화: {val_change:+.6f}")

    if val_change > 0:
        print("판단: 최적 Epoch 이후 Validation Loss 증가")
    elif val_change == 0:
        print("판단: 최적 Epoch와 종료 시 Validation Loss 동일")
    else:
        print("판단: 기록을 다시 확인해야 합니다.")

    return {
        "best_epoch": int(best["epoch"]),
        "last_epoch": int(last["epoch"]),
        "train_loss": float(best["train_loss"]),
        "val_loss": float(best["val_loss"]),
        "loss_gap": float(loss_gap),
        "train_acc": float(best["train_acc"]),
        "val_acc": float(best["val_acc"]),
        "accuracy_gap": float(accuracy_gap),
        "last_train_loss": float(last["train_loss"]),
        "last_val_loss": float(last["val_loss"]),
        "val_change": float(val_change)
    }


# 9. 두 모델의 과적합 지표 비교
def compare_overfitting_results(
    baseline_result,
    timegap_result
):

    print("\n===== SmallLSTM vs TimeGapLSTM 과적합 비교 =====")

    print(
        f"{'항목':<32}"
        f"{'SmallLSTM':>16}"
        f"{'TimeGapLSTM':>16}"
        f"{'차이(Gap-Base)':>18}"
    )

    print("-" * 82)

    rows = [
        ("최적 Epoch", "best_epoch"),
        ("종료 Epoch", "last_epoch"),
        ("최적 Train Loss", "train_loss"),
        ("최적 Validation Loss", "val_loss"),
        ("Train-Validation Loss 차이", "loss_gap"),
        ("최적 Train Accuracy", "train_acc"),
        ("최적 Validation Accuracy", "val_acc"),
        ("Train-Validation Accuracy 차이", "accuracy_gap"),
        ("종료 시 Train Loss", "last_train_loss"),
        ("종료 시 Validation Loss", "last_val_loss"),
        ("최적 이후 Validation Loss 변화", "val_change")
    ]

    for label, key in rows:

        base_value = baseline_result[key]
        gap_value = timegap_result[key]
        difference = gap_value - base_value

        if key in ("best_epoch", "last_epoch"):

            print(
                f"{label:<32}"
                f"{base_value:>16d}"
                f"{gap_value:>16d}"
                f"{difference:>+18d}"
            )

        else:

            print(
                f"{label:<32}"
                f"{base_value:>16.6f}"
                f"{gap_value:>16.6f}"
                f"{difference:>+18.6f}"
            )

    print("\n===== 비교 결과 요약 =====")

    if timegap_result["val_loss"] < baseline_result["val_loss"]:
        print("Validation Loss: TimeGapLSTM이 더 낮음")
    elif timegap_result["val_loss"] > baseline_result["val_loss"]:
        print("Validation Loss: SmallLSTM이 더 낮음")
    else:
        print("Validation Loss: 두 모델 동일")

    if timegap_result["loss_gap"] < baseline_result["loss_gap"]:
        print("Train-Validation Loss 격차: TimeGapLSTM이 더 작음")
    elif timegap_result["loss_gap"] > baseline_result["loss_gap"]:
        print("Train-Validation Loss 격차: SmallLSTM이 더 작음")
    else:
        print("Train-Validation Loss 격차: 두 모델 동일")

    if timegap_result["val_acc"] > baseline_result["val_acc"]:
        print("Validation Accuracy: TimeGapLSTM이 더 높음")
    elif timegap_result["val_acc"] < baseline_result["val_acc"]:
        print("Validation Accuracy: SmallLSTM이 더 높음")
    else:
        print("Validation Accuracy: 두 모델 동일")

    if timegap_result["val_change"] < baseline_result["val_change"]:
        print("최적 이후 Validation Loss 증가량: TimeGapLSTM이 더 작음")
    elif timegap_result["val_change"] > baseline_result["val_change"]:
        print("최적 이후 Validation Loss 증가량: SmallLSTM이 더 작음")
    else:
        print("최적 이후 Validation Loss 증가량: 두 모델 동일")

    print(
        "\n주의: 한 번의 학습 결과만으로 "
        "과적합 억제 효과를 입증할 수는 없습니다."
    )


# 10. 모델별 과적합 그래프 생성
def plot_model_history(name, history):

    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))

    # 그래프 맨 위에 모델 이름 표시
    plt.suptitle(
        name,
        fontsize=18,
        fontweight="bold"
    )

    # 왼쪽: Train / Validation Loss
    plt.subplot(1, 2, 1)

    plt.plot(
        history["epoch"],
        history["train_loss"],
        label="Train Loss"
    )

    plt.plot(
        history["epoch"],
        history["val_loss"],
        label="Validation Loss"
    )

    plt.title("Train and Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()

    # 오른쪽: Train / Validation Accuracy
    plt.subplot(1, 2, 2)

    plt.plot(
        history["epoch"],
        history["train_acc"],
        label="Train Accuracy"
    )

    plt.plot(
        history["epoch"],
        history["val_acc"],
        label="Validation Accuracy"
    )

    plt.title("Train and Validation Accuracy")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.legend()

    plt.tight_layout(
        rect=[0, 0, 1, 0.94]
    )

    # 기존과 동일한 파일명으로 그래프 저장
    save_path = RESULT_DIR / f"{name}_overfitting.png"

    plt.savefig(
        save_path,
        dpi=150
    )

    print(f"{name} 그래프 저장: {save_path}")


# 11. 과적합 분석 전체 실행
def run_overfitting_analysis():

    import matplotlib.pyplot as plt

    # 학습 당시 저장한 기록 사용
    baseline = load_history(
        "SmallLSTM_history.csv"
    )

    timegap = load_history(
        "TimeGapLSTM_history.csv"
    )

    print("\n===== 과적합 분석 =====")
    print("학습 기록 사용: 기존 CSV")
    print("SmallLSTM Epoch 수:", len(baseline))
    print("TimeGapLSTM Epoch 수:", len(timegap))

    # 각 모델의 과적합 지표 분석
    baseline_result = analyze_model(
        "SmallLSTM",
        baseline
    )

    timegap_result = analyze_model(
        "TimeGapLSTM",
        timegap
    )

    # 모델별 지표 비교
    compare_overfitting_results(
        baseline_result,
        timegap_result
    )

    # 이전에 생성한 Figure가 남아 있다면 정리
    plt.close("all")

    # 그래프 1: SmallLSTM
    plot_model_history(
        "SmallLSTM",
        baseline
    )

    # 그래프 2: TimeGapLSTM
    plot_model_history(
        "TimeGapLSTM",
        timegap
    )

    print("\n===== 그래프 저장 완료 =====")

    print(
        "SmallLSTM 그래프:",
        RESULT_DIR / "SmallLSTM_overfitting.png"
    )

    print(
        "TimeGapLSTM 그래프:",
        RESULT_DIR / "TimeGapLSTM_overfitting.png"
    )

    print("\n그래프 창을 표시합니다.")

    # VSCode에서 그래프 창이 닫힐 때까지 유지
    plt.show(block=True)

    print("\n과적합 분석 완료")
    print("기존 학습 기록을 사용했으며 재학습하지 않았습니다.")


# 12. 실행 옵션 및 전체 실행 순서
def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--split",
        choices=["validation", "test"],
        default="test",
        help="평가 구간 선택 (기본값: test)"
    )

    parser.add_argument(
        "--export-predictions",
        action="store_true",
        help="공식 채점용 예측 CSV 저장"
    )

    parser.add_argument(
        "--analyze-overfitting",
        action="store_true",
        help="과적합 분석과 그래프만 실행"
    )

    args = parser.parse_args()

    # 과적합 분석만 실행하는 경우
    if args.analyze_overfitting:

        if args.export_predictions:
            parser.error(
                "--analyze-overfitting과 "
                "--export-predictions는 동시에 사용할 수 없습니다."
            )

        run_overfitting_analysis()
        return

    # 1. 기존 Validation / Test 성능 평가
    run_evaluation(
        args.split,
        args.export_predictions
    )

    # 2. 성능 평가 후 과적합 분석 자동 실행
    run_overfitting_analysis()


if __name__ == "__main__":
    main()
