# -*- coding: utf-8 -*-
"""여정 문제 은행(dungeons/) 읽기와 봉인 풀기.

던전이 "출제됨"이라는 것은 dungeons/<던전>/meta.json 이 있다는 것뿐임. 공개 파일(index.json, meta.json, intro.md,
problem.json, problem.md)은 여기서 읽어 화면에 쓸 모양으로 정리하고, 비밀 파일(기준 풀이, 테스트, 힌트, 해설 등)은
sealed.json 에서 풀되 평문 작업본이 있으면 평문이 이김. 봉인은 base64 와 zlib 로 감쌌을 뿐이라 우연히 답을 보지
않게 가리는 장치임. 경로 상수는 import 할 때 복사하지 말고 bank.BANK_DIR 처럼 쓸 때 읽음(테스트가 바꿔 끼움).
"""
import json
import os
import re
import zlib

import study
from journey import values

BANK_DIR = os.path.join(study.ROOT, "dungeons")
INDEX_NAME = "index.json"
SEALED_NAME = "sealed.json"
SECRET_FILES = ("solution.py", "solution.js", "brute.py", "certify.py", "alt.py", "alt.js", "gen.py", "validate.py",
                "tests.json", "extra.json", "wrong.json", "hints.md", "explain.md", "review.json")
DUNGEON_SECRETS = ("review.json",)  # 던전 폴더 바로 아래의 비밀 파일
WRONG_DIR = "wrong"
WRONG_EXTS = (".py", ".js")
PROBLEM_ID = re.compile(r"(p[1-9]|boss)\Z")
ROLES = ("basic", "mid", "side", "boss")
HINT_HEAD = re.compile(r"##\s+(\d+)\s*\Z")


class BankError(Exception):
    """은행 파일을 읽지 못함. 문구는 화면 위 알림이나 오류 대화상자에 그대로 보여 줌."""


def _why(error):
    if isinstance(error, KeyError):
        return "%s 키가 없음" % error
    return str(error) or type(error).__name__


def _read_json(path, shown):
    try:
        return study.read_json(path)
    except (OSError, ValueError) as error:
        raise BankError("%s 을 읽을 수 없습니다: %s" % (shown, error))


def _read_text(path, shown):
    try:
        return study.read_text(path)
    except (OSError, ValueError) as error:
        raise BankError("%s 을 읽을 수 없습니다: %s" % (shown, error))


def read_index(root=None):
    """index.json 의 던전 목록을 배열 순서대로. 빠진 키는 기본값으로 채움."""
    root = root or BANK_DIR
    data = _read_json(os.path.join(root, INDEX_NAME), INDEX_NAME)
    try:
        entries = []
        for item in data["dungeons"]:
            entries.append({"id": str(item["id"]), "no": int(item["no"]), "title": str(item["title"]),
                            "topic": str(item.get("topic", "")), "boss_target": str(item.get("boss_target", "")),
                            "prereq": [str(did) for did in item.get("prereq", [])], "final": bool(item.get("final", False))})
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("%s 의 형식이 맞지 않습니다: %s" % (INDEX_NAME, _why(error)))
    return entries


def dungeon_dir(did, root=None):
    return os.path.join(root or BANK_DIR, did)


def is_ready(did, root=None):
    return os.path.isfile(os.path.join(dungeon_dir(did, root), "meta.json"))


def _problem(ddir, item):
    pid, no, role = str(item["id"]), str(item["no"]), str(item["role"])
    if not PROBLEM_ID.match(pid):
        raise ValueError("문제 id %r" % pid)
    if role not in ROLES:
        raise ValueError("역할 %r" % role)
    shown = "%s/problem.json" % pid
    data = _read_json(os.path.join(ddir, pid, "problem.json"), shown)
    markdown = _read_text(os.path.join(ddir, pid, "problem.md"), "%s/problem.md" % pid)
    try:
        signature = {"params": [{"name": str(p["name"]), "type": str(p["type"])} for p in data["signature"]["params"]],
                     "returns": str(data["signature"]["returns"])}
        for kind in [p["type"] for p in signature["params"]] + [signature["returns"]]:
            values.parse_type(kind)
        limits = {lang: int(data["time_limit_ms"][lang]) for lang in values.LANGS}
        examples = [{"args": list(ex["args"]), "expected": ex["expected"]} for ex in data["examples"]]
        score = data.get("score")
        if score is not None:
            score = {"accuracy": float(score["accuracy"]), "efficiency": float(score["efficiency"])}
        problem = {"id": pid, "no": no, "role": role, "title": str(data["title"]), "tier": str(data.get("tier", "")),
                   "signature": signature, "time_limit_ms": limits, "score": score, "examples": examples,
                   "prep": [str(p) for p in data.get("prep", [])], "uses": [str(p) for p in data.get("uses", [])],
                   "markdown": markdown}
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("%s 의 형식이 맞지 않습니다: %s" % (shown, _why(error)))
    return problem


