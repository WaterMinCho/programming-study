# -*- coding: utf-8 -*-
"""기존 자료 생성기를 재사용해 세 모델의 공통 입력과 비교 자료를 준비함."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from aiprep.collection import inside, packed
from learning_server import dataset


def question_token(row):
    return packed([row["question_id"], row.get("question_revision")])


def metrics(targets, probabilities):
    size = len(targets)
    if not size:
        return {"rows": 0, "brier": None, "log_loss": None, "roc_auc": None}
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


def write_starter(events, destination, source_sha256=None):
    events = list(events)
    root = Path(__file__).resolve().parent.parent
    destination = Path(destination)
    if inside(destination, root):
        raise ValueError("공통 학습 자료는 공개 저장소 밖에 저장해 주세요.")
    os.mkdir(destination, mode=0o700)
    record_manifest = dataset.write_dataset(events, str(destination / "records"), source_sha256=source_sha256)
    tracks = sorted({name.split("-", 1)[0] for name in record_manifest["files"]})
    vocabulary, comparisons = {}, {}
    for track in tracks:
        rows = {part: [json.loads(line) for line in (destination / "records" / (track + "-" + part + ".jsonl")).read_text(encoding="utf-8").splitlines()]
                for part in ("train", "validation", "test")}
        train = rows["train"]
        questions = {question_token(r) for r in train}
        concepts = {c for r in train for c in r["concepts"]}
        courses = {r["course"] for r in train if r.get("course") is not None}
        for row in train:
            for past in row["features"]["sequence_history"]:
                questions.add(question_token(past))
                concepts.update(past["concepts"])
                if past.get("course") is not None:
                    courses.add(past["course"])
        vocabulary[track] = {"questions": ["<PAD>", "<UNK>"] + sorted(questions),
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
        result = write_starter(events, args.out, hashlib.sha256(raw).hexdigest() if raw is not None else None)
        print("공통 입력과 비교 자료를 저장하고 다시 읽어 확인했습니다. %s" % args.out)
        print(packed(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
