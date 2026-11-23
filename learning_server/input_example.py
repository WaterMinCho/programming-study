# -*- coding: utf-8 -*-
"""파일 해시를 확인하고 딥러닝 모델에 넘길 배열을 표준 라이브러리로 준비함."""
import argparse
import copy
import datetime
import hashlib
import json
import random
from pathlib import Path

from learning_server.starter import QUESTION_UNITS, question_token
from learning_server.dataset import FEATURES_VERSION, SUPPORTED_FEATURES_VERSIONS, author_difficulty
from learning_data import generation

HIDE_RATE = 0.1

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
    newer(manifest.get("features_version"))
    if (type(manifest.get("features_version")) is not int
            or type(records.get("features_version")) is not int
            or manifest["features_version"] not in SUPPORTED_FEATURES_VERSIONS
            or records.get("features_version") != manifest["features_version"]):
        raise ValueError("이전 이력 집계로 만든 자료입니다. 원본을 보존하고 새 폴더에 공통 자료를 다시 준비해 주세요.")
    vocabulary = json.loads(verified(root / "vocabulary.json", manifest["files"]["vocabulary.json"]))[track]
    unit = vocabulary.get("question_unit")
    # 버전 4~7 번호표에는 규칙이 없고 (문항 id, 문항 버전) 쌍으로 읽음. 버전 8 은 규칙이 있어야 함
    if unit is not None and unit not in QUESTION_UNITS or unit is None and manifest["features_version"] >= 8:
        raise ValueError("버전 8 자료의 번호표 규칙이 없거나 모르는 값입니다. 같은 묶음의 원본을 다시 받아 주세요.")
    name = track + "-" + part + ".jsonl"
    rows = [json.loads(line) for line in verified(root / "records" / name, records["files"][name]["sha256"]).splitlines()]
    return rows, vocabulary


def newer(version):
    if type(version) is int and version > FEATURES_VERSION:
        raise ValueError("더 새 도구로 만든 자료입니다. 저장소를 최신 main 으로 갱신한 뒤 읽어 주세요.")


def batch(rows, vocabulary, length=32):
    result = _encode(rows, vocabulary, length)
    return dict(result, targets=[row["target"] for row in rows], event_ids=[row["event_id"] for row in rows])


def candidate_batch(candidates, vocabulary, snapshot, length=32):
    """추천 시각에 공개된 이력과 정답 없는 후보를 batch와 같은 배열로 바꿈.
    snapshot은 prediction_at과 features를 담음. 공개 시각·철회·정정 반영은 호출자가 맡음.
    후보 순서와 candidate_id를 유지하며 targets나 답안 기록용 event_id는 만들지 않음."""
    if set(snapshot) != {"prediction_at", "features"}:
        raise ValueError("추천 이력에는 prediction_at과 features만 넣어 주세요.")

    def instant(value):
        try:
            result = datetime.datetime.fromisoformat(value)
            if result.tzinfo is not None:
                return result
        except (TypeError, ValueError):
            pass
        raise ValueError("추천 시각과 이력 시각에 시간대를 포함해 주세요.")

    cutoff = instant(snapshot["prediction_at"])
    features = snapshot["features"]
    if set(features) != {"sequence_history", "observed_history"}:
        raise ValueError("추천 이력에는 sequence_history와 observed_history를 넣어 주세요.")
    previous = None
    for past in features["sequence_history"]:
        at = instant(past["at"])
        if at >= cutoff or previous is not None and at < previous:
            raise ValueError("지난 풀이를 추천 시각보다 앞선 순서로 준비해 주세요.")
        if type(past["result"]) is not int or past["result"] not in (0, 1):
            raise ValueError("지난 풀이에는 채점이 끝난 정오답만 넣어 주세요.")
        previous = at
    for observed in features["observed_history"].values():
        if observed["last_at"] is not None and instant(observed["last_at"]) >= cutoff:
            raise ValueError("개념별 마지막 풀이 시각은 추천 시각보다 앞서야 합니다.")

    fields = {"candidate_id", "question_id", "question_revision", "concepts", "course", "difficulty", "generation"}
    rows, ids = [], []
    for candidate in candidates:
        if set(candidate) - fields:
            raise ValueError("문제 후보에는 문항 정보만 넣고 정답·채점 결과는 빼 주세요.")
        for key in ("candidate_id", "question_id"):
            if not isinstance(candidate.get(key), str) or not candidate[key].strip() or candidate[key] in ("<PAD>", "<UNK>"):
                raise ValueError("후보와 문항에는 비어 있지 않은 고유번호를 넣어 주세요.")
        if candidate["candidate_id"] in ids:
            raise ValueError("candidate_id가 중복됩니다. 후보마다 다른 값을 넣어 주세요.")
        concepts = candidate.get("concepts")
        if not isinstance(concepts, list) or any(not isinstance(name, str) or not name.strip()
                                                or name in ("<PAD>", "<UNK>") for name in concepts):
            raise ValueError("후보의 concepts에는 개념 이름 목록을 넣어 주세요.")
        ids.append(candidate["candidate_id"])
        candidate_features = {"sequence_history": features["sequence_history"],
                              "observed_history": {name: value for name, value in features["observed_history"].items()
                                                   if name in concepts}}
        rows.append(dict(candidate, prediction_at=snapshot["prediction_at"], features=candidate_features))
    result = _encode(rows, vocabulary, length)
    return dict(result, candidate_ids=ids, prediction_at=snapshot["prediction_at"])


