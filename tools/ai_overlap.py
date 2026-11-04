#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 비전 개론 글이 강의 글을 옮기지 않았는지 보는 겹침 검사(설계 8.8, 부록 A.5). 출제자 컴퓨터에서만 돌림(강의 자료는 저장소 밖).

  python tools/ai_overlap.py --lecture "$AI_LECTURE_DIR" [l05 i05 m1 l18 pc S1 ...] [--no-pdf]

강의 폴더는 인자나 환경 변수 AI_LECTURE_DIR 로만 받고 저장소에 적지 않음. 말뭉치는 대상 차시와 앞뒤 한 차시 폴더의 노트북
(markdown·code 셀, 출력 제외), docx, PDF 와 맨 위의 요약본·LectureNote.docx·대학원_강의안 전부. PDF 는 pypdf 로 읽고 pypdf 가
없으면 실패함(--no-pdf 로 건너뛰면 결과에 "PDF 안 봄"을 적음).

실패: 산문에서 한글 10자 이상을 포함한 20자 이상 같은 구간, 코드에서 공백을 뺀 120자 이상 같은 구간이나 10자 넘는 줄 셋이 이어
같은 곳. 14~19자 근접 구간은 10개까지 검토자에게 보임. 결과에는 우리 글 쪽 위치와 앞 30자만 적고 강의 글은 찍지 않음.
대상은 학습 노트(글, 캡션, 프레임 줄, ai-* 블록 글), 문항(지문, 보기, why, 해설), 문장, facts.json 의 text, 생성기 견본 5개, 모의고사,
상황별 코드 뼈대(ai/patterns/S*.json 의 판 줄과 고르기 오답 줄은 코드, 상황·지문·해설·why·aim·hint 는 산문)와 items/pc 의
facts·errata 글. 뼈대는 노트북 원문을 옮기지 않고 같은 API 를 이 트랙 이름(x, y, out, loader)으로 써서 겹침 규칙을 면제 없이
통과시킴. 대상에 l18·pc·S1 가운데 하나라도 있으면 l18 노트, 뼈대 전부, items/pc 가 함께 대상이 되고 말뭉치에 모든 차시 폴더를 넣음.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from aiprep import bank as aibank  # noqa: E402
from aiprep import gen as genlib  # noqa: E402
from webprep import bank as webbank  # noqa: E402

PROSE_MIN, PROSE_HANGUL, NEAR_MIN, NEAR_SHOWN = 20, 10, 14, 10
CODE_MIN, LINE_MIN, LINE_RUN = 120, 10, 3
GEN_SAMPLES = 5
HANGUL = re.compile("[가-힣]")
FENCE = re.compile(r"^\s*(```|~~~)\s*([\w-]*)\s*$")
PATTERN_TARGET = re.compile(r"(l18|pc|S\d+)\Z")


def prose_norm(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in text if ch.isalnum())


