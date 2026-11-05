#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 비전 개론 문항 묶음(ai/items/*, ai/mocks/*)의 work/ 를 sealed.json 하나로 묶고 푸는 출제자용 도구. 명령은 USAGE 에 있음.

tools/web_seal.py 의 함수(secrets_of, remove_plain, sealed_problem, inside)와 webprep.bank 의 봉인 규칙을 그대로 씀. 학습 노트와
코드 뼈대(ai/learn, ai/patterns)는 공개라 봉인하지 않음. 봉인은 base64 와 zlib 로 감쌌을 뿐이라 우연히 답을 보지 않게 가리는
장치이고, 내용을 바꾸지 않으므로 봉인 앞뒤로 work/review.json 의 해시가 그대로 맞음.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank as aibank  # noqa: E402
from aiprep import gen as genlib  # noqa: E402
from aiprep import skel  # noqa: E402
from tools import web_seal  # noqa: E402
from webprep import bank  # noqa: E402

NOTE = ("AI 비전 개론의 문항·문장·사실 목록·검토 서명 묶음입니다(스포일러 방지용). 출제자는 tools/ai_seal.py unseal 로 풉니다. "
        "공개 저장소에 들어간 봉인은 누구나 풀 수 있으니 과제 마감 전 과제 근거 문항은 올리지 않습니다.")
PARENTS = ("items", "mocks")
SAMPLES = 10
SKEL_SEEDS = (1, 2, 3)  # 순서·고칠 줄 카드 견본 시드
SKEL_FADES = (("f0", None), ("f2", 2), ("f3", 4))  # 뼈대 빈칸 견본 이름과 같은 판 자리 모두에 줄 상자
WHOLE_KEY = re.compile(r"(S\d+) (.+) 전체\Z")
SEED_KEY = re.compile(r"(pc-[ox]\d{2,3}) 시드 (\d+)\Z")
SAMPLE_KEY = re.compile(r"(pc-k\d{2,3}) (f\d)\Z")
LEVEL_FILES = {7: "1_l7.md", 15: "2_l15.md", 20: "3_l20.md"}  # 세 수준 공개본의 수준 파일. 이 순서로 엶
LEVELS_ANSWERS = "levels_answers.json"
USAGE = """AI 비전 개론 봉인 도구 (출제자용)

문항 묶음(ai/items/<id>/work/)과 모의고사(ai/mocks/<id>/work/)의 평문은 커밋하지 않고 폴더마다 sealed.json 하나로 묶어
커밋합니다. 암호화는 아니고, 실수로 답을 미리 보지 않게 가려 두는 용도입니다.

  python tools/ai_seal.py seal [i05 m1 ...] [--keep]   work/ → sealed.json (평문 삭제, --keep 이면 평문 유지)
  python tools/ai_seal.py unseal [i05 ...]             sealed.json → work/ (고칠 때)
  python tools/ai_seal.py check                        봉인 안 된 평문이 있거나 sealed.json 이 깨졌으면 실패
  python tools/ai_seal.py brief i05 --out DIR          재풀이자에게 줄 공개본(정답 없음)을 저장소 밖 DIR 에 만듦
  python tools/ai_seal.py brief pc --out DIR           상황별 코드 공개본. sheet.md 를 다 푼 뒤에 skel.md 를 엽니다
  python tools/ai_seal.py levels l04 [l05 ...] --out DIR
                                                       학습 노트의 세 수준 블록 재풀이 공개본. 블록마다 폴더 하나이고
                                                       수준 파일을 하나씩 열며 levels_answers.json 을 채웁니다

--bank DIR 로 은행 폴더를 바꿀 수 있습니다(기본 ai/).
"""


def item_dirs(bank_dir):
    """봉인 대상 폴더 [(id, 경로)]. items/ 와 mocks/ 아래 폴더 전부(common, pc 포함)."""
    out = []
    for parent in PARENTS:
        folder = os.path.join(bank_dir, parent)
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            path = os.path.join(folder, name)
            if os.path.isdir(path) and not name.startswith((".", "_")):
                out.append((name, path))
    return out


