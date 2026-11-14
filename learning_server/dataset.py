# -*- coding: utf-8 -*-
"""수집 파일을 과목별 시간순 학습·검증·평가 자료로 만듦. 모델을 학습하지 않음."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import uuid
from collections import deque

from learning_data.collection import inside, packed
from learning_data import generation

FEATURES_VERSION = 6
SUPPORTED_FEATURES_VERSIONS = (4, 5, FEATURES_VERSION)


def author_difficulty(item, track=None):
    """출제 난이도만 읽고 값이 없으면 미확인으로 남김."""
    value = item.get("difficulty", item.get("level") if track == "python" else None)
    if value is not None and (type(value) is not int or not 1 <= value <= 3):
        raise ValueError("출제 난이도는 1~3 또는 미확인 값으로 지정해 주세요.")
    return value


def question_key(row):
    """실제로 반환한 같은 문항 버전·풀이 위치만 연결함."""
    data, item = row["data"], row.get("item") or {}
    mock = row["kind"] in ("mock_question_returned", "mock_answer")
    fields = ("mock", "try", "card", "position") if mock else ("set", "card", "position", "again")
    if not row.get("item_revision") or any(data.get(name) is None for name in fields):
        return None
    return (row["participant"], row["track"], mock, item.get("course", data.get("course")),
            row["item_revision"], (item.get("generation") or {}).get("instance_id"), *(data[name] for name in fields))


def source_events(events, synthetic=None):
    """입력의 출처 표시를 유지하고 서로 다른 출처의 혼합을 거절함."""
    if synthetic is not None and type(synthetic) is not bool:
        raise ValueError("합성 여부는 참·거짓 또는 미표시로 지정해 주세요.")
    events = list(events)
    markers = {row["synthetic"] for row in events
               if row.get("kind") == "manifest" and type(row.get("synthetic")) is bool}
    if len(markers) > 1:
        raise ValueError("출처가 다른 입력은 따로 내보내 주세요.")
    fallback = next(iter(markers)) if markers else synthetic
    output = []
    for row in events:
        if row.get("kind") == "manifest":
            continue
        marker = row.get("synthetic") if type(row.get("synthetic")) is bool else fallback
        origin = "unmarked" if marker is None else "synthetic" if marker else "recorded"
        output.append(dict(row, synthetic=marker, data_source=origin))
    if len({row["data_source"] for row in output}) > 1:
        raise ValueError("합성·기록·출처 미표시 입력은 따로 내보내 주세요.")
    return output


def course_fields(track, item, data):
    """수집한 과정 이름과 옛 기록의 id로 추정한 값을 나눔."""
    if track != "ai":
        return {"course": None, "course_inferred": None, "course_inferred_from": None}
    course = item.get("course", data.get("course"))
    if course is not None and course not in ("intro", "app"):
        raise ValueError("학습 자료의 AI 과정 구분을 확인해 주세요.")
    if item.get("course") is not None and data.get("course") is not None and item["course"] != data["course"]:
        raise ValueError("문항과 풀이의 AI 과정 구분이 다릅니다.")
    lesson = item.get("lesson")
    inferred = None
    if isinstance(lesson, str) and len(lesson) == 3 and lesson[0] in "ia" and lesson[1:].isdigit():
        inferred = "app" if lesson[0] == "a" else "intro"
    if course is not None and inferred is not None and course != inferred:
        raise ValueError("차시와 AI 과정 구분이 다릅니다.")
    return {"course": course, "course_inferred": inferred if course is None else None,
            "course_inferred_from": "item.lesson" if course is None and inferred is not None else None}


def prepare(events, synthetic=None):
    events = source_events(events, synthetic)
    events = [row for row in events if row.get("data", {}).get("training_eligible") is not False]
    events = sorted(events, key=lambda row: (row["participant"], row["track"], row["sequence"]))
    results = ("pass", "stuck", "ok", "wrong")
    def answer_key(row):
        data = row["data"]
        return (row["participant"], row["track"], data.get("set"), data.get("card"), data.get("again"))
    def mock_key(row):
        data = row["data"]
        if data.get("batch"):
            return (row["participant"], row["track"], "batch", data["batch"])
        return (row["participant"], row["track"], data.get("mock"), data.get("try"))
    def eligible(row):
        data = row["data"]
        return row["kind"] in ("answer", "mock_answer") and data.get("result") in results and not (
            row["kind"] == "answer" and (data.get("again", 0) or data.get("first_in_set") is False))
    corrected = {answer_key(row) for row in events if row["kind"] == "override"}
    mock_last = {}
    for row in events:
        if eligible(row) and (row["kind"] == "mock_answer" or row["data"].get("batch")):
            mock_last[mock_key(row)] = row["sequence"]
    history, moments, observed, mock_before, pending, output = {}, {}, {}, {}, {}, []
    sequences, group_sequences = {}, {}
    released_history, group_history_lengths, questions = {}, {}, {}
    blank = {"attempts": 0, "correct": 0, "last_at": None, "overrides": 0}
    for row in events:
        data, item = row["data"], row.get("item") or {}
        if item.get("generation") is not None:
            if row["track"] != "ai":
                raise ValueError("생성 문항의 과목을 확인해 주세요.")
            generation.from_item(item)
        key = (row["participant"], row["track"])
        at = datetime.datetime.fromisoformat(row["at"])
        if at.tzinfo is None:
            raise ValueError("학습 자료의 시각에 시간대가 없습니다.")
        if key in moments and at < moments[key]:
            raise ValueError("수집 순서와 시각이 맞지 않습니다. 시계가 바뀐 구간을 확인해 주세요.")
        moments[key] = at
        prior = history.setdefault(key, {})
        sequence = sequences.setdefault(key, deque(maxlen=128))
        released = released_history.setdefault(key, [])
        if row["kind"] in ("consent", "withdraw"):
            questions.pop(key, None)
        if row["track"] == "ai" and row["kind"] in ("question_returned", "mock_question_returned"):
            shown_key = question_key(row)
            if shown_key is not None:
                shown = questions.setdefault(key, {})
                # 같은 위치의 반환 기록이 여럿이면 관찰 시각을 임의로 고르지 않음.
                shown[shown_key] = row if shown_key not in shown else None
        if row["kind"] in ("mock_start", "mock_question_returned", "batch_start"):
            mock_before.setdefault(mock_key(row), {tag: dict(value) for tag, value in prior.items()})
            group_sequences.setdefault(mock_key(row), list(sequence))
            group_history_lengths.setdefault(mock_key(row), len(released))
            continue
        if row["kind"] == "override":
            tags = observed.get(answer_key(row), [])
            for tag in tags:
                prior[tag]["overrides"] += 1
            released.append((tags, None, row["at"], None, row["at"]))
            continue
        if not eligible(row):
            continue
        card = item.get("card") or data.get("card")
        if not card:
            continue
        tags = item.get("tags") or [item.get("family") or card]
        is_mock = row["kind"] == "mock_answer" or bool(data.get("batch"))
        source = mock_before.get(mock_key(row)) if is_mock else prior
        before = {tag: dict(source.get(tag, blank)) for tag in tags} if source is not None else None
        session = data.get("set") or "%s:%s" % (data.get("mock"), data.get("try"))
        sequence_before = list(group_sequences.get(mock_key(row), [])) if is_mock else list(sequence)
        prediction_at = data.get("prediction_at")
        prediction_source = "data.prediction_at" if prediction_at is not None else None
        prediction_event = None
        shown = questions.get(key, {}).get(question_key(row))
        if prediction_at is None and row["track"] == "ai":
            if shown is not None:
                prediction_at = shown["at"]
                prediction_source = shown["kind"] + ".at"
                prediction_event = shown["event_id"]
        if prediction_at is not None:
            cutoff = datetime.datetime.fromisoformat(prediction_at)
            if cutoff.tzinfo is None or cutoff > at:
                raise ValueError("예측 시점의 시각과 시간대를 확인해 주세요.")
            available = released[:group_history_lengths.get(mock_key(row), 0)] if is_mock else released
            available = [past for past in available if datetime.datetime.fromisoformat(past[4]) < cutoff]
            sequence_before = [past[3] for past in available if past[3] is not None][-128:]
            if before is not None:
                before = {tag: dict(blank) for tag in tags}
                for past_tags, result, answered_at, _, _ in available:
                    for tag in set(past_tags) & set(tags):
                        if result is None:
                            before[tag]["overrides"] += 1
                        else:
                            before[tag]["attempts"] += 1
                            before[tag]["correct"] += result
                            previous_at = before[tag]["last_at"]
                            if previous_at is None or datetime.datetime.fromisoformat(answered_at) > datetime.datetime.fromisoformat(previous_at):
                                before[tag]["last_at"] = answered_at
        # 예측 전에 관찰한 동일 문항만 사용함. 답 기록에만 남은 조건은 소급하지 않음.
        variant = None
        if shown is not None and prediction_at is not None and datetime.datetime.fromisoformat(shown["at"]) <= cutoff:
            variant = generation.from_item(shown.get("item") or {})
        target = int(data["result"] in ("pass", "ok"))
        if answer_key(row) not in corrected and before is not None:
            output.append({"participant": row["participant"], "track": row["track"], "event_id": row["event_id"],
                           "sequence": row["sequence"], "at": row["at"], "session": session, "question_id": card,
                           "question_revision": row.get("item_revision"), "concepts": tags, "source": row["kind"],
                           "generation": variant,
                           "difficulty": author_difficulty(item, row["track"]),
                           "goal": data.get("goal"), **course_fields(row["track"], item, data),
                           "synthetic": row["synthetic"], "data_source": row["data_source"],
                           "provenance": data.get("provenance", "collected"),
                           "prediction_at": prediction_at,
                           "prediction_source": prediction_source, "prediction_event": prediction_event,
                           "features": {"observed_history": before,
                                        "sequence_history": sequence_before},
                           "target": target})
        observed[answer_key(row)] = tags
        entry = {"event_id": row["event_id"], "question_id": card, "question_revision": row.get("item_revision"),
                 "generation": variant,
                 "concepts": tags, "result": target, "at": row["at"],
                 "difficulty": author_difficulty(item, row["track"]), **course_fields(row["track"], item, data)}
        updates = [(tags, target, row["at"], entry)]
        if is_mock:
            pending.setdefault(mock_key(row), []).extend(updates)
            updates = pending.pop(mock_key(row)) if row["sequence"] == mock_last[mock_key(row)] else []
        for update_tags, update_target, update_at, entry in updates:
            released.append((update_tags, update_target, update_at, entry, row["at"]))
            sequence.append(entry)
            for tag in update_tags:
                current = prior.setdefault(tag, dict(blank))
                current["attempts"] += 1
                current["correct"] += update_target
                if current["last_at"] is None or datetime.datetime.fromisoformat(update_at) > datetime.datetime.fromisoformat(current["last_at"]):
                    current["last_at"] = update_at
    return output

def split(records):
    days = sorted({datetime.datetime.fromisoformat(row["at"]).astimezone(datetime.timezone.utc).date() for row in records})
    if len(days) < 3:
        raise ValueError("시간순 평가에는 3일 이상의 관찰 기록이 필요합니다.")
    train_end = max(1, min(len(days) - 2, int(len(days) * 0.7)))
    valid_end = max(train_end + 1, min(len(days) - 1, int(len(days) * 0.85)))

    def part(row):
        day = datetime.datetime.fromisoformat(row["at"]).astimezone(datetime.timezone.utc).date()
        return "train" if day < days[train_end] else ("validation" if day < days[valid_end] else "test")

    groups = {}
    for row in records:
        key = (row["participant"], row["track"], row["session"])
        groups.setdefault(key, set()).add(part(row))
    parts = {name: [] for name in ("train", "validation", "test")}
    for row in records:
        if len(groups[(row["participant"], row["track"], row["session"])]) == 1:
            parts[part(row)].append(row)
    for name, prior in (("validation", ("train",)), ("test", ("train", "validation"))):
        available = [datetime.datetime.fromisoformat(row["at"]) for group in prior for row in parts[group]]
        if not available:
            continue
        cutoff = max(available)
        invalid = {(row["participant"], row["track"], row["session"]) for row in parts[name]
                   if row.get("prediction_at") and datetime.datetime.fromisoformat(row["prediction_at"]) < cutoff}
        parts[name] = [row for row in parts[name] if (row["participant"], row["track"], row["session"]) not in invalid]
    if not all(parts.values()):
        raise ValueError("풀이 묶음을 나누지 않고 평가할 관찰 기록이 더 필요합니다.")
    return parts


def synthetic_events():
    """입출력 연습용 가상 기록을 만듦. 실제 수강생 성능 평가에 쓰지 않음."""
    rows = []
    for person in range(2):
        participant = str(uuid.uuid5(uuid.NAMESPACE_URL, "study-synthetic-person-%d" % person))
        for track in ("ai", "python"):
            for day in range(1, 7):
                rows.append({"participant": participant, "track": track, "sequence": day, "synthetic": True,
                             "event_id": str(uuid.uuid5(uuid.UUID(participant), "%s-%d" % (track, day))),
                             "at": "2026-01-%02dT10:00:00+00:00" % day, "kind": "answer", "item_revision": "0" * 64,
                             "item": {"card": track + "-demo", "tags": ["demo"], "difficulty": 2},
                             "data": {"set": "demo-%d" % day, "card": track + "-demo", "again": 0,
                                      "result": "pass" if (person + day) % 3 else "stuck", "first_in_set": True,
                                      "prediction_at": "2026-01-%02dT10:00:00+00:00" % day}})
    return rows


def write_private(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
        output.write(text)


def write_dataset(events, destination, synthetic=None, source_sha256=None):
    root = Path(__file__).resolve().parent.parent
    if inside(destination, root):
        raise ValueError("학습 자료는 공개 저장소 밖에 저장해 주세요.")
    records = prepare(events, synthetic=synthetic)
    parts = {track: split([row for row in records if row["track"] == track]) for track in sorted({row["track"] for row in records})}
    if not parts:
        raise ValueError("사용할 첫 시도 답안이 없습니다.")
    os.mkdir(destination, mode=0o700)
    manifest = {"format": 1, "features_version": FEATURES_VERSION, "synthetic": records[0]["synthetic"], "source": records[0]["data_source"],
                "source_sha256": source_sha256, "eligible_rows": len(records),
                "excluded_split_rows": len(records) - sum(len(rows) for groups in parts.values() for rows in groups.values()),
                "files": {}}
    for track, groups in parts.items():
        for name, rows in groups.items():
            path = Path(destination) / (track + "-" + name + ".jsonl")
            write_private(path, "".join(packed(row) + "\n" for row in rows))
            readback = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            if readback != rows:
                raise ValueError("학습용 파일을 다시 읽어 확인하지 못했습니다.")
            manifest["files"][path.name] = {"rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    write_private(Path(destination) / "manifest.json", packed(manifest) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="과목별 시간순 학습 자료를 만듭니다.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--synthetic", action="store_true")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        raw = Path(args.input).read_bytes() if args.input else None
        events = [json.loads(line) for line in raw.splitlines()] if raw is not None else synthetic_events()
        result = write_dataset(events, args.out, True if args.synthetic else None,
                               hashlib.sha256(raw).hexdigest() if raw is not None else None)
        print("과목별 학습 자료를 저장하고 다시 읽어 확인했습니다. %s" % args.out)
        print(packed(result))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
