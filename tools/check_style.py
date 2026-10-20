#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""문서·주석·화면 문구·커밋 메시지의 말투 검사. 하나라도 걸리면 1 로 끝남.

기록(커밋 본문, 주석, 독스트링, yml 주석)은 ~함/~음/~했음/~임 체로, 가이드(README, docs, 지문·힌트·해설, 화면 문구)는
~니다/~세요 체로 씀. 그 밖에 em-dash, 예고형 도입, 개수를 세어 닫는 문장, 은유, 담화표지, 속 빈 수식, 강조 부사,
긴 설명 뒤에 붙는 짧은 정리문, 불릿마다 같은 '**라벨** 설명' 꼴, 커밋 제목 형식을 봄. 규칙 하나하나는 FIXED 와 check() 에 있음.

  python tools/check_style.py README.md gui/hub_page.py      파일을 바로 검사
  python tools/check_style.py --commit <파일>                 커밋 메시지, 또는 PR 제목과 본문
  python tools/check_style.py --changed origin/main           main 과 갈라진 뒤 바뀐 파일 가운데 검사할 것만
  python tools/check_style.py --staged                        스테이지에 올린 파일 가운데 검사할 것만(pre-commit 훅)
  python tools/check_style.py --install-hooks                 tools/hooks 의 훅을 .git/hooks 에 복사