def targets(bank_dir, tokens):
    found = dict(item_dirs(bank_dir))
    for token in tokens:
        if token not in found:
            raise SystemExit("문항 묶음이나 모의고사 폴더가 없습니다: %s (은행 %s)" % (token, bank_dir))
    return [(iid, found[iid]) for iid in (tokens or sorted(found))]


def seal(idir, iid, keep=False):
    files = web_seal.secrets_of(idir, iid)
    sealed = os.path.join(idir, bank.SEALED_NAME)
    if not files:
        if os.path.isfile(sealed):
            os.remove(sealed)
            print("봉인할 비밀 파일이 없어 sealed.json 을 지웠습니다: %s" % iid)
        else:
            print("봉인할 비밀 파일이 없습니다: %s" % iid)
        return
    study.write_text(sealed, bank.seal_text(files, NOTE))
    if not keep:
        web_seal.remove_plain(idir)
    print("봉인: %s (파일 %d개%s)" % (iid, len(files), ", 평문 유지" if keep else ""))


def unseal(idir, iid):
    files = web_seal.secrets_of(idir, iid)
    for rel, text in sorted(files.items()):
        study.write_text(os.path.join(idir, bank.WORK_DIR, *rel.split("/")), text)
    print("봉인 해제: %s (파일 %d개). 고친 뒤 verify_ai.py 로 확인하고 seal 로 다시 묶으세요." % (iid, len(files)))


def check(bank_dir):
    dirty, broken = [], []
    for iid, idir in item_dirs(bank_dir):
        rel = os.path.relpath(idir, bank_dir).replace(os.sep, "/")
        dirty += ["%s/%s/%s" % (rel, bank.WORK_DIR, name) for name in bank.plain_secret_paths(idir)]
        why = web_seal.sealed_problem(idir)
        if why:
            broken.append("%s/%s: %s" % (rel, bank.SEALED_NAME, why))
    shown = study.shown_path(bank_dir).replace(os.sep, "/")
    if dirty:
        print("봉인되지 않은 평문 작업본이 있습니다. `python tools/ai_seal.py seal` 을 실행하세요:")
        for line in dirty:
            print("  %s/%s" % (shown, line))
    if broken:
        print("풀리지 않는 sealed.json 이 있습니다:")
        for line in broken:
            print("  %s/%s" % (shown, line))
    if dirty or broken:
        return 1
    print("OK: AI 비전 개론 은행에 봉인되지 않은 평문 작업본이 없습니다.")
    return 0


# 공개본

def _blank_answers(stem):
    return [""] * len(aibank.BLANK.findall(stem or ""))


def option_order(item):
    """공개본 고르기의 보기 순서(원래 번호 목록). 답안에 적어 두면 원래 0번 보기가 몇 번으로 갔는지 보여 답이 드러나므로 적지 않고
    채점 때 같은 시드로 다시 만듦. genlib.Rng 라 파이썬 판이 달라도 같은 순서임."""
    return genlib.Rng("%s 보기" % item["id"]).shuffle(list(range(len(item.get("options") or []))))


def gen_option_order(gid, seed, count):
    """공개본 생성기 고르기의 보기 순서(원래 번호 목록). 생성기는 정답을 맨 앞에 두는 일이 많아 그대로 보이면 답이 드러나므로 섞고,
    채점 때 같은 생성기 id 와 시드로 다시 만듦."""
    return genlib.Rng("%s %s 보기" % (gid, seed)).shuffle(list(range(count)))


