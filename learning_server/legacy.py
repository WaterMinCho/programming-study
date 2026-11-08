# -*- coding: utf-8 -*-
"""명시적으로 고른 기존 파이썬 프로필을 별도 연구 자료로 변환함."""
import datetime
from collections import OrderedDict
import uuid
import re
from zoneinfo import ZoneInfo

from aiprep.collection import digest


def profile_events(profile, catalog, timezone):
    """기존 판정과 시각을 보존함. 과거 입력 시각·문항 판·희망 직무를 복원하지 않음."""
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
