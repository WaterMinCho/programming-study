# -*- coding: utf-8 -*-
"""명시적으로 고른 기존 파이썬 프로필을 별도 연구 자료로 변환함."""
import datetime
from collections import OrderedDict
import hashlib
import json
import secrets
import uuid
import re
from zoneinfo import ZoneInfo

from aiprep.collection import digest, packed, stamp


def profile_events(profile, catalog, timezone):
    """기존 판정과 시각을 보존함. 과거 입력 시각·문항 버전·희망 직무를 복원하지 않음."""
    offset = re.fullmatch(r"([+-])(\d{2}):(\d{2})", timezone)
    if offset:
        hours, minutes = int(offset[2]), int(offset[3])
        if hours > 23 or minutes > 59:
            raise ValueError("기존 기록에 적용할 시간대를 확인해 주세요.")
        zone = datetime.timezone(datetime.timedelta(minutes=(hours * 60 + minutes) * (1 if offset[1] == "+" else -1)))
    else:
        zone = ZoneInfo(timezone)
    participant = str(uuid.uuid4())
    groups = OrderedDict()
    omitted = {"missing_time": 0, "unknown_question": 0, "skipped": 0}
    previous = None
    rounds = {row["id"]: row for row in profile.get("rounds", [])}
    seen = set()
    for attempt in profile["attempts"]:
        if attempt.get("skipped"):
            omitted["skipped"] += 1
            continue
        if not attempt.get("at"):
            omitted["missing_time"] += 1
            continue
        item = catalog.get(attempt["item"])
        if item is None:
            omitted["unknown_question"] += 1
            continue
        if type(attempt.get("ok")) is not bool or type(attempt.get("try")) is not int or attempt["try"] < 1:
            raise ValueError("기존 기록의 정오답과 시도 번호를 확인해 주세요.")
        moment = datetime.datetime.fromisoformat(attempt["at"])
        assumed = moment.tzinfo is None
        if assumed:
            moment = moment.replace(tzinfo=zone)
        moment = moment.astimezone(datetime.timezone.utc)
        if previous is not None and moment < previous:
            raise ValueError("기존 기록의 시각이 거꾸로 바뀐 구간을 먼저 확인해 주세요.")
        previous = moment
        identity = (attempt["round"], attempt["item"], attempt["try"], attempt["at"])
        if identity in seen:
            raise ValueError("기존 기록에 같은 시도가 중복돼 있습니다.")
        seen.add(identity)
        groups.setdefault((attempt["round"], moment.isoformat()), []).append((attempt, item, assumed))
    rows = [{"kind": "manifest", "synthetic": False, "source_type": "legacy_profile", "timezone": timezone,
             "omitted": omitted}]
    for (rid, at), attempts in groups.items():
        batch = str(uuid.uuid4())
        def add(kind, data, item=None):
            rows.append({"format": 1, "participant": participant, "track": "python", "synthetic": False,
                         "sequence": len(rows), "event_id": str(uuid.uuid4()), "at": at,
                         "kind": kind, "item_revision": None, "item": item, "data": data})
        add("batch_start", {"batch": batch, "set": rid})
        for attempt, item, assumed in attempts:
            metadata = {"unit": item["unit"], "tags": item["tags"], "kind": item["kind"], "type": item["type"]}
            created = rounds.get(rid, {}).get("created")
            prediction_at = None
            if created:
                created_at = datetime.datetime.fromisoformat(created)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=zone)
                created_at = created_at.astimezone(datetime.timezone.utc)
                if created_at <= datetime.datetime.fromisoformat(at):
                    prediction_at = created_at.isoformat()
            add("answer", {"batch": batch, "set": rid, "card": attempt["item"],
                           "again": attempt["try"] - 1, "first_in_set": attempt["try"] == 1,
                           "result": "ok" if attempt["ok"] else "wrong",
                           "goal": None, "observed_at": None, "prediction_at": prediction_at,
                           "provenance": {"kind": "legacy_profile", "original_at": attempt["at"],
                                          "timezone_assumption": timezone if assumed else None,
                                          "question_revision": "unknown", "concepts": "current_catalog",
                                          "catalog_revision": digest(metadata)}},
                {"card": attempt["item"], "tags": item["tags"] or [item["unit"]]})
    return rows


