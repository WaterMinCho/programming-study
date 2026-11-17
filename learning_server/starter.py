# -*- coding: utf-8 -*-
"""기존 자료 생성기를 재사용해 세 모델의 공통 입력과 비교 자료를 준비함."""
import argparse
import hashlib
import json
import math
import numbers
import os
from collections import Counter
from pathlib import Path

from learning_data.collection import inside, packed
from learning_server import dataset


QUESTION_UNITS = ("question_id",)
MIN_COUNT = 2


def question_token(row, unit="question_id"):
    """번호표 토큰. 버전 8 은 문항 id 하나, unit 이 None 이면 버전 4~7 의 (문항 id, 문항 버전) 쌍임.
    AI 문항 버전 해시는 seed·보기 순서·실행 코드 해시가 들어가 화면에 낼 때마다 바뀌므로 버전 8 에서 토큰에서 뺌."""
    if unit is None:
        return packed([row["question_id"], row.get("question_revision")])
    if unit not in QUESTION_UNITS:
        raise ValueError("번호표 규칙을 확인해 주세요: %s" % unit)
    return row["question_id"]


def metrics(targets, probabilities):
    def scalar(value):
        if getattr(value, "ndim", None) == 0:
            try:
                return value.item()
            except (AttributeError, TypeError, ValueError):
                pass
        return value

    size = len(targets)
    if size != len(probabilities):
        raise ValueError("정답과 예측값을 같은 개수로 전달해 주세요.")
    targets, probabilities = [scalar(value) for value in targets], [scalar(value) for value in probabilities]
    for index, target in enumerate(targets, 1):
        if not isinstance(target, numbers.Real) or target not in (0, 1):
            raise ValueError("%d번째 정답에는 숫자 0 또는 1을 넣어 주세요." % index)
    for index, probability in enumerate(probabilities, 1):
        if not isinstance(probability, numbers.Real) or not 0 <= probability <= 1 or not math.isfinite(probability):
            raise ValueError("%d번째 예측값에는 0 이상 1 이하의 유한한 숫자를 넣어 주세요." % index)
    if not size:
        return {"rows": 0, "brier": None, "log_loss": None, "roc_auc": None}
    targets, probabilities = [int(value) for value in targets], [float(value) for value in probabilities]
    brier = sum((p - y) ** 2 for y, p in zip(targets, probabilities)) / size
    loss = -sum(y * math.log(max(1e-12, p)) + (1-y) * math.log(max(1e-12, 1-p)) for y, p in zip(targets, probabilities)) / size
    positive = sum(targets)
    auc = None
    if 0 < positive < size:
        ordered = sorted(zip(probabilities, targets))
        ranks, start = 0, 0
        while start < size:
            end = start + 1
            while end < size and ordered[end][0] == ordered[start][0]:
                end += 1
            ranks += (start + 1 + end) / 2 * sum(y for _, y in ordered[start:end])
            start = end
        auc = (ranks - positive * (positive + 1) / 2) / (positive * (size - positive))
    return {"rows": size, "brier": brier, "log_loss": loss, "roc_auc": auc}


def baseline(rows):
    predictions = []
    for row in rows:
        histories = list(row["features"]["observed_history"].values())
        probability = sum((h["correct"] + 1) / (h["attempts"] + 2) for h in histories) / len(histories)
        predictions.append({"event_id": row["event_id"], "question_id": row["question_id"],
                            "question_revision": row["question_revision"], "probability": probability,
                            "model_version": "past-concept-ratio-v1"})
    groups = sorted({row.get("course") or "unrecorded" for row in rows})
    by_course = {course: metrics([row["target"] for row in rows if (row.get("course") or "unrecorded") == course],
                                [p["probability"] for row, p in zip(rows, predictions) if (row.get("course") or "unrecorded") == course])
                 for course in groups}
    return {"metrics": metrics([r["target"] for r in rows], [p["probability"] for p in predictions]),
            "by_course": by_course, "predictions": predictions}


