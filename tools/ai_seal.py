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
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank as aibank  # noqa: E402
from aiprep import gen as genlib  # noqa: E402
from tools import web_seal  # noqa: E402
from webprep import bank  # noqa: E402

NOTE = ("AI 비전 개론의 문항·문장·사실 목록·검토 서명 묶음입니다(스포일러 방지용). 출제자는 tools/ai_seal.py unseal 로 풉니다. "
        "공개 저장소에 들어간 봉인은 누구나 풀 수 있으니 과제 마감 전 과제 근거 문항은 올리지 않습니다.")
PARENTS = ("items", "mocks")
SAMPLES = 10
USAGE = """AI 비전 개론 봉인 도구 (출제자용)

문항 묶음(ai/items/<id>/work/)과 모의고사(ai/mocks/<id>/work/)의 평문은 커밋하지 않고 폴더마다 sealed.json 하나로 묶어
커밋합니다. 암호화는 아니고, 실수로 답을 미리 보지 않게 가려 두는 용도입니다.

  python tools/ai_seal.py seal [i05 m1 ...] [--keep]   work/ → sealed.json (평문 삭제, --keep 이면 평문 유지)
  python tools/ai_seal.py unseal [i05 ...]             sealed.json → work/ (고칠 때)
  python tools/ai_seal.py check                        봉인 안 된 평문이 있거나 sealed.json 이 깨졌으면 실패
  python tools/ai_seal.py brief i05 --out DIR          재풀이자에게 줄 공개본(정답 없음)을 저장소 밖 DIR 에 만듦

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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("seal", "unseal", "check", "brief"):
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
    for iid, idir in targets(bank_dir, opts.targets):
        if command == "seal":
            seal(idir, iid, opts.keep)
        elif os.path.isfile(os.path.join(idir, bank.SEALED_NAME)):
            unseal(idir, iid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