TRANSFER_SCHEMA = """
CREATE TABLE IF NOT EXISTS legacy_transfers (
    participant TEXT PRIMARY KEY, transfer_id TEXT UNIQUE NOT NULL,
    source_sha256 TEXT UNIQUE NOT NULL, provenance TEXT NOT NULL,
    consent TEXT, imported_at TEXT NOT NULL, state TEXT NOT NULL,
    removed_at TEXT
)
"""


def transfer_plan(path, catalog):
    """운영자가 고른 원본을 읽고 가명·동의·변환 근거를 분리함. 원본에는 쓰지 않음."""
    from learning_server.operations import private_path

    path = private_path(path).resolve()
    plan = json.loads(path.read_bytes())
    if plan.get("format") != 1 or not isinstance(plan.get("profiles"), list) or not plan["profiles"]:
        raise ValueError("이관 목록의 형식과 프로필 항목을 확인해 주세요.")
    timezone = plan.get("timezone")
    prepared, participants, sources = [], set(), set()
    for entry in plan["profiles"]:
        participant = entry["participant"]
        if not isinstance(participant, str) or str(uuid.UUID(participant)) != participant:
            raise ValueError("이관 목록에는 사람마다 고정한 UUID 가명값을 지정해 주세요.")
        consent = entry["consent"]
        if (consent.get("private_server_transfer") is not True or consent.get("recommendation_research") is not True
                or not isinstance(consent.get("evidence_ref"), str) or not consent["evidence_ref"].strip()):
            raise ValueError("기존 풀이의 비공개 서버 이전·추천 연구 동의와 확인 근거를 적어 주세요.")
        confirmed = datetime.date.fromisoformat(consent["confirmed_on"])
        if confirmed.isoformat() != consent["confirmed_on"]:
            raise ValueError("동의를 확인한 날짜를 확인해 주세요.")
        consent = {name: consent[name] for name in (
            "confirmed_on", "evidence_ref", "private_server_transfer", "recommendation_research")}
        source = path.parent / entry["profile"]
        if source.name != "profile.json":
            raise ValueError("기존 풀이의 profile.json 파일을 지정해 주세요.")
        raw = source.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if participant in participants or checksum in sources:
            raise ValueError("이관 목록에 같은 가명 또는 같은 원본이 중복돼 있습니다.")
        participants.add(participant)
        sources.add(checksum)
        rows = profile_events(json.loads(raw), catalog, timezone)
        manifest, events = rows[0], rows[1:]
        if not events:
            raise ValueError("변환할 수 있는 시각·문항이 있는 풀이 기록이 없습니다.")
        transfer_id = str(uuid.uuid5(uuid.UUID(participant), "legacy:" + checksum))
        batches = {}
        for row in events:
            row["participant"] = participant
            row["event_id"] = str(uuid.uuid5(uuid.UUID(transfer_id), "event:%d" % row["sequence"]))
            old_batch = row["data"]["batch"]
            batches.setdefault(old_batch, str(uuid.uuid5(uuid.UUID(transfer_id), "batch:%d" % row["sequence"])))
            row["data"]["batch"] = batches[old_batch]
            if row["kind"] == "answer":
                row["data"]["provenance"].update(source_sha256=checksum, transfer_id=transfer_id)
        provenance = {"converter_version": 1, "timezone": timezone, "omitted": manifest["omitted"],
                      "question_revision": "unknown", "concepts": "current_catalog",
                      "catalog_sha256": digest({row["data"]["card"]: row["data"]["provenance"]["catalog_revision"]
                                                for row in events if row["kind"] == "answer"}),
                      "events_sha256": digest(events), "events": len(events),
                      "answers": sum(row["kind"] == "answer" for row in events)}
        prepared.append({"participant": participant, "transfer_id": transfer_id, "source_sha256": checksum,
                         "provenance": provenance, "consent": consent, "events": events})
    return prepared


def transfer(path, manifest, catalog, *, dry_run=False):
    return store_plan(path, transfer_plan(manifest, catalog), dry_run=dry_run)


