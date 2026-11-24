from pathlib import Path
import pandas as pd
import numpy as np
import subprocess
import sys

def save_predictions(
    event_ids,
    probabilities,
    output_path="../preds/lstm-validation.csv",
    model_version="small-lstm-v1"
):
    probabilities = np.asarray(probabilities).reshape(-1)
    event_ids = list(event_ids)

    if len(event_ids) != len(probabilities):
        raise ValueError("event_id 개수와 예측 확률 개수가 다릅니다.")

    if len(set(event_ids)) != len(event_ids):
        raise ValueError("중복된 event_id가 있습니다.")

    if not np.isfinite(probabilities).all():
        raise ValueError("NaN 또는 무한대 확률이 있습니다.")

    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("확률은 0 이상 1 이하여야 합니다.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        raise FileExistsError(
            f"이미 파일이 존재합니다: {output_path}"
        )

    if len(event_ids) == 0:
        raise ValueError("예측 데이터가 비어 있습니다.")
    
    df = pd.DataFrame({
        "event_id": event_ids,
        "probability": probabilities,
        "model_version": model_version
    })

    print("저장 경로:", output_path.resolve())
    print("파일 존재:", output_path.exists())
    print("디렉터리 여부:", output_path.is_dir())

    df.to_csv(output_path, index=False)

    print(f"예측 파일 저장 완료: {output_path}")
    print(f"예측 행 수: {len(df)}")

    return df

def validate_predictions(
    csv_path,
    expected_event_ids
):
    df = pd.read_csv(
        csv_path,
        dtype={"event_id": str}
    )

    required_columns = [
        "event_id",
        "probability",
        "model_version"
    ]

    if list(df.columns) != required_columns:
        raise ValueError("CSV 열 이름 또는 순서가 잘못됐습니다.")

    if df.isna().any().any():
        raise ValueError("CSV에 결측값이 있습니다.")

    if df["event_id"].duplicated().any():
        raise ValueError("중복 event_id가 있습니다.")

    expected_ids = [str(x) for x in expected_event_ids]
    actual_ids = df["event_id"].tolist()

    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("평가 데이터의 event_id가 중복됐습니다.")

    if actual_ids != expected_ids:
        raise ValueError(
            "event_id가 평가 데이터의 순서와 일치하지 않습니다."
        )

    probabilities = pd.to_numeric(
        df["probability"],
        errors="raise"
    ).to_numpy(dtype=float)

    if not np.isfinite(probabilities).all():
        raise ValueError("확률에 NaN 또는 무한대가 있습니다.")

    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("확률 범위가 0~1을 벗어났습니다.")

    if df["model_version"].nunique() != 1:
        raise ValueError("model_version이 하나가 아닙니다.")

    if (df["model_version"].astype(str).str.strip() == "").any():
        raise ValueError("model_version이 비어 있습니다.")

    print("CSV 검증 통과")
    print("예측 행 수:", len(df))
    print("모델 버전:", df["model_version"].iloc[0])
    print(df.head())

    return df

def run_score(
    dataset_path,
    predictions_path,
    output_path=None
):
    command = [
        sys.executable,
        "-m",
        "learning_server.score",
        "--dataset", str(dataset_path),
        "--track", "ai",
        "--split", "validation",
        "--predictions", str(predictions_path)
    ]

    if output_path is not None:
        output_path = Path(output_path)

        if output_path.exists():
            raise FileExistsError(
                f"이미 결과 파일이 존재합니다: {output_path}"
            )

        command.extend(["--out", str(output_path)])

    subprocess.run(
        command,
        check=True
    )