검사할 파일: *.md(submissions/ 아래 제외), 저장소 맨 위와 gui/·journey/·tools/ 아래의 .py, .github/workflows/*.yml,
dungeons/<던전>/sealed.json 안의 hints.md·explain.md. tests/test_style.py 는 일부러 틀린 문장을 담은 테스트라 뺌.
이 파일도 뺌. raw 문자열도 화면 문구처럼 글로 보는데, 패턴 표의 낱말이 거기에 걸림.
"""
import filecmp
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tokenize
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_NAMES = ("pre-commit", "commit-msg")
SEALED_NOTES = ("hints.md", "explain.md")
CODE_SUFFIXES = (".py", ".yml", ".yaml", ".bat", ".command", ".sh")

# 글 어디에 있어도 걸리는 꼴
FIXED = {
    "em-dash(\u2014)": "\u2014",
    "예고형 도입": r"알아보겠습니다|살펴보겠습니다|알아볼까요|소개합니다\.$",
    "기계 순서": r"^(먼저|다음으로는?|마지막으로)[ ,]|첫째,|둘째,|셋째,",
    "단정 요약(개수 세기)": r"하나입니다|둘입니다|둘뿐입니다|두 가지입니다|세 가지입니다|두 가지뿐|딱 하나|하나면 됩니다|하나뿐입니다",
    "은유": r"갈림길|열쇠|관문|첫걸음|핵심이에요|핵심입니다|지름길|경계선|한눈에",
    "담화표지": r"^(정리하면|즉 |요컨대|결국 )|여기[가서] [^\n]{0,25}(인데요|많은데요)",
    "해석 덧붙이기": r"(뜻이에요|뜻입니다|얘기입니다|이야기입니다|셈입니다|말입니다)\.",
    "빈 예고문": r"(내용은 이렇습니다|다음과 같습니다|짚고 갑니다|함정이 있습니다)\.",
    "추상 서술어": r"그대로(입니다|예요)\.|사정이 다릅니다|(은|는) 다릅니다\.|기준입니다\.$",
    "속 빈 수식": r"중요합니다|효과적입니다|도움이 됩니다|다양한|여러 가지|손쉽게|간편하게|강력한|완벽",
    "정형 마무리": r"도움이 되셨|바랍니다\.$|화이팅|파이팅",
    "강조 부사": r"(^|[\s(])(정말|아주|매우|굉장히|의외로|생각보다|무려)\s",
    "이모지": r"[\U0001F300-\U0001FAFF☀-➿⭐✅]",
    "느낌표": r"[가-힣a-zA-Z)]!(\s|$)",
}
END = r"(니다|세요|어요|아요|해요|돼요)\.$"
POINTER = r"(^|\s)(그|이|그게|이게|바로 그)\s?\S{0,10}" + END  # 앞 문장을 가리키며 닫는 짧은 문장
# 불릿마다 '**라벨** 설명' 같은 꼴. 라벨 뒤 구분 글자는 em-dash, 쌍점, en-dash, 붙임표. 줄표는 이 파일에 글자로 두지 않고 \u 로 적음
SCAFFOLD = "^\\s*[-*] \\*\\*[^*\\n]{1,20}\\*\\* ?[\u2014:\u2013-] "
RECORD_BAD = r"[가-힣](니다|다|요|죠)[.!]?\s*$"  # 기록(커밋 본문·주석·독스트링)이 평서형·존댓말로 끝남
GUIDE_BAD = r"[가-힣](함|음|임|됨|했음|없음|있음|않음)\.\s*$"  # 가이드(문서·안내)가 ~함/~음 으로 끝남
# 커밋 메시지(PR 제목·본문)에 두지 않는 줄. 도구와 상관없이 줄 꼴만 봄
TRAILERS = {
    "커밋에 넣지 않는 줄(Co-Authored-By:)": r"^\s*co-authored-by:",
    "커밋에 넣지 않는 줄(Generated with)": r"generated with",
}


def record_fails(lines):
    out = []
    for line in lines:
        for sent in re.split(r"(?<=[.])\s+", line.strip()):
            if len(sent) >= 6 and " " in sent and re.search(RECORD_BAD, sent):
                out.append(("기록 문장은 ~함/~음/~했음/~임 체", sent[-30:]))
    return out


def code_text(path, text):
    """코드 파일에서 사람이 읽는 글을 (기록, 가이드)로 나눠 뽑음.
    기록 = 주석과 독스트링. 가이드 = 화면·터미널에 보이는 한글 문자열."""
    hangul = re.compile("[가-힣]")
    records, guides = [], []
    if path.endswith(".py"):
        prev = None  # 직전의 의미 있는 토큰 종류
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.COMMENT:
                    records.append(tok.string.lstrip("# "))
                    continue
                if tok.type in (tokenize.NL,):
                    continue
                if tok.type == tokenize.STRING and hangul.search(tok.string):
                    body = re.sub(r'^[rbuRBUfF]*("""|\'\'\'|"|\')|("""|\'\'\'|"|\')$', "", tok.string)
                    lines = [line.strip() for line in body.replace("\\n", "\n").split("\n")]
                    docstring = prev in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT) and tok.string.lstrip("rbuRBU").startswith(('"""', "\'\'\'"))
                    (records if docstring else guides).extend(lines)
                prev = tok.type
        except (tokenize.TokenError, IndentationError):
            return [ln for ln in text.split("\n") if hangul.search(ln)], []
        return records, guides
    for line in text.split("\n"):
        if not hangul.search(line):
            continue
        m = re.match(r"^\s*(#|::|REM |rem )\s?(.*)$", line)
        if m:
            records.append(m.group(2))
        else:
            guides.append(re.sub(r"^\s*(echo|-?\s*run:|name:|description:|label:|title:|placeholder:)\s?", "", line.split(" # ")[0]))
            if " # " in line:
                records.append(line.split(" # ", 1)[1])
    return records, guides


def prose_lines(text, commit=False):
    """코드 블록·표·그림·주석 줄을 뺀 글 줄."""
    out, fence = [], False
    for line in text.replace("\r\n", "\n").split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
            continue
        if fence or re.match(r"^\s*\|", line) or re.match(r"^\s*(!\[|<!--|#!)", line):
            continue
        if commit and (line.startswith("#") or re.match(r"^(Co-Authored-By|Signed-off-by):", line)):
            continue
        line = re.sub(r"`[^`\n]*`", "", line)  # 인라인 코드 안은 보지 않음
        out.append(line)
    return out


def check(text, commit=False, path=""):
    fails = []
    code = path.endswith(CODE_SUFFIXES)
    records = []
    if code:
        records, guides = code_text(path, text)
        lines = records + guides
    else:
        lines = prose_lines(text, commit)
    body = "\n".join(lines)
    for name, pattern in FIXED.items():
        if commit and name in ("em-dash(\u2014)",):  # 커밋 제목의 em-dash 는 예전 커밋에도 있어 보지 않음
            continue
        if code and name in ("이모지", "느낌표"):  # 채점 표시와 시험용 출력 문자열
            continue
        for m in re.finditer(pattern, body, re.M):
            fails.append((name, body[max(0, m.start() - 22):m.end() + 6].replace("\n", " ").strip()))
    # 긴 설명 뒤 짧은 정리문, 앞 내용을 가리키며 닫는 단문
    for para in re.split(r"\n\s*\n", body):
        flat = re.sub(r"^\s*([-*]|\d+\.)\s+", "", para.replace("\n", " ").strip())
        sents = [s.strip() for s in re.split(r"(?<=[.?])\s+", flat) if s.strip()]
        for k, s in enumerate(sents):
            if len(s) <= 25 and re.search(POINTER, s):
                fails.append(("앞 내용을 가리키며 닫는 단문", s))
            elif k == len(sents) - 1 and len(sents) > 1 and len(s) <= 14 and re.search(END, s) and len(sents[k - 1]) >= 35:
                fails.append(("긴 설명 뒤 짧은 정리문", sents[k - 1][-18:] + " " + s))
    # 불릿이 전부 같은 '**라벨** 설명' 꼴로 3개 이상 이어짐
    run = 0
    for line in lines:
        run = run + 1 if re.match(SCAFFOLD, line) else 0
        if run == 3:
            fails.append(("불릿마다 같은 '**라벨** 설명' 꼴", line.strip()[:40]))
    fails += record_fails(records)
    if not code and not commit:  # 문서(가이드)는 ~니다 체
        for line in lines:
            if re.search(GUIDE_BAD, line.strip()):
                fails.append(("가이드 문장은 ~니다 체", line.strip()[-30:]))
    if commit:
        raw = [ln for ln in text.replace("\r\n", "\n").split("\n") if not ln.startswith("#")]  # git 이 지우는 # 줄은 빼고 봄
        for name, pattern in TRAILERS.items():
            for ln in raw:
                if re.search(pattern, ln, re.I):
                    fails.append((name, ln.strip()[:40]))
        subject = next((ln for ln in lines if ln.strip()), "")
        if not re.match(r"^(feat|fix|docs|refactor|test|chore|style|perf|build|ci)(\([\w/.-]+\))?: \S", subject) \
                and not subject.startswith(("Merge ", "Revert ")):
            fails.append(("커밋 제목 형식(type(scope): 내용)", subject[:50]))
        body_lines = [ln for ln in lines if ln.strip()][1:]
        fails += record_fails(body_lines)
        if len([ln for ln in lines if re.match(r"^\s*[-*] ", ln)]) > 4:
            fails.append(("커밋 본문에 불릿 5개 이상(요약 나열 대신 한두 문장으로)", ""))
    return fails


def select(paths):
    """바뀐 파일 가운데 검사할 것만 고름. 경로는 저장소 맨 위 기준."""
    picked = []
    for p in paths:
        p = p.replace("\\", "/")
        if p.startswith("submissions/") or p in ("tests/test_style.py", "tools/check_style.py"):
            continue
        top = p.split("/")[0]
        if p.endswith(".md"):
            picked.append(p)
        elif p.endswith(".py") and ("/" not in p or top in ("gui", "journey", "tools")):
            picked.append(p)
        elif p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")):
            picked.append(p)
        elif re.match(r"dungeons/[^/]+/sealed\.json$", p):
            picked.append(p)
    return picked


def changed_paths(ref=None, staged=False, root=None):
    """git 이 보는 바뀐 파일(지운 파일 제외). ref 가 있으면 merge-base 이후, staged 면 스테이지에 올린 것."""
    cmd = ["git", "-c", "core.quotepath=false", "diff", "--name-only", "--diff-filter=d"]
    cmd.append("--cached" if staged else "%s...HEAD" % ref)
    done = subprocess.run(cmd, cwd=root or ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise SystemExit(done.stderr.strip() or "git diff 가 실패했습니다.")
    return [ln for ln in done.stdout.splitlines() if ln.strip()]


def index_text(rel, root=None):
    """스테이지에 올린 내용. git add -p 로 일부만 올렸을 때 작업 폴더가 아니라 커밋될 글을 봄."""
    done = subprocess.run(["git", "cat-file", "blob", ":" + rel], cwd=root or ROOT, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if done.returncode != 0:
        raise SystemExit(done.stderr.decode("utf-8", "replace").strip() or "스테이지에서 %s 을 읽지 못했습니다." % rel)
    return done.stdout.decode("utf-8")


def sealed_texts(path, text=None):
    """던전 sealed.json 안의 hints.md·explain.md 를 [(상대경로, 글)] 로 꺼냄. 못 풀면 그 사실을 실패로 돌려줌.
    text 가 있으면 파일 대신 그 글을 풂(스테이지에 올린 내용)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import study
    try:
        if text is None:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        files = study.unseal_blob(json.loads(text)["blob"])
        pairs = [(rel, note) for rel, note in sorted(files.items()) if rel.endswith(SEALED_NOTES)]
    except (ValueError, KeyError, TypeError, zlib.error) as e:
        return [], [("sealed.json 을 풀 수 없음", str(e)[:60])]
    return pairs, []


def check_path(path, commit=False, shown=None, text=None):
    """파일 하나를 검사해 [(보여 줄 이름, 걸린 것들)] 로 돌려줌. sealed.json 은 안의 글마다 한 항목.
    text 가 있으면 파일을 읽지 않고 그 글을 검사함."""
    shown = shown or path
    if os.path.basename(path) == "sealed.json":
        pairs, broken = sealed_texts(path, text)
        return [(shown, broken)] if broken else [("%s:%s" % (shown, rel), check(note, path=rel)) for rel, note in pairs]
    if text is None:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    return [(shown, check(text, commit, path))]


def install_hooks(root=None):
    """tools/hooks 의 훅을 이 저장소의 훅 폴더에 복사함. 같은 이름의 다른 훅이 있으면 두고 1 로 끝남."""
    root = root or ROOT
    done = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=root, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        print(done.stderr.strip() or "git 저장소가 아닙니다.")
        return 2
    hooks_dir = done.stdout.strip()
    if not os.path.isabs(hooks_dir):
        hooks_dir = os.path.join(root, hooks_dir)
    os.makedirs(hooks_dir, exist_ok=True)
    kept = 0
    for name in HOOK_NAMES:
        src = os.path.join(root, "tools", "hooks", name)
        dst = os.path.join(hooks_dir, name)
        if os.path.exists(dst) and not filecmp.cmp(src, dst, shallow=False):
            print("이미 있는 훅을 그대로 두었습니다: %s. 그 훅에서 tools/hooks/%s 을 부르게 고쳐 주세요." % (dst, name))
            kept += 1
            continue
        shutil.copyfile(src, dst)
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("훅을 설치했습니다: %s" % dst)
    return 1 if kept else 0


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    if "--install-hooks" in args:
        return install_hooks()
    commit = "--commit" in args
    staged = "--staged" in args
    ref = None
    if "--changed" in args:
        at = args.index("--changed")
        if at + 1 >= len(args) or args[at + 1].startswith("--"):
            print("--changed 뒤에 비교할 ref 를 적어 주세요. 예: --changed origin/main")
            return 2
        ref = args.pop(at + 1)
    targets = [(p, p, None) for p in args if not p.startswith("--")]
    if ref is not None or staged:
        for p in select(changed_paths(ref, staged)):
            targets.append((p, os.path.join(ROOT, p), index_text(p) if staged else None))
    if not targets:
        print("검사할 파일이 없습니다.")
        return 0
    bad = 0
    for shown, path, text in targets:
        for name, fails in check_path(path, commit, shown, text):
            for rule, where in fails:
                print("  X %s: %s  [%s]" % (rule, where, name))
            bad += len(fails)
            if not fails:
                print("  통과  [%s]" % name)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
