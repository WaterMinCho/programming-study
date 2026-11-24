# -*- coding: utf-8 -*-
"""팀원이 낸 예측 파일을 공통 자료의 같은 구간에서 채점하고 기준선과 한 표로 냄. 모델을 학습하지 않음."""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
from collections import Counter
from datetime import date
from pathlib import Path

from learning_data.collection import packed
from learning_server import dataset, sample, starter

PARTS = ("train", "validation", "test")
METRICS = ("log_loss", "brier", "roc_auc", "accuracy")
LABELS = {"log_loss": "로그 손실", "brier": "Brier", "roc_auc": "ROC-AUC", "accuracy": "정확도"}
MIN_WRONG, MIN_PEOPLE = 50, 5
FEW_PEOPLE, FEW_LABEL = 3, "3개 미만"
VALIDATION_RESULTS = Path(__file__).resolve().parent.parent / ".local" / "validation-results"


def read_predictions(path):
    """CSV(event_id,probability,model_version 머리줄) 또는 JSONL 을 읽음. 확률·버전만 확인하고 행 내용은 돌려주지 않음."""
    path = Path(path).expanduser().resolve()
    if not path.is_relative_to(VALIDATION_RESULTS):
        path = sample.private_path(path)
    if path.suffix == ".csv":
        # Windows Excel 이 앞에 붙이는 BOM 을 머리줄로 읽지 않도록 utf-8-sig 로 읽음
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not {"event_id", "probability", "model_version"} <= set(reader.fieldnames or ()):
                raise ValueError("예측 파일 머리줄은 event_id,probability,model_version 으로 적어 주세요.")
            rows = list(reader)
    elif path.suffix == ".jsonl":
        rows = []
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if not isinstance(rows[-1], dict):
                raise ValueError("예측 파일 %d번째 줄을 {\"event_id\": ..., \"probability\": ..., \"model_version\": ...} 꼴로 적어 주세요." % number)
    else:
        raise ValueError("예측 파일은 .csv 또는 .jsonl 로 저장해 주세요.")
    versions = {row.get("model_version") for row in rows}
    if len(versions) != 1 or not isinstance(next(iter(versions)), str) or not next(iter(versions)):
        raise ValueError("model_version 은 파일 하나에 비어 있지 않은 한 값만 넣어 주세요.")
    counts = Counter(row.get("event_id") for row in rows)
    twice = sum(1 for value in counts.values() if value > 1)
    if twice:
        raise ValueError("같은 event_id 가 두 번 이상 나온 것이 %d개 있습니다." % twice)
    probabilities = {}
    for row in rows:
        value = row.get("probability")
        try:
            if isinstance(value, bool):
                raise ValueError
            value = float(value)
        except (TypeError, ValueError):
            value = float("nan")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("예측값에는 0 이상 1 이하의 유한한 숫자를 넣어 주세요.")
        probabilities[row.get("event_id")] = value
    return probabilities, next(iter(versions)), hashlib.sha256(path.read_bytes()).hexdigest()


def _mean_se(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1) / len(values))


def _values(targets, probabilities, constant):
    losses = [-(y * math.log(max(1e-12, p)) + (1 - y) * math.log(max(1e-12, 1 - p))) for y, p in zip(targets, probabilities)]
    squares = [(p - y) ** 2 for y, p in zip(targets, probabilities)]
    hits = [int((p >= 0.5) == bool(y)) for y, p in zip(targets, probabilities)]
    auc = None if constant else starter.metrics(targets, probabilities)["roc_auc"]
    return {"log_loss": None if constant else sum(losses) / len(losses), "brier": sum(squares) / len(squares),
            "roc_auc": auc, "accuracy": sum(hits) / len(hits)}, {"log_loss": losses, "brier": squares}


