# -*- coding: utf-8 -*-
"""운영 폴더 전체의 할당량과 논리 보관량을 읽기 전용으로 대조함."""
import os
from pathlib import Path
import stat

from learning_server.app import MAX_STORED_BYTES
from learning_server.operations import private_path, read_database
from learning_server.storage import usage


def allocated_size(root):
    pending, seen, total, files, vanished = [root], set(), 0, 0, 0
    while pending:
        path = pending.pop()
        try:
            info = path.lstat()
        except FileNotFoundError:
            vanished += 1
            continue
        identity = (info.st_dev, info.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        total += info.st_blocks * 512 if hasattr(info, "st_blocks") else info.st_size
        if stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400:
            try:
                with os.scandir(path) as entries:
                    pending.extend(Path(row.path) for row in entries)
            except FileNotFoundError:
                vanished += 1
        else:
            files += 1
    return total, files, vanished


def verify_totals(db):
    expected = {p: [count, size] for p, count, size in db.execute(
        "SELECT participant,count(*),sum(length(CAST(payload AS BLOB))) FROM events GROUP BY participant")}
    for p, size in db.execute("SELECT participant,coalesce(sum(length(payload)),0) FROM api_submissions GROUP BY participant"):
        expected.setdefault(p, [0, 0])[1] += size
    expected[""] = [sum(row[0] for row in expected.values()), sum(row[1] for row in expected.values())]
    stored = {p: [count, size] for p, count, size in db.execute("SELECT participant,events,bytes FROM storage_totals")}
    return all(expected.get(p, [0, 0]) == stored.get(p, [0, 0]) for p in expected.keys() | stored.keys())


def report(path, root, quota_mib, warn_percent=80, verify=False):
    path, root = private_path(path), private_path(root)
    if type(quota_mib) is not int or quota_mib <= 0 or not 1 <= warn_percent <= 99:
        raise ValueError("용량 한도와 경고 비율을 확인해 주세요.")
    if not root.is_dir() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("운영 DB가 포함된 저장 공간의 최상위 폴더를 지정해 주세요.")
    with read_database(path) as db:
        count, logical = usage(db)
        verified = verify_totals(db) if verify else None
    allocated, files, vanished = allocated_size(root)
    limit = quota_mib * 1024 * 1024
    disk_percent, payload_percent = allocated * 100 / limit, logical * 100 / MAX_STORED_BYTES
    warnings = []
    if disk_percent >= warn_percent:
        warnings.append("disk_capacity")
    if payload_percent >= warn_percent:
        warnings.append("payload_capacity")
    if verified is False:
        warnings.append("counter_mismatch")
    return {"status": "warning" if warnings else "ok", "warnings": warnings,
            "allocation_estimate_bytes": allocated, "configured_quota_bytes": limit,
            "disk_percent": round(disk_percent, 2), "files": files, "vanished_during_scan": vanished,
            "database_bytes": path.stat().st_size, "events": count,
            "logical_payload_bytes": logical, "logical_payload_limit": MAX_STORED_BYTES,
            "payload_percent": round(payload_percent, 2), "counter_verified": verified,
            "limit": "폴더 할당량의 추정값이며 호스팅 사업자의 계정 사용량 집계를 대신하지 않음"}