def statement_rows(topic):
    """공개본 주제 문장 [(꼬리표, 문장)]. statements.json 은 참 문장을 앞에 두고 id 도 그 순서로 매기므로 id 를 숨기고 섞은 순서에
    '<주제 id>-<번호>' 꼬리표를 붙임. 채점 때 같은 순서를 다시 만들어 문장 id 로 되돌림."""
    rows = sorted(topic.get("statements") or [], key=lambda statement: str(statement["id"]))
    genlib.Rng(str(topic.get("id"))).shuffle(rows)
    return [("%s-%d" % (topic.get("id"), n), statement) for n, statement in enumerate(rows, 1)]


# 상황별 코드 공개본(뼈대 카드)

def pattern_cards(bank_dir, group):
    """무리 하나의 뼈대와 공개 단원 카드 (skeletons, cards). l18 meta 의 units 에 적은 단원만."""
    skeletons = skel.load_patterns(bank_dir)
    note = aibank.load_note({"id": group["page"], "title": group["title"]}, bank_dir)
    units = {key: {"after": info["after"], "name": info["name"], "title": note["units"][key]["title"]}
             for key, info in group["units"].items() if key in note["visible"]}
    return skeletons, skel.cards(group, skeletons, units)


def _slot_cards(cards, pattern, variant):
    return [c for c in cards if c.get("part") == "slot" and c["pattern"] == pattern and c["variant"] == variant]


def whole_view(skeleton, variant, cards):
    """판 하나의 모든 slot 카드 자리를 한꺼번에 토큰으로 가린 견본(1단계, 키 "S1 표준형 전체"). 카드가 없으면 None.
    칸은 코드 위치 순이고 칸마다 slot 이 그 자리 id 임."""
    mine = _slot_cards(cards, skeleton["id"], variant)
    if not mine:
        return None
    return skel.slot_view(mine[0], skeleton, {}, masked=[c["id"] for c in mine[1:]], whole=False)


def skel_samples(card, skeleton, cards):
    """slot 카드 하나의 점차 지우기 견본 [(이름, view)](2단계). 같은 판 slot 카드 모두에 같은 상자를 줘서 f0·f2·f3 판을 만듦."""
    ids = [c["id"] for c in _slot_cards(cards, card["pattern"], card["variant"])]
    return [(name, skel.slot_view(card, skeleton, {sid: box for sid in ids})) for name, box in SKEL_FADES]


def skel_option_order(card, count):
    """공개본 뼈대 고르기의 보기 순서(원래 번호 목록). pick 은 정답 줄이 맨 앞이라 Rng 로 섞고, order 는 view 가 이미 섞었고
    change 는 코드 순서 그대로 보임."""
    order = list(range(count))
    if card.get("part") == "pick":
        genlib.Rng("%s 보기" % card["id"]).shuffle(order)
    return order


def skel_choice(card, skeleton, seed=None):
    """공개본 고르기 견본의 view. pick 은 시드가 없고 order·change 는 시드로 보기를 만듦."""
    if card["part"] == "pick":
        return skel.pick_view(card, skeleton)
    return skel.view(card, skeleton, seed)


