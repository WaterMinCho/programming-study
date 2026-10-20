#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""알고리즘 여행 비밀 파일을 던전마다 sealed.json 하나로 묶고 푸는 출제자용 도구. 명령은 USAGE 에 있음.

tools/seal.py 와 같은 꼴임. 비밀 파일 목록은 journey.bank 의 것(SECRET_FILES, wrong/ 아래 .py·.js, 던전 폴더의
review.json)을 씀. 봉인은 base64 와 zlib 로 감쌌을 뿐이라 우연히 답을 보지 않게 가리는 장치이고, 파일 내용을 바꾸지
않으므로 봉인 앞뒤로 review.json 의 해시가 그대로 맞음.
"""
import argparse
import json
import os
import shutil
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from journey import bank, values  # noqa: E402

NOTE = "알고리즘 여행의 기준 풀이·테스트·힌트·해설 묶음입니다(스포일러 방지용). 출제자는 tools/journey_seal.py unseal 로 풉니다."
BRIEF_KEYS = ("title", "signature", "time_limit_ms", "examples")
USAGE = """알고리즘 여행 봉인 도구 (출제자용)

기준 풀이·테스트·힌트·해설 같은 비밀 파일은 평문으로 커밋하지 않고 던전마다 sealed.json 하나로 묶어 커밋합니다.
암호화는 아니고, 실수로 답을 미리 보지 않게 가려 두는 용도입니다.

  python tools/journey_seal.py seal [던전...] [--keep]     평문 → sealed.json (평문 삭제, --keep 이면 평문 유지)
  python tools/journey_seal.py unseal [던전...]            sealed.json → 평문 (고칠 때)
  python tools/journey_seal.py check                       봉인 안 된 평문이 있거나 sealed.json 이 깨졌으면 실패
  python tools/journey_seal.py brief d01/p3 --out DIR      다시 풀 사람에게 줄 공개본을 저장소 밖 DIR 에 만듦

