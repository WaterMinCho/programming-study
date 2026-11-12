# -*- coding: utf-8 -*-
"""과거 AI 판정을 보관용 이벤트로 옮김. 관찰하지 않은 예측 시각은 만들지 않음."""
import datetime
import hashlib
import json
import uuid

from aiprep.collection import digest
from learning_server.legacy import store_plan
from learning_server.operations import private_path


def transfer_plan(path):
    path = private_path(path).resolve()
    plan = json.loads(path.read_bytes())
    if plan.get("format") != 1 or not isinstance(plan.get("profiles"), list) or not plan["profiles"]:
        raise ValueError("이관 목록의 형식과 프로필 항목을 확인해 주세요.")
    archived_at = plan["archived_at"]
    moment = datetime.datetime.fromisoformat(archived_at)
    if moment.tzinfo is None:
        raise ValueError("보관 작업 시각에는 시간대를 적어 주세요.")
    prepared, participants, sources = [], set(), set()
    for entry in plan["profiles"]:
        participant = entry["participant"]
        if not isinstance(participant, str) or str(uuid.UUID(participant)) != participant:
            raise ValueError("이관 목록의 고정 UUID 가명값을 확인해 주세요.")
        consent = entry["consent"]
        if (consent.get("private_server_transfer") is not True or consent.get("recommendation_research") is not True
                or not isinstance(consent.get("evidence_ref"), str) or not consent["evidence_ref"].strip()):
            raise ValueError("비공개 서버 이전·추천 연구 동의와 확인 근거를 적어 주세요.")
        if datetime.date.fromisoformat(consent["confirmed_on"]).isoformat() != consent["confirmed_on"]:
            raise ValueError("동의를 확인한 날짜를 확인해 주세요.")
        consent = {key: consent[key] for key in (
            "confirmed_on", "evidence_ref", "private_server_transfer", "recommendation_research")}
        source = path.parent / entry["record"]
        if source.name != "record.json":
            raise ValueError("AI 풀이의 record.json 파일을 지정해 주세요.")
        raw = source.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if participant in participants or checksum in sources:
            raise ValueError("같은 가명 또는 원본이 중복돼 있습니다.")
        participants.add(participant)
        sources.add(checksum)
        record = json.loads(raw)
        if not isinstance(record.get("log"), list):
            raise ValueError("원본 풀이 로그를 확인해 주세요.")
        transfer_id = str(uuid.uuid5(uuid.UUID(participant), "legacy-ai:" + checksum))
        events, skipped, seen = [], 0, set()
        for index, row in enumerate(record["log"]):
            if not isinstance(row, dict):
                raise ValueError("원본 풀이 항목을 확인해 주세요.")
            if row.get("kind") == "override":
                raise ValueError("정정 이력이 있는 원본은 판정과 정정의 연결을 먼저 확인해 주세요.")
            if row.get("kind") != "answer":
                skipped += 1
                continue
            if (not isinstance(row.get("card"), str) or not row["card"] or row.get("result") not in ("pass", "stuck", "partial")
                    or type(row.get("again")) is not int or row["again"] < 0):
                raise ValueError("원본 문항·판정·재시도 값을 확인해 주세요.")
            identity = digest({key: row.get(key) for key in ("set", "card", "again", "at")})
            if identity in seen:
                raise ValueError("원본에 같은 풀이 시도가 중복돼 있습니다.")
            seen.add(identity)
            data = {key: row[key] for key in ("card", "set", "again", "result", "sure", "dontknow") if key in row}
            data.update(original_at=row.get("at"), original_secs=row.get("secs"),
                        course=None, prediction_at=None, training_eligible=False,
                        provenance={"kind": "legacy_ai_archive", "source_sha256": checksum,
                                    "source_index": index, "transfer_id": transfer_id, "at_meaning": "archived_at",
                                    "archived_at": archived_at,
                                    "question_revision": "unknown", "course": "unknown"})
            events.append({"format": 1, "participant": participant, "track": "ai", "synthetic": False,
                           "sequence": len(events) + 1, "event_id": str(uuid.uuid5(uuid.UUID(transfer_id), "log:%d" % index)),
                           "at": archived_at, "kind": "legacy_answer", "item_revision": None,
                           "item": {"card": row["card"]}, "data": data})
        if not events:
            raise ValueError("보관할 AI 풀이 판정이 없습니다.")
        provenance = {"converter_version": 1, "source_type": "legacy_ai_archive", "archived_at": archived_at,
                      "question_revision": "unknown", "course": "unknown", "training_eligible": False,
                      "omitted": {"missing_time": 0, "unknown_question": 0, "skipped": skipped},
                      "events_sha256": digest(events), "events": len(events), "answers": len(events)}
        prepared.append({"participant": participant, "track": "ai", "transfer_id": transfer_id,
                         "source_sha256": checksum, "provenance": provenance, "consent": consent, "events": events})
    return prepared


def transfer(path, manifest, *, dry_run=False):
    return store_plan(path, transfer_plan(manifest), dry_run=dry_run)