def brief_patterns(bank_dir, group, out_dir):
    """상황별 코드 공개본. sheet.md 에는 판마다 모든 자리를 한꺼번에 가린 판과 순서·줄·고칠 줄 고르기를 두고,
    skel.md 에는 slot 카드마다 f0·f2·f3 견본을 둠. skel.md 는 sheet.md 답을 answers.json 에 다 적은 뒤에 엶(뼈대 빈칸 견본끼리 서로의 답을 보여 줌).
    line_answer·valid·wrong why·aim·facts.json 은 넣지 않음."""
    skeletons, cards = pattern_cards(bank_dir, group)
    gid = group["id"]
    lines = ["# %s 재풀이 문제지" % gid, "",
             "%s 을 읽기 전에 위에서부터 풀고 answers.json 을 채웁니다. 다 적은 뒤에 skel.md 를 엽니다. 빈칸은 ①② 순서대로 칸마다 "
             "글을 적고, 고르기는 이 문제지에 적힌 번호(1부터)를 씁니다." % group["page"], ""]
    answers = {}
    for sid in sorted(skeletons, key=lambda k: int(k[1:])):
        for variant in skeletons[sid]["variants"]:
            view = whole_view(skeletons[sid], variant, cards)
            if view is None:
                continue
            key = "%s %s 전체" % (sid, variant)
            lines += ["## %s" % key, "", aibank.number_blanks(view["stem"], code=True), ""]
            answers[key] = [""] * len(view["blanks"])
    for card in cards:
        if card["part"] == "slot":
            continue
        skeleton = skeletons[card["pattern"]]
        seeds = [None] if card["part"] == "pick" else list(SKEL_SEEDS)
        for seed in seeds:
            view = skel_choice(card, skeleton, seed)
            key = card["id"] if seed is None else "%s 시드 %d" % (card["id"], seed)
            lines += ["## %s" % key, "", view["stem"], "", "모두 고르기입니다." if view.get("multi") else "하나를 고릅니다.", ""]
            for n, k in enumerate(skel_option_order(card, len(view["options"])), 1):
                lines += ["%d." % n, "", "```python", view["options"][k]["text"], "```", ""]
            answers[key] = {"picked": []}
    notes = _note_lines(bank_dir, group["page"])
    if notes:
        lines += ["## 학습 노트의 먼저 풀어 보기와 떠올리기", ""] + notes + [""]
    samples = ["# %s 뼈대 빈칸 견본" % gid, "",
               "sheet.md 의 답을 answers.json 에 모두 적은 뒤에 엽니다. 견본마다 가린 자리가 다르고 서로의 답을 보여 주므로 위에서부터 "
               "풀고, 이미 적은 답은 고치지 않습니다. 견본 이름의 f0·f2·f3 은 함께 가린 자리 수입니다.", ""]
    for card in cards:
        if card["part"] != "slot":
            continue
        for name, view in skel_samples(card, skeletons[card["pattern"]], cards):
            key = "%s %s" % (card["id"], name)
            samples += ["## %s" % key, "", aibank.number_blanks(view["stem"], code=True), ""]
            answers[key] = [""] * len(view["blanks"])
    os.makedirs(out_dir, exist_ok=True)
    study.write_text(os.path.join(out_dir, "sheet.md"), "\n".join(lines).rstrip() + "\n")
    study.write_text(os.path.join(out_dir, "skel.md"), "\n".join(samples).rstrip() + "\n")
    study.write_text(os.path.join(out_dir, "answers.json"), json.dumps(answers, ensure_ascii=False, indent=1) + "\n")
    print("공개본을 만들었습니다: %s (sheet.md, skel.md, answers.json)" % out_dir)
    print("재풀이자는 %s 을 읽기 전에 sheet.md 를 풀어 answers.json 에 적고, 그 뒤에 skel.md 를 엽니다. 그다음 "
          "`python tools/verify_ai.py %s --answers answers.json` 으로 대조합니다." % (group["page"], gid))


def _note_lines(bank_dir, page_id):
    """학습 노트의 먼저 풀어 보기·떠올리기(정답을 뺀 것)."""
    lines = []
    pdir = aibank.page_dir(page_id, bank_dir)
    if not os.path.isfile(os.path.join(pdir, "page.md")):
        return lines
    meta = study.read_json(os.path.join(pdir, "meta.json"))
    parsed = aibank.parse_page(study.read_text(os.path.join(pdir, "page.md")), meta.get("sections") or {})
    for key in parsed["order"]:
        for step in parsed["units"][key]["steps"]:
            for block in step["blocks"]:
                if block["kind"] == "guess":
                    lines.append("- %s/%s 먼저 풀어 보기 %s: %s" % (key, step["no"], block.get("id"), block.get("q", "")))
                    lines += ["  %d. %s" % (n, text) for n, text in enumerate(block.get("options") or [], 1)]
                elif block["kind"] == "recall":
                    lines.append("- %s/%s 떠올리기 %s: %s" % (key, step["no"], block.get("id"), block.get("q", "")))
    return lines


