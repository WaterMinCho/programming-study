# -*- coding: utf-8 -*-
"""같은 묶음의 비공개 자료를 확인하고 모델 입력 시험용 샘플을 저장함."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random

from learning_data.collection import packed
from learning_server import dataset, input_example

PARTS = ("train", "validation", "test")
TRACKS = ("python", "ai")


def private_path(path):
    path = Path(path).expanduser().resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("자료와 샘플은 Git 저장소 밖에 보관해 주세요.")
    return path


def inspect(folder):
    root = private_path(folder)
    path = root / "manifest.json"
    if not path.is_file():
        raise ValueError("선택한 폴더에 manifest.json이 없습니다. 압축을 푼 뒤 recorded-python 또는 synthetic 폴더를 지정해 주세요.")
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if (manifest.get("format") != 1 or type(manifest.get("features_version")) is not int
            or manifest["features_version"] not in dataset.SUPPORTED_FEATURES_VERSIONS):
        raise ValueError("지원하는 공통 입력 버전의 자료를 지정해 주세요.")
    tracks = manifest.get("tracks", [])
    if not tracks or len(set(tracks)) != len(tracks) or any(track not in TRACKS for track in tracks):
        raise ValueError("자료에 포함된 과목 목록을 확인해 주세요.")
    if not {"vocabulary.json", "baseline.json"} <= set(manifest["files"]):
        raise ValueError("자료의 번호표와 기준 결과 파일 목록을 확인해 주세요.")
    for name, checksum in manifest["files"].items():
        if name not in ("vocabulary.json", "baseline.json", "legacy-provenance.json"):
            raise ValueError("공통 자료의 파일 목록을 확인해 주세요.")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != checksum:
            raise ValueError("자료가 바뀌었습니다. 받은 원본과 파일 해시를 확인해 주세요.")
    records_raw = (root / "records/manifest.json").read_bytes()
    if hashlib.sha256(records_raw).hexdigest() != manifest["records_manifest_sha256"]:
        raise ValueError("자료 목록의 해시가 바뀌었습니다. 받은 원본을 확인해 주세요.")
    record_manifest = json.loads(records_raw)
    if any(manifest.get(key) != record_manifest.get(key) for key in ("format", "features_version", "source", "synthetic")):
        raise ValueError("자료의 출처와 입력 버전 표시가 맞지 않습니다.")
    if set(record_manifest["files"]) != {track + "-" + part + ".jsonl" for track in tracks for part in PARTS}:
        raise ValueError("자료의 과목과 파일 목록이 맞지 않습니다.")
    content, counts = {}, {}
    for track in tracks:
        content[track], counts[track] = {}, {}
        for part in PARTS:
            rows, vocabulary = input_example.load(root, track, part)
            if len(rows) != record_manifest["files"][track + "-" + part + ".jsonl"]["rows"]:
                raise ValueError("자료 목록의 행 수와 실제 파일이 맞지 않습니다.")
            content[track][part] = (rows, vocabulary)
            counts[track][part] = len(rows)
    if path.read_bytes() != raw:
        raise ValueError("확인 도중 자료 버전이 바뀌었습니다. 같은 자료 묶음을 새 폴더에서 확인해 주세요.")
    report = {"status": "verified", "features_version": manifest["features_version"],
              "synthetic": manifest["synthetic"], "source": manifest["source"], "tracks": counts}
    return report, content, hashlib.sha256(raw).hexdigest()


def write_sample(folder, track, part, size, seed, length, destination):
    if track not in TRACKS or part not in PARTS:
        raise ValueError("과목과 학습·검증·평가 구분을 확인해 주세요.")
    if type(size) is not int or size < 1 or type(seed) is not int:
        raise ValueError("샘플 수는 1 이상의 정수, 시드는 정수로 지정해 주세요.")
    target = private_path(destination)
    if target.exists():
        raise ValueError("이미 있는 샘플은 덮어쓰지 않습니다. 다른 파일 이름을 지정해 주세요.")
    report, content, source_hash = inspect(folder)
    if track not in content:
        raise ValueError("이 자료에는 %s 과목이 없습니다. 포함 과목: %s" % (track, ", ".join(content)))
    rows, vocabulary = content[track][part]
    if size > len(rows):
        raise ValueError("%s/%s에는 %d건이 있습니다. 샘플 수를 줄이거나 다른 자료를 지정해 주세요." % (track, part, len(rows)))
    indices = sorted(random.Random(seed).sample(range(len(rows)), size))
    chosen = [rows[index] for index in indices]
    result = input_example.batch(chosen, vocabulary, length)
    if (len(result["targets"]) != size or len(result["event_ids"]) != size or
            any(len(values) != size for values in result["inputs"].values())):
        raise ValueError("입력·정답·샘플 번호의 개수가 맞지 않습니다.")
    if (result["event_ids"] != [row["event_id"] for row in chosen] or
            result["targets"] != [row["target"] for row in chosen]):
        raise ValueError("샘플 번호·정답의 값이나 순서가 원본과 맞지 않습니다.")
    changed = copy.deepcopy(chosen)
    for row in changed:
        row["target"] = 1 - row["target"]
    changed_batch = input_example.batch(changed, vocabulary, length)
    if (result["inputs"] != changed_batch["inputs"]
            or result["question_provenance"] != changed_batch["question_provenance"]):
        raise ValueError("이번 정답이 모델 입력에 섞였습니다. 입력과 정답을 분리해 주세요.")
    provenance = result["question_provenance"]
    if len(provenance["query"]) != size or len(provenance["history"]) != size:
        raise ValueError("생성 문항 출처의 행 수가 입력과 다릅니다.")
    inputs = result["inputs"]
    width = len(vocabulary["concepts"])
    for index, (mask, count) in enumerate(zip(inputs["mask"], inputs["lengths"])):
        if count != min(len(chosen[index]["features"]["sequence_history"]), length):
            raise ValueError("풀이 이력의 길이가 원본과 맞지 않습니다.")
        if not 0 <= count <= length:
            raise ValueError("실제 풀이 이력의 길이를 확인해 주세요.")
        if any(len(inputs[name][index]) != length for name in ("questions", "courses", "results", "concepts", "mask", "difficulties", "difficulty_known")):
            raise ValueError("풀이 이력 배열의 길이가 맞지 않습니다.")
        if mask != [True] * count + [False] * (length - count):
            raise ValueError("실제 이력과 빈 자리의 표시가 맞지 않습니다.")
        if len(provenance["history"][index]) != length or any(value is not None for value in provenance["history"][index][count:]):
            raise ValueError("생성 문항 출처의 이력 길이와 빈 자리를 확인해 주세요.")
        if any(value != 0 for name in ("questions", "courses", "results", "difficulties", "difficulty_known") for value in inputs[name][index][count:]):
            raise ValueError("빈 자리에 문제·과정·정오답·난이도 값이 들어 있습니다.")
        if (any(len(row) != width for row in inputs["concepts"][index]) or
                any(len(inputs[name][index]) != width for name in ("query_concepts", "query_gap_seconds", "query_gap_known"))):
            raise ValueError("개념 배열의 너비가 번호표와 맞지 않습니다.")
        if any(value != 0 for row in inputs["concepts"][index][count:] for value in row):
            raise ValueError("빈 자리에 개념 값이 들어 있습니다.")
    value = {"format": 1, "purpose": "input-smoke-test", "features_version": report["features_version"],
             "synthetic": report["synthetic"], "source_manifest_sha256": source_hash,
             "track": track, "split": part, "seed": seed, "history_length": length,
             "vocabulary": vocabulary, "batch": result}
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    dataset.write_private(target, packed(value) + "\n")
    if json.loads(target.read_text(encoding="utf-8")) != value:
        raise ValueError("샘플을 저장한 뒤 다시 읽어 확인하지 못했습니다.")
    return {"status": "input_checked", "features_version": report["features_version"], "synthetic": report["synthetic"],
            "track": track, "split": part, "sample_rows": size, "seed": seed,
            "shapes": {"questions": [len(inputs["questions"]), len(inputs["questions"][0])],
                       "concepts": [len(inputs["concepts"]), len(inputs["concepts"][0]), len(inputs["concepts"][0][0])],
                       "mask": [len(inputs["mask"]), len(inputs["mask"][0])],
                       "query_concepts": [len(inputs["query_concepts"]), len(inputs["query_concepts"][0])],
                       "difficulties": [size, length],
                       "query_difficulty": [size],
                       "targets": [len(result["targets"])]},
            "empty_histories": sum(count == 0 for count in inputs["lengths"]),
            "truncated_histories": sum(len(row["features"]["sequence_history"]) > length for row in chosen),
            "target_separation": "passed", "padding": "passed"}


def main():
    parser = argparse.ArgumentParser(description="비공개 자료를 확인하고 입력 시험용 샘플을 만듭니다.")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "sample"):
        sub = commands.add_parser(command)
        sub.add_argument("--dataset", required=True)
        if command == "sample":
            sub.add_argument("--track", choices=TRACKS, required=True)
            sub.add_argument("--split", choices=PARTS, default="train")
            sub.add_argument("--size", type=int, default=4)
            sub.add_argument("--seed", type=int, default=42)
            sub.add_argument("--length", type=int, default=32)
            sub.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = inspect(args.dataset)[0]
        else:
            result = write_sample(args.dataset, args.track, args.split, args.size, args.seed, args.length, args.out)
        print(packed(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