def _encode(rows, vocabulary, length):
    if not 1 <= length <= 128:
        raise ValueError("풀이 이력 길이는 1~128로 지정해 주세요.")
    questions = {value: n for n, value in enumerate(vocabulary["questions"])}
    unit = vocabulary.get("question_unit")
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
        inputs["questions"].append([questions.get(question_token(past, unit), 1) for past in history] + [0] * (length-size))
        inputs["concepts"].append([multi_hot(past["concepts"]) for past in history] + [[0]*width for _ in range(length-size)])
        inputs["courses"].append([courses.get(past.get("course"), 1) for past in history] + [0] * (length-size))
        inputs["query_course"].append(courses.get(row.get("course"), 1))
        inputs["results"].append([past["result"] for past in history] + [0] * (length-size))
        inputs["mask"].append([True]*size + [False]*(length-size))
        inputs["lengths"].append(size)
        inputs["query_question"].append(questions.get(question_token(row, unit), 1))
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
    return {"inputs": inputs, "question_provenance": provenance}


def hide_questions(rows, vocabulary, rate=HIDE_RATE, seed=0, by="question"):
    """학습할 때만 쓰는 함수. rows 의 복사본에서 문항 일부의 id 를 번호표의 <UNK> 로 바꿔 돌려주고 rows 는 바꾸지 않음.
    batch() 가 돌려받은 행을 읽으면 바뀐 자리의 문제 번호가 1번이 되고 개념·난이도·과정 칸은 그대로 남음.
    by="question" 은 번호표에 있는 문항 가운데 rate 비율만큼 골라 이번 문제와 지난 풀이 양쪽에서 같이 바꿈.
    rate가 양수이고 후보가 있으면 적어도 문항 하나를 바꿈. rate가 0이면 바꾸지 않음.
    학습 때 한 번도 못 본 문항(ROS2 같은 새 과목의 문항)은 이번 문제와 이력 모두 1번으로 들어오므로 그 꼴을 흉내 냄.
    by="slot" 은 이번 문제와 지난 풀이의 자리마다 따로 rate 확률로 바꿈.
    같은 seed 면 같은 문항이 바뀜. 에폭마다 seed 를 바꾸면 다시 고르며 이전과 같은 문항이 뽑힐 수도 있음.
    기본 비율 0.1 은 학습으로 비교해 보지 않은 값임. 문항 10개 중 9개의 번호 정보를 남기면서 1번 임베딩도 학습되게 하려고 고른 값이고 비교 실험으로 다시 정함."""
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= rate <= 1:
        raise ValueError("바꿀 비율은 0 이상 1 이하의 숫자로 지정해 주세요.")
    if type(seed) is not int:
        raise ValueError("바꾸기 시드는 정수로 지정해 주세요.")
    if by not in ("question", "slot"):
        raise ValueError("바꾸는 단위는 question 또는 slot 으로 지정해 주세요.")
    unknown, unit = vocabulary["questions"][1], vocabulary.get("question_unit")
    known = set(vocabulary["questions"][2:])
    rows = copy.deepcopy(rows)
    chooser = random.Random(seed)
    def slots():
        for row in rows:
            yield row
            yield from row["features"]["sequence_history"]
    if by == "slot":
        for item in slots():
            if chooser.random() < rate:
                item["question_id"] = unknown
        return rows
    pool = sorted({question_token(item, unit) for item in slots()} & known)
    count = max(1, round(rate * len(pool))) if pool and rate > 0 else 0
    chosen = set(chooser.sample(pool, count))
    for item in slots():
        if question_token(item, unit) in chosen:
            item["question_id"] = unknown
    return rows


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