def brief(bank_dir, iid, out_dir):
    """재풀이자에게 줄 공개본 sheet.md, cloze.md 와 빈 답안 answers.json. 정답·해설·why·facts.json 은 넣지 않음.
    빈칸판은 참 문장에만 있어 문장 옆에 두면 판정이 드러나므로 cloze.md 로 따로 뺌. 답안의 문장 칸은 참·거짓과 상관없이 모두
    {"ok": null, "cloze": [""]} 꼴이고, 고르기 칸에는 보기 순서를 적지 않음. 생성기 표본은 params 를 빼고(form 같은 값이 답을
    알려 줌) 고르기 보기를 gen_option_order 로 섞어 보임."""
    idir = os.path.join(bank_dir, "items", iid)
    if not os.path.isfile(os.path.join(idir, "meta.json")):
        raise SystemExit("문항 묶음의 meta.json 이 있어야 합니다: %s" % iid)
    for folder in (ROOT, bank_dir):
        if web_seal.inside(out_dir, folder):
            raise SystemExit("공개본은 저장소 밖에 만들어 주세요. 저장소 안에 두면 커밋에 섞일 수 있습니다: %s" % out_dir)
    group = next((g for g in aibank.read_index(bank_dir)["patterns"] if g["id"] == iid), None)
    if group is not None:
        brief_patterns(bank_dir, group, out_dir)
        return
    secrets = web_seal.secrets_of(idir, iid)
    meta = study.read_json(os.path.join(idir, "meta.json"))
    items = json.loads(secrets.get("items.json", '{"items": []}')).get("items") or []
    topics = json.loads(secrets.get("statements.json", '{"topics": []}')).get("topics") or []
    lines = ["# %s 재풀이 문제지" % iid, "", "정답을 보기 전에 풀고 answers.json 을 채우세요. 고르기는 이 문제지에 적힌 번호(1부터)를 씁니다. "
             "주제 문장은 ok 에 참이면 true, 거짓이면 false 를 적습니다.", ""]
    answers, clozes = {}, []
    for item in items:
        lines += ["## %s" % item["id"], "", item.get("stem", ""), ""]
        if item.get("kind") == "choice":
            lines += ["%d. %s" % (n, item["options"][k]["text"]) for n, k in enumerate(option_order(item), 1)] + [""]
            answers[item["id"]] = {"picked": []}
        else:
            answers[item["id"]] = _blank_answers(item.get("stem", ""))
    for topic in topics:
        lines += ["## 주제 %s · %s" % (topic.get("id"), topic.get("title", "")), ""]
        for tag, statement in statement_rows(topic):
            lines.append("- %s: %s (참/거짓)" % (tag, statement["text"]))
            answers[tag] = {"ok": None, "cloze": [""]}
            if statement.get("cloze"):
                clozes.append("- %s: %s" % (tag, statement["cloze"]["text"]))
        lines.append("")
    if clozes:
        lines += ["문장 판정을 answers.json 에 모두 적은 뒤에 cloze.md 를 열어 빈칸판을 풉니다. 빈칸판은 참 문장으로만 만들어서 판정 "
                  "전에 열면 어느 문장이 참인지 드러납니다.", ""]
    aibank.load_common(bank_dir)
    for spec in genlib.load_module(os.path.join(idir, "gens.py"), "ai_brief_%s" % iid):
        lines += ["## 생성기 %s" % spec.id, "", spec.doc.strip(), ""]
        samples = {}
        for seed in range(1, SAMPLES + 1):
            made = genlib.run(spec, seed)
            lines += ["### 시드 %d" % seed, "", made["stem"], ""]
            if made["kind"] == "choice":
                order = gen_option_order(spec.id, seed, len(made["options"]))
                lines += ["%d. %s" % (n, made["options"][k]["text"]) for n, k in enumerate(order, 1)] + [""]
                samples[str(seed)] = {"picked": []}
            else:
                samples[str(seed)] = _blank_answers(made["stem"])
        answers[spec.id] = samples
    notes = _note_lines(bank_dir, str(meta.get("page", "")))
    if notes:
        lines += ["## 학습 노트의 먼저 풀어 보기와 떠올리기", ""] + notes + [""]
    os.makedirs(out_dir, exist_ok=True)
    study.write_text(os.path.join(out_dir, "sheet.md"), "\n".join(lines).rstrip() + "\n")
    if clozes:
        head = ["# %s 빈칸판" % iid, "", "sheet.md 의 문장 판정을 answers.json 에 모두 적은 뒤에 엽니다. 아래 꼬리표 칸의 cloze 에 빈칸에 들어갈 "
                "말을 적고, 이미 적은 ok 는 고치지 않습니다.", ""]
        study.write_text(os.path.join(out_dir, "cloze.md"), "\n".join(head + clozes) + "\n")
    study.write_text(os.path.join(out_dir, "answers.json"), json.dumps(answers, ensure_ascii=False, indent=1) + "\n")
    print("공개본을 만들었습니다: %s (sheet.md%s, answers.json)" % (out_dir, ", cloze.md" if clozes else ""))
    print("재풀이자는 학습 노트와 sheet.md 만 보고 answers.json 을 채우고, 문장 판정을 다 적은 뒤에 cloze.md 를 풉니다. 그다음 "
          "`python tools/verify_ai.py %s --answers answers.json` 으로 대조합니다." % iid)