def code_norm(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


# 말뭉치

def _pdf_text(path):
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def _docx_text(path):
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", "replace")
    return re.sub(r"<[^>]+>", "", xml.replace("</w:p>", "\n"))


def _notebook(path):
    """(산문, 코드). markdown·code 셀 글만, 출력은 뺌."""
    data = json.loads(study.read_text(path))
    prose, code = [], []
    for cell in data.get("cells") or []:
        source = cell.get("source") or ""
        source = "".join(source) if isinstance(source, list) else str(source)
        if cell.get("cell_type") == "code":
            code.append(source)
        prose.append(source)
    return "\n".join(prose), "\n".join(code)


def lesson_folders(lecture, numbers):
    """강의 폴더 아래에서 차시 번호(앞뒤 한 차시 포함)가 이름에 든 폴더."""
    out = []
    wanted = set()
    for n in numbers:
        wanted |= {n - 1, n, n + 1}
    for name in sorted(os.listdir(lecture)):
        path = os.path.join(lecture, name)
        found = re.search(r"(?<!\d)(\d{1,2})차시", unicodedata.normalize("NFC", name))  # macOS 는 한글 이름을 NFD 로 줌
        if os.path.isdir(path) and found and (not numbers or int(found.group(1)) in wanted):
            out.append(path)
    return out


def corpus(lecture, numbers, use_pdf=True):
    """{"prose": [글], "code": [글], "skipped_pdf": bool}."""
    prose, code = [], []
    files = []
    for folder in lesson_folders(lecture, numbers):
        for here, _, names in os.walk(folder):
            files += [os.path.join(here, n) for n in sorted(names)]
    for name in sorted(os.listdir(lecture)):
        path = os.path.join(lecture, name)
        if os.path.isfile(path):
            files.append(path)
        elif os.path.isdir(path) and "대학원" in unicodedata.normalize("NFC", name):
            for here, _, names in os.walk(path):
                files += [os.path.join(here, n) for n in sorted(names)]
    for path in files:
        low = path.lower()
        if low.endswith(".ipynb"):
            text, source = _notebook(path)
            prose.append(text)
            code.append(source)
        elif low.endswith(".docx"):
            prose.append(_docx_text(path))
        elif low.endswith(".pdf") and use_pdf:
            prose.append(_pdf_text(path))
        elif low.endswith((".md", ".txt", ".py")):
            text = study.read_text(path)
            prose.append(text)
            code.append(text)
    return {"prose": prose, "code": code, "skipped_pdf": not use_pdf}


# 우리 글

def split_markdown(text):
    """마크다운을 (산문, 코드) 로. figure 의 캡션·프레임 줄과 ai-* 블록의 글 값은 산문에 넣음. ai-levels 블록의 수준 code 는 코드 쪽으로
    보내 120자·세 줄 규칙으로 봄."""
    prose, code, fence, lines = [], [], None, []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        found = FENCE.match(line)
        if fence is None:
            if found and found.group(2):
                fence, lines = found.group(2), []
            elif found:
                fence, lines = "code", []
            else:
                prose.append(line)
            continue
        if found and not found.group(2):
            body = "\n".join(lines)
            if fence == "figure":
                prose += [re.sub(r"^\s*(캡션:|내용:|\d+\.)\s*", "", ln) for ln in lines if not ln.strip().startswith(("파일:", "프레임:"))]
            elif fence.startswith("ai-"):
                try:
                    data = json.loads(body)
                except ValueError:
                    prose.append(body)
                else:
                    if fence == "ai-levels" and isinstance(data, dict) and isinstance(data.get("levels"), list):
                        levels = [dict(level) for level in data["levels"] if isinstance(level, dict)]
                        code += [str(level.pop("code")) for level in levels if "code" in level]
                        data = dict(data, levels=levels)
                    prose += list(_strings(data))
            else:
                code.append(body)
            fence = None
            continue
        lines.append(line)
    return "\n".join(prose), "\n".join(code)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def pattern_targets(bank_dir, index):
    """상황별 코드 대상 [(어디, 산문, 코드)]. 뼈대 파일마다 판 줄·오답 줄(코드)과 글(산문), 무리 문항 폴더의 facts·errata 글."""
    out = []
    folder = os.path.join(bank_dir, "patterns")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not re.match(r"S\d+\.json\Z", name):
            continue
        data = json.loads(study.read_text(os.path.join(folder, name)))
        for vname, variant in (data.get("variants") or {}).items():
            out.append(("patterns/%s %s 판" % (name, vname), str(variant.get("situation") or ""), "\n".join(variant.get("lines") or [])))
        for key in ("slots", "orders", "picks", "changes"):
            for entry in data.get(key) or []:
                prose = [str(entry.get(k) or "") for k in ("stem", "back", "explain", "hint")]
                code = []
                for wrong in entry.get("wrong") or []:
                    if isinstance(wrong, dict):
                        code.append(str(wrong.get("text") or ""))
                        prose += [str(wrong.get("why") or ""), str(wrong.get("aim") or "")]
                out.append(("patterns/%s %s" % (name, entry.get("id")), "\n".join(p for p in prose if p), "\n".join(code)))
    for group in index.get("patterns") or []:
        idir = aibank.items_dir(group["id"], bank_dir)
        if not os.path.isfile(os.path.join(idir, "meta.json")):
            continue
        facts = json.loads(webbank.load_secrets(idir).get("facts.json", '{"facts": []}'))
        for fact in facts.get("facts") or []:
            out.append(("%s facts %s" % (group["id"], fact.get("id")), str(fact.get("text") or ""), ""))
        for wrong in facts.get("errata") or []:
            out.append(("%s errata %s" % (group["id"], wrong.get("id")), "\n".join(str(wrong.get(k) or "") for k in ("lecture", "right")), ""))
    return out


def targets(bank_dir, wanted):
    """[(어디, 산문, 코드)]. wanted 는 lNN·iNN·mN·pc·SN 목록(없으면 전부). l18·pc·SN 가운데 하나라도 있으면 l18 노트와 상황별 코드
    대상 전부."""
    out = []
    index = aibank.read_index(bank_dir)
    patterns = not wanted or any(PATTERN_TARGET.match(t) for t in wanted)
    pages = [p["id"] for p in index["pages"] if not wanted or p["id"] in wanted
             or ("i" + p["id"][1:]) in wanted or (patterns and p["id"] in [g["page"] for g in index["patterns"]])]
    for pid in pages:
        path = os.path.join(aibank.page_dir(pid, bank_dir), "page.md")
        if os.path.isfile(path):
            prose, code = split_markdown(study.read_text(path))
            out.append(("%s page.md" % pid, prose, code))
    lessons = [e for e in index["lessons"] if not wanted or e["id"] in wanted or e["page"] in wanted]
    aibank.load_common(bank_dir)
    for entry in lessons:
        folder = aibank.items_dir(entry["id"], bank_dir)
        if not os.path.isfile(os.path.join(folder, "meta.json")):
            continue
        secrets = webbank.load_secrets(folder)
        for item in json.loads(secrets.get("items.json", '{"items": []}')).get("items") or []:
            texts = [item.get("stem", ""), item.get("explain", "")]
            texts += [o.get(k, "") for o in item.get("options") or [] for k in ("text", "why")]
            prose, code = split_markdown("\n".join(texts))
            out.append(("%s %s" % (entry["id"], item.get("id")), prose, code))
        for topic in json.loads(secrets.get("statements.json", '{"topics": []}')).get("topics") or []:
            for s in topic.get("statements") or []:
                out.append(("%s %s" % (entry["id"], s.get("id")), "\n".join([s.get("text", ""), s.get("why", ""),
                                                                           (s.get("cloze") or {}).get("text", "")]), ""))
        for fact in json.loads(secrets.get("facts.json", '{"facts": []}')).get("facts") or []:
            out.append(("%s facts %s" % (entry["id"], fact.get("id")), fact.get("text", ""), ""))
        for spec in genlib.load_module(os.path.join(folder, "gens.py"), "ai_overlap_%s" % entry["id"]):
            for seed in range(1, GEN_SAMPLES + 1):
                made = genlib.run(spec, seed)
                prose, code = split_markdown(made.get("stem", "") + "\n" + made.get("explain", ""))
                out.append(("%s %s 시드 %d" % (entry["id"], spec.id, seed), prose, code))
    for mock in index["mocks"]:
        if wanted and mock["id"] not in wanted:
            continue
        folder = aibank.mock_dir(mock["id"], bank_dir)
        if not os.path.isfile(os.path.join(folder, "meta.json")):
            continue
        secrets = webbank.load_secrets(folder)
        for item in json.loads(secrets.get("items.json", '{"items": []}')).get("items") or []:
            texts = [item.get("stem", ""), item.get("explain", "")] + [o.get("text", "") for o in item.get("options") or []]
            prose, code = split_markdown("\n".join(texts))
            out.append(("%s %s" % (mock["id"], item.get("id")), prose, code))
    if patterns:
        out += pattern_targets(bank_dir, index)
    return out


# 겹침

def overlaps(our, lecture):
    """our 는 [(어디, 산문, 코드)], lecture 는 corpus 결과. {"fail": [(어디, 앞 30자, 까닭)], "near": [(어디, 앞 30자)]}."""
    prose_windows, near_windows, code_windows = {}, {}, {}
    for n, (where, prose, code) in enumerate(our):
        flat = prose_norm(prose)
        for k in range(len(flat) - PROSE_MIN + 1):
            piece = flat[k:k + PROSE_MIN]
            if len(HANGUL.findall(piece)) >= PROSE_HANGUL:
                prose_windows.setdefault(piece, set()).add(n)
        for k in range(len(flat) - NEAR_MIN + 1):
            near_windows.setdefault(flat[k:k + NEAR_MIN], set()).add(n)
        packed = code_norm(code)
        for k in range(len(packed) - CODE_MIN + 1):
            code_windows.setdefault(packed[k:k + CODE_MIN], set()).add(n)
    failed, near = {}, set()
    for text in lecture["prose"]:
        flat = prose_norm(text)
        for k in range(len(flat) - NEAR_MIN + 1):
            piece = flat[k:k + NEAR_MIN]
            if piece in near_windows:
                near |= near_windows[piece]
                if k + PROSE_MIN <= len(flat):
                    longer = flat[k:k + PROSE_MIN]
                    for n in prose_windows.get(longer, ()):
                        failed.setdefault(n, "산문 %d자 이상 같음" % PROSE_MIN)
    for text in lecture["code"]:
        packed = code_norm(text)
        for k in range(len(packed) - CODE_MIN + 1):
            for n in code_windows.get(packed[k:k + CODE_MIN], ()):
                failed.setdefault(n, "코드 %d자 이상 같음" % CODE_MIN)
    runs = set()
    for text in lecture["code"]:
        lines = [code_norm(ln) for ln in text.split("\n")]
        lines = [ln for ln in lines if len(ln) > LINE_MIN]
        runs |= {tuple(lines[k:k + LINE_RUN]) for k in range(len(lines) - LINE_RUN + 1)}
    for n, (_, _, code) in enumerate(our):
        lines = [code_norm(ln) for ln in code.split("\n")]
        lines = [ln for ln in lines if len(ln) > LINE_MIN]
        if any(tuple(lines[k:k + LINE_RUN]) in runs for k in range(len(lines) - LINE_RUN + 1)):
            failed.setdefault(n, "%d자 넘는 코드 줄 %d개가 이어 같음" % (LINE_MIN, LINE_RUN))

    def head(n):
        where, prose, code = our[n]
        return where, " ".join((prose or code).split())[:30]
    fails = [head(n) + (why,) for n, why in sorted(failed.items())]
    close = [head(n) for n in sorted(near - set(failed))][:NEAR_SHOWN]
    return {"fail": fails, "near": close}


def main(argv=None, out=None):
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="ai_overlap.py")
    parser.add_argument("targets", nargs="*", help="lNN·iNN·mN (없으면 전부)")
    parser.add_argument("--lecture", default=os.environ.get("AI_LECTURE_DIR"))
    parser.add_argument("--bank", default=aibank.AI_DIR)
    parser.add_argument("--no-pdf", action="store_true")
    opts = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not opts.lecture:
        print("강의 폴더를 --lecture 나 AI_LECTURE_DIR 로 알려 주세요.", file=out)
        return 2
    lecture_dir = os.path.abspath(os.path.expanduser(opts.lecture))
    if not os.path.isdir(lecture_dir):
        print("강의 폴더가 없습니다: %s" % lecture_dir, file=out)
        return 2
    if not opts.no_pdf:
        try:
            import pypdf  # noqa: F401
        except ImportError:
            print("PDF 를 읽을 pypdf 가 없습니다. 출제자 컴퓨터의 /opt/homebrew/bin/python3 로 돌리거나 --no-pdf 로 PDF 를 건너뛰세요.", file=out)
            return 1
    numbers = sorted({int(t[1:]) for t in opts.targets if re.match(r"[il]\d{2}\Z", t)})
    if any(PATTERN_TARGET.match(t) for t in opts.targets):
        numbers = []  # 상황별 코드는 여러 차시 코드를 모으므로 모든 차시 폴더와 견줌
    lecture = corpus(lecture_dir, numbers, not opts.no_pdf)
    ours = targets(os.path.abspath(opts.bank), opts.targets)
    found = overlaps(ours, lecture)
    for where, head, why in found["fail"]:
        print("실패 %s: %s (%s…)" % (where, why, head), file=out)
    if found["near"]:
        print("근접 구간(%d~%d자) 검토:" % (NEAR_MIN, PROSE_MIN - 1), file=out)
        for where, head in found["near"]:
            print("  %s: %s…" % (where, head), file=out)
    note = " · PDF 안 봄" if lecture["skipped_pdf"] else ""
    print("대상 %d곳, 실패 %d곳%s" % (len(ours), len(found["fail"]), note), file=out)
    return 1 if found["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