def measure(targets, probabilities, groups, constant=False):
    """네 지표와 표준오차 두 가지. 행 독립 표준오차는 정확도 √(p(1-p)/n), 로그 손실·Brier 는 행별 값의 표준편차/√n,
    AUC 는 Hanley–McNeil 근사임. 가명 묶음 표준오차는 가명 하나씩 빼고 다시 계산하는 잭나이프임.
    constant 는 늘 같은 값을 내는 기준선이라 로그 손실·AUC 를 내지 않음."""
    values, per_row = _values(targets, probabilities, constant)
    n = len(targets)
    rows = {"log_loss": None if constant else _mean_se(per_row["log_loss"]), "brier": _mean_se(per_row["brier"]),
            "accuracy": math.sqrt(values["accuracy"] * (1 - values["accuracy"]) / n), "roc_auc": None}
    auc = values["roc_auc"]
    if auc is not None:
        positive = sum(targets)
        negative = n - positive
        q1, q2 = auc / (2 - auc), 2 * auc ** 2 / (1 + auc)
        rows["roc_auc"] = math.sqrt((auc * (1 - auc) + (positive - 1) * (q1 - auc ** 2)
                                     + (negative - 1) * (q2 - auc ** 2)) / (positive * negative))
    names = sorted(set(groups))
    leave = {metric: [] for metric in METRICS}
    if len(names) >= 2:
        for name in names:
            keep = [i for i, group in enumerate(groups) if group != name]
            partial = _values([targets[i] for i in keep], [probabilities[i] for i in keep], constant)[0]
            for metric in METRICS:
                leave[metric].append(partial[metric])
    result = {}
    for metric in METRICS:
        part = leave[metric]
        group = None
        if part and values[metric] is not None and all(value is not None for value in part):
            center = sum(part) / len(part)
            group = math.sqrt((len(part) - 1) / len(part) * sum((value - center) ** 2 for value in part))
        result[metric] = {"value": values[metric], "se_row": rows[metric], "se_group": group}
    return result


def warning(wrong, people, shown=None, subject="이 구간은"):
    """경고 여부는 실제 가명 수로 정함. shown 이 "3개 미만"이면 문구의 가명 수 자리에 그 표시를 씀."""
    if wrong < MIN_WRONG or people < MIN_PEOPLE:
        if shown == FEW_LABEL:
            return "%s 오답 %d행, 가명 %s이라 모델 비교 근거로 쓰기 어렵습니다." % (subject, wrong, FEW_LABEL)
        return "%s 오답 %d행, 가명 %d개라 모델 비교 근거로 쓰기 어렵습니다." % (subject, wrong, people)
    return None


def baselines(train, rows, saved):
    """학습 구간으로 정한 기준선. 비율은 학습 평균 m 을 2건 섞어 (정답 수 + 2m) / (답 수 + 2) 로 평활함."""
    mean = sum(row["target"] for row in train) / len(train)

    def ratios(keys):
        totals = {}
        for row in train:
            for key in keys(row):
                hit = totals.setdefault(key, [0, 0])
                hit[0] += row["target"]
                hit[1] += 1
        return {key: (correct + 2 * mean) / (count + 2) for key, (correct, count) in totals.items()}

    question = ratios(lambda row: [row["question_id"]])
    concept = ratios(lambda row: row["concepts"])
    person = ratios(lambda row: [row["participant"]])
    return [
        ("majority", [float(mean >= 0.5)] * len(rows), True),
        ("overall-mean", [mean] * len(rows), False),
        ("per-question", [question.get(row["question_id"], mean) for row in rows], False),
        ("per-concept", [sum(concept.get(c, mean) for c in row["concepts"]) / len(row["concepts"])
                         if row["concepts"] else mean for row in rows], False),
        ("per-participant", [person.get(row["participant"], mean) for row in rows], False),
        ("past-concept-ratio-v1", [saved[row["event_id"]] for row in rows], False),
    ]