# 세 수준 블록 공개본(학습 노트 기준, 봉인과 상관없음)

def _figure_lines(figure):
    """공개본의 그림 줄. 그림은 절대 경로, 캡션과 장 설명은 화면에 보이는 그대로. 내용(content)은 화면에 없어서 넣지 않음."""
    lines = ["그림: %s" % os.path.abspath(figure["path"]) if figure.get("path") else "그림: %s" % figure.get("file", "")]
    if figure.get("caption"):
        lines.append("캡션: %s" % figure["caption"])
    lines += ["장 %d: %s" % (n, frame["text"]) for n, frame in enumerate(figure.get("frames") or [], 1) if frame.get("text")]
    return lines


def step_brief(pid, key, step):
    """단계 글(ai-* 블록을 뺀 글과 그림). 떠올리기·왜일까요는 답이 들어 있어 넣지 않음."""
    lines = ["# %s %s/%s %s" % (pid, key, step["no"], step["title"]), ""]
    for block in step["blocks"]:
        if block["kind"] == "text":
            lines += [aibank.strip_marks(block["markdown"]), ""]
        elif block["kind"] == "figure":
            lines += _figure_lines(block) + [""]
    return "\n".join(lines).rstrip() + "\n"


def level_brief(pid, key, step, block, level):
    """수준 하나의 공개본. 글, 그림, (20살) 코드·자주 하는 착각, 물음. answer·why는 넣지 않음."""
    lines = ["# %s %s/%s %s %d살 수준" % (pid, key, step["no"], block["id"], level["level"]), "",
             "세 수준으로 다시 보기%s" % (" · " + block["concept"] if block.get("concept") else ""), ""]
    if level.get("figure"):
        lines += _figure_lines(level["figure"]) + [""]
    lines += [level["text"], ""]
    if level.get("code"):
        lines += ["```python", level["code"], "```", ""]
    if level.get("mistake"):
        lines += ["자주 하는 착각: %s" % level["mistake"], ""]
    lines += ["## 확인 물음", "", level["q"], ""]
    return "\n".join(lines).rstrip() + "\n"


