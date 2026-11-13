# -*- coding: utf-8 -*-
"""직접 고른 진로 목표와 선택 당시 로드맵 버전을 보존함."""
import hashlib
import json
from pathlib import Path
import uuid

STABLE_IDS = ("arm", "nav", "vision", "field", "physical", "platform")


def catalog(repository):
    raw = (Path(repository) / "tools" / "roadmap" / "roadmap.json").read_bytes()
    data = json.loads(raw)
    try:
        options = {row["id"]: row["title"] for row in data["paths"]}
        updated = data["updated"]
    except (KeyError, TypeError):
        raise ValueError("희망 직무 목록과 로드맵 버전을 확인해 주세요.") from None
    if set(options) != set(STABLE_IDS) or not isinstance(updated, str):
        raise ValueError("희망 직무 목록과 로드맵 버전을 확인해 주세요.")
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"options": [(key, options[key]) for key in STABLE_IDS],
            "roadmap_revision": hashlib.sha256(canonical).hexdigest(), "roadmap_updated": data["updated"]}


def unselected():
    return {"goal_id": None, "roadmap_revision": None, "roadmap_updated": None,
            "basis": "self_selected_goal", "selected_at": None, "selection_id": None}


def selection(goal_id, roadmap, at):
    if goal_id is not None and goal_id not in dict(roadmap["options"]):
        raise ValueError("목록에 있는 희망 직무를 고르거나 미선택으로 저장해 주세요.")
    return {"goal_id": goal_id, "roadmap_revision": roadmap["roadmap_revision"],
            "roadmap_updated": roadmap["roadmap_updated"], "basis": "self_selected_goal",
            "selected_at": at, "selection_id": str(uuid.uuid4())}