def evaluate(folder, track, split, predictions, *, inspect_all=True):
    if split not in PARTS:
        raise ValueError("채점할 구간은 train, validation, test 가운데 하나로 지정해 주세요.")
    probabilities, version, predictions_sha256 = read_predictions(predictions)
    if inspect_all:
        inspection = sample.inspect(folder)
    else:
        parts = ("train",) if split == "train" else ("train", split)
        inspection = sample.inspect(folder, track=track, parts=parts)
    report, content, manifest_sha256 = inspection
    if track not in content:
        raise ValueError("이 자료에는 %s 과목이 없습니다." % track)
    root = sample.private_path(folder)
    manifest_raw = (root / "manifest.json").read_bytes()
    baseline_raw = (root / "baseline.json").read_bytes()
    if (hashlib.sha256(manifest_raw).hexdigest() != manifest_sha256
            or hashlib.sha256(baseline_raw).hexdigest() != json.loads(manifest_raw)["files"]["baseline.json"]):
        raise ValueError("채점 도중 자료가 바뀌었습니다. 받은 원본을 확인해 주세요.")
    rows, train = content[track][split][0], content[track]["train"][0]
    expected = {row["event_id"] for row in rows}
    missing, extra = len(expected - set(probabilities)), len(set(probabilities) - expected)
    if missing:
        raise ValueError("예측 파일에 빠진 event_id 가 %d개 있습니다." % missing)
    if extra:
        raise ValueError("채점할 구간에 없는 event_id 가 %d개 있습니다." % extra)
    saved = {p["event_id"]: p["probability"] for p in json.loads(baseline_raw)[track][split]["predictions"]}
    lines = [(version, [probabilities[row["event_id"]] for row in rows], False)] + baselines(train, rows, saved)
    synthetic = report["synthetic"] is True
    cell, table, message = _bucket(rows, lines, synthetic, "이 구간은")
    # 처음 보는 문제는 학습 번호표에 없어 모델 입력에서 1번(UNK)이 되는 문제임. 학습 구간에서 드물어 번호표에서 뺀 문항도 들어감
    vocabulary = content[track][split][1]
    known, unit = set(vocabulary["questions"]), vocabulary.get("question_unit")
    picked = [i for i, row in enumerate(rows) if starter.question_token(row, unit) not in known]
    unseen_lines = [(name, [values[i] for i in picked], constant) for name, values, constant in lines]
    unseen = dict(zip(("cell", "table", "warning"),
                      _bucket([rows[i] for i in picked], unseen_lines, synthetic, "처음 보는 문제 행은")))
    unseen["cell"]["questions"] = len({starter.question_token(rows[i], unit) for i in picked})
    if not picked:
        unseen["warning"] = "처음 보는 문제 행이 없어 표를 내지 않습니다."
    elif unseen["warning"] is None and unseen["table"][0]["metrics"]["roc_auc"]["value"] is None:
        unseen["warning"] = "처음 보는 문제 행은 정답이나 오답 한쪽만 있어 ROC-AUC 를 계산할 수 없습니다."
    return {"dataset_manifest_sha256": manifest_sha256, "features_version": report["features_version"],
            "synthetic": report["synthetic"], "track": track, "split": split,
            "predictions_sha256": predictions_sha256, "model_version": version,
            "cell": cell, "table": table, "warning": message, "unseen": unseen}

def _previous_validation_version(root, model_name):
    prefix = f"{model_name}-v"
    pattern = re.compile(re.escape(prefix) + r"([0-9]+)")
    names = [path.name for path in root.glob(f"{prefix}*")]

    reports = list(root.glob("*score*.json"))
    reports += list(root.glob(f"{model_name}-run*/score.json"))
    for path in reports:
        try:
            report = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if isinstance(report, dict):
            names.append(report.get("model_version"))

    csv_files = list(root.glob("*-validation*.csv"))
    csv_files += list(root.glob(f"{model_name}-run*/predictions.csv"))
    for path in csv_files:
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream), {})
        except (OSError, ValueError, csv.Error):
            continue
        names.append(row.get("model_version"))

    versions = []
    for name in names:
        match = pattern.fullmatch(name) if isinstance(name, str) else None
        if match:
            versions.append(int(match.group(1)))
    return max(versions, default=0)


