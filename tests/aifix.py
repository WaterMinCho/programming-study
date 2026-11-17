# -*- coding: utf-8 -*-
"""AI 비전 개론 테스트가 같이 쓰는 고정 은행 도우미.

pc_bank(dest) 는 tests/ai_bank 를 dest 에 복사하고 상황별 코드 자료 tests/ai_bank_pc(뼈대 S90, 학습 노트 l18, 문항 묶음 pc)를
덮은 뒤 index.json 의 pages·order·patterns 를 고침. 기존 고정 은행은 그대로 두어 상황별 코드가 없는 테스트의 기대값이 바뀌지
않게 함. 서명은 넣지 않으니 서명이 필요한 테스트는 만든 사본에서 서명함.

apc_bank(dest) 는 pc_bank 위에 응용 코딩 실습 자료 tests/ai_bank_apc(뼈대 patterns/apc/S190, 학습 노트 al18, 문항 묶음 apc)를
덮고 index.json 에 응용 차시 a90(노트 al90, 자료 없음)과 무리 apc 를 더함. app_lesson(dest) 는 l90·i90 을 al90·a90 으로 옮기고
목록에 a90 이 없으면 더해 응용 차시 a90 을 실제로 읽히게 함.
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_BANK = os.path.join(ROOT, "tests", "ai_bank")
PC_FILES = os.path.join(ROOT, "tests", "ai_bank_pc")
APC_FILES = os.path.join(ROOT, "tests", "ai_bank_apc")
PATTERNS = {"id": "pc", "page": "l18", "title": "상황별 코드",
            "units": {"18a": {"after": "i90", "name": "학습 루프"}, "18b": {"after": "i90", "name": "평가 루프"}}}
APP_PATTERNS = {"id": "apc", "course": "app", "folder": "apc", "page": "al18", "title": "코딩으로 실전학습하기",
                "units": {"a18a": {"after": "a90", "name": "응용 루프"}, "a18b": {"after": "a90", "name": "응용 평가"}}}
APP_LESSON = {"id": "a90", "no": 90, "course": "app", "title": "응용 시험 차시", "page": "al90", "date": None, "weight": 1.0,
              "units": 2, "hw_due": None}


def pc_bank(dest):
    """상황별 코드가 든 고정 은행을 dest 에 만들고 dest 를 돌려줌. dest 는 없거나 빈 폴더여야 함."""
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(AI_BANK, dest, ignore=skip, dirs_exist_ok=True)
    shutil.copytree(PC_FILES, dest, ignore=skip, dirs_exist_ok=True)
    path = os.path.join(dest, "index.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["pages"].append({"id": "l18", "title": "상황별 코드"})
    data["order"].append("l18")
    data["patterns"] = [json.loads(json.dumps(PATTERNS))]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    return dest


def _edit_index(dest, fn):
    path = os.path.join(dest, "index.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fn(data)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def apc_bank(dest):
    """pc 와 응용 무리 apc 가 함께 든 고정 은행을 dest 에 만들고 dest 를 돌려줌. dest 는 없거나 빈 폴더여야 함."""
    pc_bank(dest)
    shutil.copytree(APC_FILES, dest, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)

    def add(data):
        data["pages"].append({"id": "al18", "title": "코딩으로 실전학습하기"})
        data["order"].append("al18")
        data["patterns"].append(json.loads(json.dumps(APP_PATTERNS)))
    _edit_index(dest, _add_app_lesson)
    _edit_index(dest, add)
    return dest


def _add_app_lesson(data):
    if not any(p["id"] == "al90" for p in data["pages"]):
        data["pages"].append({"id": "al90", "title": "응용 90차시 시험 노트"})
        data["order"].append("al90")
    if not any(e["id"] == "a90" for e in data["lessons"]):
        data["lessons"].append(json.loads(json.dumps(APP_LESSON)))


def app_lesson(dest):
    """dest 은행의 l90·i90(평문 work/)을 al90·a90 으로 옮겨 적어 응용 차시 a90 을 출제된 차시로 만듦. 그림 파일 이름은 옮기지 않음."""
    for source, target in (("learn/l90", "learn/al90"), ("items/i90", "items/a90")):
        shutil.copytree(os.path.join(dest, source), os.path.join(dest, target), dirs_exist_ok=True)
    for folder in (os.path.join(dest, "learn", "al90"), os.path.join(dest, "items", "a90")):
        for base, _, names in os.walk(folder):
            for name in names:
                if name.endswith((".json", ".md", ".py")):
                    path = os.path.join(base, name)
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                    text = text.replace("i90", "a90").replace("l90", "al90").replace("90a", "a90a").replace("90b", "a90b")
                    with open(path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(text)
    _edit_index(dest, _add_app_lesson)
    return dest