def levels(bank_dir, pages, out_dir):
    """세 수준 블록 재풀이 공개본. 블록마다 폴더 <노트>_<단원><단계>_<id>/ 에 0_step.md(단계 글)와 수준 파일 셋, 맨 위에 빈 답안
    levels_answers.json({"l04 4b/3 v1 7": ""}). 답안이 이미 있으면 적힌 답은 그대로 두고 키만 더함. page.md 는 블록 JSON 에 정답이
    있어 재풀이자가 열지 않음."""
    for folder in (ROOT, bank_dir):
        if web_seal.inside(out_dir, folder):
            raise SystemExit("공개본은 저장소 밖에 만들어 주세요. 저장소 안에 두면 커밋에 섞일 수 있습니다: %s" % out_dir)
    known = {p["id"]: p for p in aibank.read_index(bank_dir)["pages"]}
    target = os.path.join(out_dir, LEVELS_ANSWERS)
    answers = study.read_json(target) if os.path.isfile(target) else {}
    made = []
    for pid in pages:
        if pid not in known:
            raise SystemExit("학습 노트가 없습니다: %s (은행 %s)" % (pid, bank_dir))
        note = aibank.load_note(known[pid], bank_dir)
        for key in note["order"]:
            for step in note["units"][key]["steps"]:
                for block in step["blocks"]:
                    if block["kind"] != "levels":
                        continue
                    if block.get("error"):
                        raise SystemExit("%s %s/%s 의 세 수준 블록을 읽지 못했습니다: %s" % (pid, key, step["no"], block["error"]))
                    folder = os.path.join(out_dir, "%s_%s%s_%s" % (pid, key, step["no"], block["id"]))
                    study.write_text(os.path.join(folder, "0_step.md"), step_brief(pid, key, step))
                    for level in block["levels"]:
                        study.write_text(os.path.join(folder, LEVEL_FILES[level["level"]]), level_brief(pid, key, step, block, level))
                        answers.setdefault("%s %s/%s %s %d" % (pid, key, step["no"], block["id"], level["level"]), "")
                    made.append(os.path.basename(folder))
    os.makedirs(out_dir, exist_ok=True)
    study.write_text(target, json.dumps(answers, ensure_ascii=False, indent=1) + "\n")
    print("세 수준 공개본을 만들었습니다: %s (블록 %d개: %s)" % (out_dir, len(made), ", ".join(made) or "없음"))
    print("재풀이자는 블록 폴더마다 0_step.md 를 읽고, 1_l7.md 의 물음 답을 %s 에 적은 뒤에 2_l15.md 를 엽니다. 같은 방식으로 "
          "3_l20.md 까지 갑니다. 이미 적은 답은 고치지 않고 page.md 는 열지 않습니다(블록 JSON 에 정답이 있음). 다 적은 뒤 "
          "`python tools/verify_ai.py --levels-answers %s` 로 대조합니다." % (LEVELS_ANSWERS, target))
    return made


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("seal", "unseal", "check", "brief", "levels"):
        print(USAGE)
        return 2
    parser = argparse.ArgumentParser(prog="ai_seal.py %s" % argv[0])
    parser.add_argument("targets", nargs="*")
    parser.add_argument("--bank", default=aibank.AI_DIR)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--out")
    opts = parser.parse_args(argv[1:])
    bank_dir = os.path.abspath(opts.bank)
    command = argv[0]
    if command == "check":
        return check(bank_dir)
    if command == "brief":
        if len(opts.targets) != 1 or not opts.out:
            raise SystemExit("쓰는 법: python tools/ai_seal.py brief i05 --out DIR")
        brief(bank_dir, opts.targets[0], os.path.abspath(opts.out))
        return 0
    if command == "levels":
        if not opts.targets or not opts.out:
            raise SystemExit("쓰는 법: python tools/ai_seal.py levels l04 [l05 ...] --out DIR")
        levels(bank_dir, opts.targets, os.path.abspath(opts.out))
        return 0
    for iid, idir in targets(bank_dir, opts.targets):
        if command == "seal":
            seal(idir, iid, opts.keep)
        elif os.path.isfile(os.path.join(idir, bank.SEALED_NAME)):
            unseal(idir, iid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
