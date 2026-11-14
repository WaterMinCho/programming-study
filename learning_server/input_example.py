# -*- coding: utf-8 -*-
"""파일 해시를 확인하고 딥러닝 모델에 넘길 배열을 표준 라이브러리로 준비함."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

from learning_server.starter import question_token
from learning_server.dataset import SUPPORTED_FEATURES_VERSIONS, author_difficulty
from learning_data import generation


def load(folder, track, part):
    root = Path(folder)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if track not in manifest["tracks"] or part not in ("train", "validation", "test"):
        raise ValueError("자료의 과목과 분할 이름을 확인해 주세요.")
    def verified(path, checksum):
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError("자료가 바뀌었습니다. 파일 해시를 확인해 주세요.")
        return raw
    records = json.loads(verified(root / "records/manifest.json", manifest["records_manifest_sha256"]))
    if (type(manifest.get("features_version")) is not int
            or type(records.get("features_version")) is not int
            or manifest["features_version"] not in SUPPORTED_FEATURES_VERSIONS
            or records.get("features_version") != manifest["features_version"]):
        raise ValueError("이전 이력 집계로 만든 자료입니다. 원본을 보존하고 새 폴더에 공통 자료를 다시 준비해 주세요.")
    vocabulary = json.loads(verified(root / "vocabulary.json", manifest["files"]["vocabulary.json"]))[track]
    name = track + "-" + part + ".jsonl"
    rows = [json.loads(line) for line in verified(root / "records" / name, records["files"][name]["sha256"]).splitlines()]
    return rows, vocabulary


def batch(rows, vocabulary, length=32):
    if not 1 <= length <= 128:
        raise ValueError("풀이 이력 길이는 1~128로 지정해 주세요.")
    questions = {value: n for n, value in enumerate(vocabulary["questions"])}
    concepts = {value: n for n, value in enumerate(vocabulary["concepts"])}
    courses = {value: n for n, value in enumerate(vocabulary.get("courses", ["<PAD>", "<UNK>"]))}
    width = len(concepts)
    def multi_hot(names):
        values = [0] * width
        for name in names:
            values[concepts.get(name, 1)] = 1
        return values
    inputs = {name: [] for name in ("questions", "concepts", "results", "mask", "lengths", "query_question",
                                    "query_concepts", "query_gap_seconds", "query_gap_known", "courses", "query_course",
                                    "difficulties", "difficulty_known", "query_difficulty", "query_difficulty_known")}
    for row in rows:
        history = row["features"]["sequence_history"][-length:]
        size = len(history)
        difficulties = [author_difficulty(past) for past in history]
        query_difficulty = author_difficulty(row)
        inputs["difficulties"].append([value or 0 for value in difficulties] + [0] * (length-size))
        inputs["difficulty_known"].append([value is not None for value in difficulties] + [False] * (length-size))
        inputs["query_difficulty"].append(query_difficulty or 0)
        inputs["query_difficulty_known"].append(query_difficulty is not None)
        inputs["questions"].append([questions.get(question_token(past), 1) for past in history] + [0] * (length-size))
        inputs["concepts"].append([multi_hot(past["concepts"]) for past in history] + [[0]*width for _ in range(length-size)])
        inputs["courses"].append([courses.get(past.get("course"), 1) for past in history] + [0] * (length-size))
        inputs["query_course"].append(courses.get(row.get("course"), 1))
        inputs["results"].append([past["result"] for past in history] + [0] * (length-size))
        inputs["mask"].append([True]*size + [False]*(length-size))
        inputs["lengths"].append(size)
        inputs["query_question"].append(questions.get(question_token(row), 1))
        inputs["query_concepts"].append(multi_hot(row["concepts"]))
        gaps, known = [0.0]*width, [False]*width
        now = datetime.datetime.fromisoformat(row["prediction_at"]) if row.get("prediction_at") else None
        grouped = {}
        for name, previous in row["features"]["observed_history"].items():
            if now is not None and previous["last_at"] is not None:
                elapsed = (now - datetime.datetime.fromisoformat(previous["last_at"])).total_seconds()
                if elapsed < 0:
                    raise ValueError("풀이 간격이 음수입니다. 원본 시각을 확인해 주세요.")
                index = concepts.get(name, 1)
                grouped.setdefault(index, []).append(elapsed)
        for index, values in grouped.items():
            gaps[index], known[index] = min(values), True
        inputs["query_gap_seconds"].append(gaps)
        inputs["query_gap_known"].append(known)
    # 출제 재현용 조건은 숫자 배열과 함께 반환함. 답·해설·현재 정오답을 넣지 않음.
    provenance = {"query": [], "history": []}
    for row in rows:
        value = row.get("generation")
        provenance["query"].append(generation.validate(value) if value is not None else None)
        history = row["features"]["sequence_history"][-length:]
        provenance["history"].append(
            [generation.validate(past["generation"]) if past.get("generation") is not None else None for past in history]
            + [None] * (length - len(history)))
    return {"inputs": inputs, "question_provenance": provenance, "targets": [row["target"] for row in rows],
            "event_ids": [row["event_id"] for row in rows]}


def main():
    parser = argparse.ArgumentParser(description="공통 입력의 모양과 예를 확인합니다.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--track", choices=("ai", "python"), required=True)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="train")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--length", type=int, default=32)
    args = parser.parse_args()
    try:
        if args.batch_size < 1:
            raise ValueError("묶음 크기는 1 이상으로 지정해 주세요.")
        rows, vocabulary = load(args.dataset, args.track, args.split)
        result = batch(rows[:args.batch_size], vocabulary, args.length)
        print(json.dumps({"batch": len(result["targets"]), "history_length": args.length,
                          "concept_width": len(vocabulary["concepts"]), "example": result}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