def score_validation(*, dataset_path, track, event_ids, probabilities, model_name, output_root=None):
    """검증 예측을 채점하고 예측 CSV, 결과 JSON, 저장 경로를 반환함."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", model_name):
        raise ValueError("모델 이름에는 소문자, 숫자, 하이픈을 써 주세요.")

    ids, values = list(event_ids), list(probabilities)
    if not ids or len(ids) != len(values):
        raise ValueError("풀이 ID와 예측 확률의 개수를 맞춰 주세요.")

    if output_root is None:
        day = date.today().isoformat()
        root = (VALIDATION_RESULTS / day).resolve()
        if root.parent != VALIDATION_RESULTS:
            raise ValueError("검증 결과는 프로젝트의 .local/validation-results 아래에 저장해 주세요.")
        model_name = f"{model_name}-{day}"
    else:
        root = sample.private_path(output_root)
    number = _previous_validation_version(root, model_name) + 1
    while True:
        version = f"{model_name}-v{number}"
        run_dir = root / version
        try:
            run_dir.mkdir(mode=0o700, parents=True)
        except FileExistsError:
            if not run_dir.exists():
                raise
            number += 1
        else:
            break

    predictions = run_dir / "predictions.csv"
    try:
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(("event_id", "probability", "model_version"))
        writer.writerows((key, value, version) for key, value in zip(ids, values))
        dataset.write_private(predictions, out.getvalue())

        result = evaluate(dataset_path, track, "validation", predictions, inspect_all=False)
        dataset.write_private(run_dir / "score.json", packed(result) + "\n")
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    return result, run_dir

def _bucket(rows, lines, synthetic, subject):
    """행 묶음 하나의 행 수·오답·가명 수와 표, 경고를 냄. 행이 없으면 표와 경고를 비움."""
    targets = [row["target"] for row in rows]
    groups = [row["participant"] for row in rows]
    wrong, people = len(rows) - sum(targets), len(set(groups))
    # 실제 자료에서 가명이 3개보다 적으면 가명 수를 가림. 가명 묶음 표준오차도 가명 1개일 때처럼 비워서 1개인지 2개인지 드러나지 않게 함
    # per-participant 줄은 값이 모두 같은지만 봐도 가명이 1개인지 2개인지 알 수 있어 "-" 로 냄
    masked = not synthetic and people < FEW_PEOPLE
    shown = FEW_LABEL if masked else people
    if masked:
        groups = [None] * len(rows)
    cell = {"rows": len(rows), "wrong": wrong, "participants": shown,
            "linked_rows": sum(1 for row in rows if (row.get("selection") or {}).get("pool") == "linked")}
    if not rows:
        return cell, [], None
    blank = {metric: {"value": None, "se_row": None, "se_group": None} for metric in METRICS}
    table = [{"name": name, "metrics": blank if masked and name == "per-participant"
              else measure(targets, values, groups, constant)} for name, values, constant in lines]
    return cell, table, warning(wrong, people, shown, subject)


def render(result):
    def cell(value):
        if value["value"] is None:
            return "-"
        group = "계산할 수 없음" if value["se_group"] is None else "%.4f" % value["se_group"]
        row = "-" if value["se_row"] is None else "%.4f" % value["se_row"]
        return "%.4f ± %s / %s" % (value["value"], row, group)

    info = result["cell"]
    people = info["participants"] if info["participants"] == FEW_LABEL else "%d개" % info["participants"]
    out = ["%s %s 구간: %d행, 오답 %d행, 가명 %s, 끼운 변형 %d행 (자료 버전 %s, 묶음 %s)" % (
        result["track"], result["split"], info["rows"], info["wrong"], people, info["linked_rows"],
        result["features_version"], result["dataset_manifest_sha256"][:12])]
    if result["synthetic"]:
        out.append("합성 자료입니다. 실행 확인용이며 모델 비교 근거로 쓰지 않습니다.")
    out.append("표의 값: 값 ± 행 독립 표준오차 / 가명 묶음 표준오차")

    def table(lines, message):
        if lines:
            out.append(" | ".join(["이름"] + [LABELS[metric] for metric in METRICS]))
        for line in lines:
            out.append(" | ".join([line["name"]] + [cell(line["metrics"][metric]) for metric in METRICS]))
        if message:
            out.append(message)

    table(result["table"], result["warning"])
    unseen = result.get("unseen")
    if unseen is not None:
        info = unseen["cell"]
        people = info["participants"] if info["participants"] == FEW_LABEL else "%d개" % info["participants"]
        out.append("")
        out.append("처음 보는 문제(학습 번호표에 없는 문제) %d개: %d행, 오답 %d행, 가명 %s, 끼운 변형 %d행" % (
            info["questions"], info["rows"], info["wrong"], people, info["linked_rows"]))
        table(unseen["table"], unseen["warning"])
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="예측 파일을 공통 자료의 같은 구간에서 기준선과 함께 채점합니다.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--track", choices=sample.TRACKS, required=True)
    parser.add_argument("--split", choices=PARTS, default="validation",
                        help="기본은 검증 구간입니다. 평가 구간(test)은 설정을 모두 정한 뒤 한 번만 채점합니다")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--out", help="결과 JSON. Git 저장소 밖의 새 파일만 받습니다")
    args = parser.parse_args()
    try:
        target = None
        if args.out:
            target = sample.private_path(args.out)
            if target.exists():
                raise ValueError("이미 있는 결과 파일은 덮어쓰지 않습니다. 다른 파일 이름을 지정해 주세요.")
        result = evaluate(args.dataset, args.track, args.split, args.predictions)
        print(render(result))
        if target is not None:
            dataset.write_private(target, packed(result) + "\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