--bank DIR 로 은행 폴더를 바꿀 수 있습니다(기본 dungeons/).
"""


def dungeon_names(bank_dir):
    try:
        names = os.listdir(bank_dir)
    except OSError:
        return []
    return sorted(name for name in names if os.path.isdir(os.path.join(bank_dir, name)))


def targets(bank_dir, tokens):
    known = dungeon_names(bank_dir)
    for token in tokens:
        if token not in known:
            raise SystemExit("던전 폴더가 없습니다: %s (은행 %s)" % (token, bank_dir))
    return tokens or known


def remove_plain(ddir):
    for rel in bank.plain_secret_paths(ddir):
        os.remove(os.path.join(ddir, *rel.split("/")))
    for pid in bank.problem_ids(ddir):
        wrong = os.path.join(ddir, pid, bank.WRONG_DIR)
        if os.path.isdir(wrong) and not os.listdir(wrong):
            os.rmdir(wrong)


def secrets_of(ddir, did):
    """bank.load_secrets 와 같음. sealed.json 이 풀리지 않으면 이유를 적고 멈춤."""
    try:
        return bank.load_secrets(ddir)
    except bank.BankError as error:
        raise SystemExit("%s: %s\nsealed.json 을 git 에서 되돌리거나, 평문 작업본만으로 다시 묶으려면 sealed.json 을 지운 뒤 "
                         "seal 하세요." % (did, error))


def seal(bank_dir, did, keep=False):
    """평문과 기존 봉인을 합쳐(평문이 이김) sealed.json 을 씀. 폴더가 사라진 문제의 항목은 버리고, 남은 것이 없으면
    sealed.json 을 지움."""
    ddir = os.path.join(bank_dir, did)
    files = secrets_of(ddir, did)
    pids = set(bank.problem_ids(ddir))
    files = {rel: text for rel, text in files.items() if "/" not in rel or rel.split("/")[0] in pids}
    if not files:
        sealed = os.path.join(ddir, bank.SEALED_NAME)
        if os.path.isfile(sealed):
            os.remove(sealed)
            print("봉인할 비밀 파일이 없어 sealed.json 을 지웠습니다: %s" % did)
        else:
            print("봉인할 비밀 파일이 없습니다: %s" % did)
        return
    blob = study.seal_blob(files)
    study.write_text(os.path.join(ddir, bank.SEALED_NAME),
                     json.dumps({"note": NOTE, "blob": blob}, ensure_ascii=False, indent=1) + "\n")
    if not keep:
        remove_plain(ddir)
    print("봉인: %s (파일 %d개%s)" % (did, len(files), ", 평문 유지" if keep else ""))


def unseal(bank_dir, did):
    ddir = os.path.join(bank_dir, did)
    files = secrets_of(ddir, did)
    written = 0
    for rel, text in sorted(files.items()):
        parts = rel.split("/")
        if len(parts) > 1 and not os.path.isdir(os.path.join(ddir, parts[0])):
            continue
        study.write_text(os.path.join(ddir, *parts), text)
        written += 1
    print("봉인 해제: %s (파일 %d개). 고친 뒤 verify_journey.py 로 확인하고 seal 로 다시 묶으세요." % (did, written))


def sealed_problem(ddir):
    """sealed.json 이 풀리지 않으면 그 이유, 괜찮거나 없으면 None."""
    path = os.path.join(ddir, bank.SEALED_NAME)
    if not os.path.isfile(path):
        return None
    try:
        files = study.unseal_blob(study.read_json(path)["blob"])
    except (OSError, ValueError, KeyError, TypeError, zlib.error) as error:
        return str(error) or type(error).__name__
    if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
        return "묶음이 {경로: 글} 꼴이 아닙니다"
    return None


def check(bank_dir):
    dirty, broken = [], []
    for did in dungeon_names(bank_dir):
        ddir = os.path.join(bank_dir, did)
        dirty += ["%s/%s" % (did, rel) for rel in bank.plain_secret_paths(ddir)]
        why = sealed_problem(ddir)
        if why:
            broken.append("%s/%s: %s" % (did, bank.SEALED_NAME, why))
    shown = study.shown_path(bank_dir).replace(os.sep, "/")
    if dirty:
        print("봉인되지 않은 평문 비밀 파일이 있습니다. `python tools/journey_seal.py seal` 을 실행하세요:")
        for rel in dirty:
            print("  %s/%s" % (shown, rel))
    if broken:
        print("풀리지 않는 sealed.json 이 있습니다:")
        for line in broken:
            print("  %s/%s" % (shown, line))
    if dirty or broken:
        return 1
    print("OK: 여정 문제 은행에 봉인되지 않은 비밀 파일이 없습니다.")
    return 0


def inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def brief(bank_dir, target, out_dir):
    """다시 풀 사람에게 줄 공개본. problem.md, problem.json 의 일부, 두 언어 시작 코드(alt.py, alt.js)만 넣음."""
    parts = [part for part in target.replace("\\", "/").split("/") if part]
    if len(parts) != 2:
        raise SystemExit("brief 에는 문제 하나를 d01/p3 처럼 적어 주세요.")
    pdir = os.path.join(bank_dir, *parts)
    if not os.path.isfile(os.path.join(pdir, "problem.json")) or not os.path.isfile(os.path.join(pdir, "problem.md")):
        raise SystemExit("문제의 problem.json 과 problem.md 가 없습니다: %s" % target)
    for folder in (ROOT, bank_dir):
        if inside(out_dir, folder):
            raise SystemExit("공개본은 저장소 밖에 만들어 주세요. 저장소 안에 두면 커밋에 섞일 수 있습니다: %s" % out_dir)
    data = study.read_json(os.path.join(pdir, "problem.json"))
    public = {key: data[key] for key in BRIEF_KEYS if key in data}
    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(os.path.join(pdir, "problem.md"), os.path.join(out_dir, "problem.md"))
    study.write_text(os.path.join(out_dir, "problem.json"), json.dumps(public, ensure_ascii=False, indent=1) + "\n")
    for lang in values.LANGS:
        name = "alt" + (".py" if lang == "python" else ".js")
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            study.write_text(path, values.starter(public["signature"], lang))
    print("공개본을 만들었습니다: %s" % out_dir)
    print("다시 풀 사람은 problem.md 만 보고 alt.py, alt.js 를 채웁니다. 다 풀면 출제자가 아닌 사람이 "
          "`python tools/verify_journey.py %s --alt %s` 로 기준 풀이와 대조합니다." % ("/".join(parts), out_dir))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("seal", "unseal", "check", "brief"):
        print(USAGE)
        return 2
    parser = argparse.ArgumentParser(prog="journey_seal.py %s" % argv[0])
    parser.add_argument("targets", nargs="*")
    parser.add_argument("--bank", default=bank.BANK_DIR)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--out")
    opts = parser.parse_args(argv[1:])
    bank_dir = os.path.abspath(opts.bank)
    command = argv[0]
    if command == "check":
        return check(bank_dir)
    if command == "brief":
        if len(opts.targets) != 1 or not opts.out:
            raise SystemExit("쓰는 법: python tools/journey_seal.py brief d01/p3 --out DIR")
        brief(bank_dir, opts.targets[0], os.path.abspath(opts.out))
        return 0
    for did in targets(bank_dir, opts.targets):
        if command == "seal":
            seal(bank_dir, did, opts.keep)
        elif os.path.isfile(os.path.join(bank_dir, did, bank.SEALED_NAME)):
            unseal(bank_dir, did)
    return 0


if __name__ == "__main__":
    sys.exit(main())