def load_dungeon(entry, root=None):
    """출제된 던전 하나의 공개 파일을 읽어 entry(index 항목)에 더한 dict 를 돌려줌. 못 읽으면 BankError.

    더하는 키: dir, intro(md), skills, problems(meta 순서). 문제마다 id, no, role, title, tier, signature,
    time_limit_ms, score(없으면 None), examples, prep, uses, markdown."""
    ddir = dungeon_dir(entry["id"], root)
    meta = _read_json(os.path.join(ddir, "meta.json"), "meta.json")
    intro_path = os.path.join(ddir, "intro.md")
    intro = _read_text(intro_path, "intro.md") if os.path.isfile(intro_path) else ""
    try:
        skills = [str(skill) for skill in meta.get("skills", [])]
        items = list(meta["problems"])
        problems = [_problem(ddir, item) for item in items]
    except (KeyError, TypeError, ValueError) as error:
        raise BankError("meta.json 의 형식이 맞지 않습니다: %s" % _why(error))
    ids = [p["id"] for p in problems]
    if len(set(ids)) != len(ids):
        raise BankError("meta.json 에 같은 문제 id 가 두 번 있습니다.")
    if [p["role"] for p in problems].count("boss") != 1 or problems[-1]["role"] != "boss":
        raise BankError("meta.json 에는 보스 문제가 정확히 하나, 마지막에 있어야 합니다.")
    return dict(entry, dir=ddir, intro=intro, skills=skills, problems=problems)


# 비밀 파일과 봉인

def problem_ids(ddir):
    """던전 폴더 안의 문제 폴더 이름(p1~p9, boss). meta.json 이 아니라 폴더를 봄(평문 작업본을 빠짐없이 찾으려는 것임)."""
    try:
        names = os.listdir(ddir)
    except OSError:
        return []
    return sorted(name for name in names if PROBLEM_ID.match(name) and os.path.isdir(os.path.join(ddir, name)))


def plain_secret_paths(ddir):
    """던전 폴더에 평문으로 놓인 비밀 파일의 상대 경로 목록("p1/solution.py", "p1/wrong/rescan.py", "review.json")."""
    rels = [name for name in DUNGEON_SECRETS if os.path.isfile(os.path.join(ddir, name))]
    for pid in problem_ids(ddir):
        folder = os.path.join(ddir, pid)
        rels += ["%s/%s" % (pid, name) for name in SECRET_FILES if os.path.isfile(os.path.join(folder, name))]
        wrong = os.path.join(folder, WRONG_DIR)
        if os.path.isdir(wrong):
            rels += ["%s/%s/%s" % (pid, WRONG_DIR, name) for name in sorted(os.listdir(wrong))
                     if name.endswith(WRONG_EXTS) and os.path.isfile(os.path.join(wrong, name))]
    return rels


def load_secrets(ddir):
    """비밀 파일을 {상대 경로: 내용} 으로. sealed.json 의 blob 을 풀고, 평문 파일이 있으면 평문이 이김. 못 풀면 BankError."""
    files = {}
    sealed = os.path.join(ddir, SEALED_NAME)
    if os.path.isfile(sealed):
        try:
            files.update(study.unseal_blob(study.read_json(sealed)["blob"]))
        except (OSError, ValueError, KeyError, TypeError, zlib.error) as error:
            raise BankError("%s 을 풀 수 없습니다: %s" % (SEALED_NAME, error))
    for rel in plain_secret_paths(ddir):
        files[rel] = _read_text(os.path.join(ddir, *rel.split("/")), rel)
    return files


def secret_json(secrets, rel):
    """비밀 파일 하나를 JSON 으로 읽음. 없으면 None, 깨졌으면 BankError."""
    text = secrets.get(rel)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError as error:
        raise BankError("%s 을 읽을 수 없습니다: %s" % (rel, error))


def parse_hints(text):
    """hints.md 를 `## 1`, `## 2` … 절의 본문 목록으로. 절 머리가 없는 앞부분은 버림."""
    hints, current = [], None
    for line in (text or "").splitlines():
        if HINT_HEAD.match(line.strip()):
            current = []
            hints.append(current)
        elif current is not None:
            current.append(line)
    return ["\n".join(lines).strip() + "\n" for lines in hints]
