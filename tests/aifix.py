# -*- coding: utf-8 -*-
"""AI 비전 개론 테스트가 같이 쓰는 고정 은행 도우미.

pc_bank(dest) 는 tests/ai_bank 를 dest 에 복사하고 상황별 코드 자료 tests/ai_bank_pc(뼈대 S90, 학습 노트 l18, 문항 묶음 pc)를
덮은 뒤 index.json 의 pages·order·patterns 를 고침. 기존 고정 은행은 그대로 두어 상황별 코드가 없는 테스트의 기대값이 바뀌지
않게 함. 서명은 넣지 않으니 서명이 필요한 테스트는 만든 사본에서 서명함.
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_BANK = os.path.join(ROOT, "tests", "ai_bank")
PC_FILES = os.path.join(ROOT, "tests", "ai_bank_pc")
PATTERNS = {"id": "pc", "page": "l18", "title": "상황별 코드",
            "units": {"18a": {"after": "i90", "name": "학습 루프"}, "18b": {"after": "i90", "name": "평가 루프"}}}


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
