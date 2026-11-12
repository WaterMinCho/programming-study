# -*- coding: utf-8 -*-
"""각 이벤트에 저장한 자기신고 목표로 비공개 집계를 만듦."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from learning_data.collection import inside, packed
from learning_data.goals import STABLE_IDS
from learning_server.dataset import write_private


def summarize(events, source="unmarked"):
    """각 이벤트의 목표 판만 사용함. 뒤의 목표 변경이나 정답 수정으로 앞의 답을 바꾸지 않음."""
    groups, seen, answer_tags, recalls = {}, {}, {}, set()
    events = sorted(events, key=lambda r: (r.get("participant", ""), r.get("track", ""), r.get("sequence", 0)))
    for row in events:
        if row.get("kind") == "manifest":
            continue
        origin = ("synthetic" if row["synthetic"] else "recorded") if type(row.get("synthetic")) is bool else source
        identity = (origin, row["participant"], row["track"], row["event_id"])
        if identity in seen:
            if seen[identity] != row:
                raise ValueError("같은 고유번호의 기록 내용이 다릅니다.")
            continue
        seen[identity] = row
        data, item, event_kind = row["data"], row.get("item") or {}, row["kind"]
        kind = {"answer": "practice", "override": "practice", "mock_answer": "mock", "recall": "recall"}.get(event_kind)
        if kind is None:
            continue
        answer_key = (origin, row["participant"], row["track"], data.get("set"), data.get("card"), data.get("again"))
        tags = item.get("tags") or ([None] if event_kind != "override" else answer_tags.get(answer_key, [None]))
        if event_kind == "answer":
            answer_tags[answer_key] = tags
        correction = event_kind == "override"
        correct = data.get("ok") if kind == "recall" else data.get("result") in ("pass", "ok")
        if not correction and ((kind == "recall" and type(data.get("ok")) is not bool)
                               or (kind != "recall" and data.get("result") not in ("pass", "stuck", "ok", "wrong"))):
            continue
        if event_kind == "answer":
            first = data.get("first_in_set")
            if type(first) is not bool:
                first = data.get("again") == 0 if type(data.get("again")) is int else None
        elif kind == "mock":
            first = data.get("try") == 1 if type(data.get("try")) is int else None
        elif kind == "recall":
            recall_key = (origin, row["participant"], row["track"], data.get("lesson"), data.get("unit"),
                          data.get("id"), data.get("slot"), data.get("level"))
            first = recall_key not in recalls
            recalls.add(recall_key)
        else:
            first = None
        goal = data.get("goal")
        goal_id = goal.get("goal_id") if isinstance(goal, dict) else None
        goal_state = ("unrecorded" if not isinstance(goal, dict) or "goal_id" not in goal else
                      "unselected" if goal_id is None else "selected" if goal_id in STABLE_IDS else "unknown")
        revision = goal.get("roadmap_revision") if isinstance(goal, dict) else None
        for tag in sorted(set(tags), key=str):
            key = (origin, row["track"], goal_state, goal_id, revision, kind, tag)
            if key not in groups:
                groups[key] = {"source": origin, "track": row["track"], "goal_state": goal_state, "goal_id": goal_id,
                               "roadmap_revision": revision, "kind": kind, "tag": tag, "participants": set(),
                               "answers": 0, "first_answers": 0, "retries": 0, "unknown_attempts": 0,
                               "correct": 0, "corrections": 0, "unselected_answers": 0,
                               "missing_timestamps": 0, "missing_response_times": 0}
            group = groups[key]
            group["participants"].add(row["participant"])
            group["missing_timestamps"] += int(not row.get("at"))
            group["corrections"] += int(correction)
            if not correction:
                group["answers"] += 1
                group["first_answers"] += int(first is True)
                group["retries"] += int(first is False)
                group["unknown_attempts"] += int(first is None)
                group["correct"] += int(correct)
                group["unselected_answers"] += int(goal_state == "unselected")
                group["missing_response_times"] += int(data.get("secs") is None)
    output = []
    for key in sorted(groups, key=lambda value: tuple("" if v is None else str(v) for v in value)):
        group = groups[key]
        group["participants"] = len(group["participants"])
        output.append(group)
    return output


def read_events(path, database=False):
    path = Path(path).resolve(strict=True)
    source = "unmarked"
    if database:
        with contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("BEGIN")
            columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
            if "seq" in columns:
                meta = dict(db.execute("SELECT key, value FROM meta"))
                rows = []
                for seq, eid, at, kind, payload, revision in db.execute("SELECT seq,event_id,at,kind,payload,item_revision FROM events ORDER BY seq"):
                    item = db.execute("SELECT payload FROM items WHERE revision=?", (revision,)).fetchone() if revision else None
                    rows.append({"participant": meta["participant"], "track": "ai", "sequence": seq, "event_id": eid,
                                 "at": at, "kind": kind, "data": json.loads(payload), "item_revision": revision,
                                 "item": json.loads(item[0]) if item else None})
            else:
                rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM events ORDER BY participant,track,sequence")]
        source = "recorded"
        checksum = hashlib.sha256(packed(rows).encode("utf-8")).hexdigest()
    else:
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        manifests = [row for row in rows if row.get("kind") == "manifest"]
        origins = {row["synthetic"] for row in manifests if type(row.get("synthetic")) is bool}
        if len(origins) > 1:
            raise ValueError("출처가 다른 파일은 따로 집계하거나 각 이벤트에 synthetic을 표시해 주세요.")
        if origins:
            source = "synthetic" if origins.pop() else "recorded"
        checksum = hashlib.sha256(raw).hexdigest()
    return rows, source, checksum


def export(source_path, destination, database=False, synthetic=False):
    repository = Path(__file__).resolve().parent.parent
    if inside(destination, repository) or inside(destination, Path(source_path).resolve().parent):
        raise ValueError("원본 폴더와 공개 저장소 밖의 새 폴더를 골라 주세요.")
    events, origin, checksum = read_events(source_path, database)
    if synthetic:
        origin = "synthetic"
    groups = summarize(events, origin)
    os.mkdir(destination, mode=0o700)
    target = Path(destination) / "cohorts.jsonl"
    write_private(target, "".join(packed(row) + "\n" for row in groups))
    if [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()] != groups:
        raise ValueError("집계 파일을 다시 읽어 확인하지 못했습니다.")
    manifest = {"format": 1, "source": origin, "sources": sorted({row["source"] for row in groups}), "source_sha256": checksum,
                "checksum_basis": "event_snapshot" if database else "input_bytes", "groups": len(groups),
                "cohorts_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    write_private(Path(destination) / "manifest.json", packed(manifest) + "\n")
    if json.loads((Path(destination) / "manifest.json").read_text(encoding="utf-8")) != manifest:
        raise ValueError("집계 목록을 다시 읽어 확인하지 못했습니다.")
    return manifest