def write_starter(events, destination, source_sha256=None, min_count=MIN_COUNT, exclude_linked=False):
    """min_count 는 학습 구간에서 예측할 문제로 나온 횟수의 하한임. 이보다 적게 나온 문항은 번호표에서 빼서 학습·검증·평가 모두 UNK 로 감.
    학습 이력에만 나오고 예측할 문제로는 0번인 문항도 min_count 가 2 이상이면 빠지고, min_count 가 1 이면 학습 구간 문항을 모두 남김.
    횟수는 학습 구간만 세므로 검증·평가 구간의 문항 id 와 정답은 번호표에 영향을 주지 않음.
    기본값 2 는 학습으로 비교해 보지 않은 값임. 학습 중에도 UNK 번호가 나오게 하려고 고른 값이고 비교 실험으로 다시 정함."""
    events = list(events)
    if type(min_count) is not int or min_count < 1:
        raise ValueError("드문 문항 기준 횟수는 1 이상의 정수로 지정해 주세요.")
    root = Path(__file__).resolve().parent.parent
    destination = Path(destination)
    if inside(destination, root):
        raise ValueError("공통 학습 자료는 공개 저장소 밖에 저장해 주세요.")
    os.mkdir(destination, mode=0o700)
    record_manifest = dataset.write_dataset(events, str(destination / "records"), source_sha256=source_sha256,
                                            exclude_linked=exclude_linked)
    tracks = sorted({name.split("-", 1)[0] for name in record_manifest["files"]})
    vocabulary, comparisons = {}, {}
    for track in tracks:
        rows = {part: [json.loads(line) for line in (destination / "records" / (track + "-" + part + ".jsonl")).read_text(encoding="utf-8").splitlines()]
                for part in ("train", "validation", "test")}
        train = rows["train"]
        counts = Counter(question_token(r) for r in train)
        questions = set(counts)
        concepts = {c for r in train for c in r["concepts"]}
        courses = {r["course"] for r in train if r.get("course") is not None}
        for row in train:
            for past in row["features"]["sequence_history"]:
                questions.add(question_token(past))
                concepts.update(past["concepts"])
                if past.get("course") is not None:
                    courses.add(past["course"])
        kept = questions if min_count == 1 else {token for token in questions if counts[token] >= min_count}
        vocabulary[track] = {"questions": ["<PAD>", "<UNK>"] + sorted(kept),
                             "question_unit": "question_id", "question_min_count": min_count,
                             "rare_questions": len(questions - kept),
                             "concepts": ["<PAD>", "<UNK>"] + sorted(concepts),
                             "courses": ["<PAD>", "<UNK>"] + sorted(courses)}
        comparisons[track] = {part: baseline(part_rows) for part, part_rows in rows.items()}
    files = {"vocabulary.json": vocabulary, "baseline.json": comparisons}
    if events and events[0].get("source_type") == "legacy_profile":
        files["legacy-provenance.json"] = events[0]
    manifest = {"format": 1, "features_version": dataset.FEATURES_VERSION, "history_limit": 128, "source": record_manifest["source"],
                "synthetic": record_manifest["synthetic"], "tracks": tracks, "source_sha256": source_sha256,
                "records_manifest_sha256": hashlib.sha256((destination / "records/manifest.json").read_bytes()).hexdigest(),
                "files": {}}
    for name, content in files.items():
        path = destination / name
        dataset.write_private(path, packed(content) + "\n")
        assert json.loads(path.read_text(encoding="utf-8")) == content
        manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    dataset.write_private(destination / "manifest.json", packed(manifest) + "\n")
    if json.loads((destination / "manifest.json").read_text(encoding="utf-8")) != manifest:
        raise ValueError("공통 자료의 저장 결과를 확인하지 못했습니다.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="기존 풀이 자료로 모델 개발용 공통 입력을 준비합니다.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="이미 내보낸 수집 JSONL")
    source.add_argument("--profile", help="사용 허락을 받은 기존 파이썬 profile.json")
    source.add_argument("--synthetic", action="store_true")
    parser.add_argument("--agree", action="store_true", help="기존 기록 소유자의 연구 사용 동의를 확인합니다")
    parser.add_argument("--timezone", help="기존 기록에 시간대가 없을 때 적용할 가정")
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-count", type=int, default=MIN_COUNT,
                        help="학습 구간에서 예측할 문제로 나온 횟수가 이 값보다 적은 문항은 UNK 로 보냅니다. 2 이상이면 이력에만 나온 문항도 보내고, 1 이면 모두 남깁니다")
    parser.add_argument("--exclude-linked", action="store_true", help="틀린 문항 뒤에 끼운 변형 행을 예측 대상에서 뺍니다")
    args = parser.parse_args()
    try:
        raw = None
        if args.profile:
            if not args.agree or not args.timezone:
                raise ValueError("기존 기록은 소유자의 동의를 확인하고 --agree와 --timezone을 지정해 주세요.")
            import adaptive
            from learning_server.legacy import profile_events
            raw = Path(args.profile).read_bytes()
            events = profile_events(json.loads(raw), adaptive.catalog(), args.timezone)
        elif args.input:
            raw = Path(args.input).read_bytes()
            events = [json.loads(line) for line in raw.splitlines()]
        else:
            events = dataset.synthetic_events()
        result = write_starter(events, args.out, hashlib.sha256(raw).hexdigest() if raw is not None else None,
                               args.min_count, args.exclude_linked)
        print("공통 입력과 비교 자료를 저장하고 다시 읽어 확인했습니다. %s" % args.out)
        print(packed(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