def store_plan(path, prepared, *, dry_run=False):
    """기존 서버 DB에 별도 이관 계정을 원자적으로 저장함. 재실행과 변경 충돌을 구분함."""
    from learning_server.app import Database
    from learning_server.operations import private_path, read_database, status

    path = private_path(path)
    status(path)
    database = None if dry_run else Database(str(path))
    result = {"status": "dry_run" if dry_run else "ok", "profiles": len(prepared),
              "inserted_profiles": 0, "existing_profiles": 0, "events": 0, "answers": 0,
              "omitted": {"missing_time": 0, "unknown_question": 0, "skipped": 0}}
    context = read_database(path) if dry_run else database.connect()
    with context as db:
        if not dry_run:
            db.execute("BEGIN IMMEDIATE")
            db.execute(TRANSFER_SCHEMA)
        has_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_transfers'").fetchone()
        for item in prepared:
            participant, provenance = item["participant"], item["provenance"]
            old = db.execute("SELECT participant, source_sha256, provenance, consent, state FROM legacy_transfers "
                             "WHERE participant=? OR source_sha256=?", (participant, item["source_sha256"])).fetchall() if has_table else []
            account = db.execute("SELECT revoked FROM participants WHERE participant=?", (participant,)).fetchone()
            values = [(participant, item.get("track", "python"), row["event_id"], row["sequence"], packed(row)) for row in item["events"]]
            if old:
                expected = [(participant, item["source_sha256"], packed(provenance), packed(item["consent"]), "active")]
                if old != expected or account != (0,):
                    raise ValueError("이관 원본·문항맵·동의 또는 철회 상태가 달라 저장하지 않았습니다.")
                saved = db.execute("SELECT participant, track, event_id, sequence, payload FROM events "
                                   "WHERE participant=? ORDER BY sequence", (participant,)).fetchall()
                if saved != values:
                    raise ValueError("이관한 기록과 현재 DB의 내용이 다릅니다.")
                result["existing_profiles"] += 1
            else:
                if account or db.execute("SELECT 1 FROM events WHERE participant=?", (participant,)).fetchone():
                    raise ValueError("다른 수집에 사용하지 않은 별도 이관 가명값을 지정해 주세요.")
                if not dry_run:
                    database.storage_limit(db, participant, sum(len(row[4].encode("utf-8")) for row in values), len(values))
                    db.execute("INSERT INTO participants VALUES (?, ?, 'legacy-operator-consent-v1', ?, 0)",
                               (participant, hashlib.sha256(secrets.token_bytes(32)).hexdigest(), stamp()))
                    db.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?)", values)
                    saved = db.execute("SELECT participant, track, event_id, sequence, payload FROM events "
                                       "WHERE participant=? ORDER BY sequence", (participant,)).fetchall()
                    if saved != values:
                        raise ValueError("이관한 기록을 다시 읽어 확인하지 못했습니다.")
                    db.execute("INSERT INTO legacy_transfers VALUES (?, ?, ?, ?, ?, ?, 'active', NULL)",
                               (participant, item["transfer_id"], item["source_sha256"], packed(provenance),
                                packed(item["consent"]), stamp()))
                result["inserted_profiles"] += 1
            result["events"] += provenance["events"]
            result["answers"] += provenance["answers"]
            for name, count in provenance["omitted"].items():
                result["omitted"][name] += count
    return result


def remove_transfer(path, participant, *, reason):
    """별도 이관 계정의 기록을 지우고 재수입을 막는 표식을 남김."""
    from learning_server.app import Database
    from learning_server.operations import private_path, status

    if reason not in ("rollback", "withdrawal") or str(uuid.UUID(participant)) != participant:
        raise ValueError("제거할 이관 가명과 사유를 확인해 주세요.")
    path = private_path(path)
    status(path)
    database = Database(str(path))
    with database.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_transfers'").fetchone():
            raise ValueError("이관한 계정이 없습니다.")
        old = db.execute("SELECT state FROM legacy_transfers WHERE participant=?", (participant,)).fetchone()
        if not old:
            raise ValueError("이관한 계정이 없습니다.")
        state = "withdrawn" if reason == "withdrawal" or old[0] == "withdrawn" else "rolled_back"
        count = db.execute("SELECT count(*) FROM events WHERE participant=?", (participant,)).fetchone()[0]
        db.execute("DELETE FROM events WHERE participant=?", (participant,))
        db.execute("UPDATE participants SET revoked=1 WHERE participant=?", (participant,))
        db.execute("UPDATE legacy_transfers SET consent=NULL, state=?, removed_at=coalesce(removed_at, ?) WHERE participant=?",
                   (state, stamp(), participant))
    return {"status": "ok", "state": state, "deleted_events": count}
