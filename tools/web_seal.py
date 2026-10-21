#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""웹 면접 준비의 비밀 파일(미션의 work/, 주제의 work/)을 sealed.json 하나로 묶고 푸는 출제자용 도구. 명령은 USAGE 에 있음.

tools/journey_seal.py 와 같은 꼴임. 비밀 파일 목록과 봉인 풀기는 webprep.bank 의 것(plain_secret_paths, load_secrets,
seal_text)을 써서 서비스와 같은 파일을 봄. 학습 페이지(learn/)는 읽을거리라 봉인하지 않음. 봉인은 base64 와 zlib 로 감쌌을
뿐이라 우연히 답을 보지 않게 가리는 장치이고, 파일 내용을 바꾸지 않으므로 봉인 앞뒤로 review.json 의 해시가 그대로 맞음.
"""
import argparse
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import study  # noqa: E402
from webprep import bank  # noqa: E402

NOTE = "웹 면접 준비의 단계 요구·검사·모범 답안·해설·꼬리 질문·사슬 묶음입니다(스포일러 방지용). 출제자는 tools/web_seal.py unseal 로 풉니다."
SEALED_KINDS = ("mission", "topic")
BRIEF_KEYS = ("format", "id", "title", "level", "prep_min", "live_min", "steps", "hidden", "pages", "needs")
SKIP_DIRS = ("node_modules", "dist", ".git")
USAGE = """웹 면접 준비 봉인 도구 (출제자용)

미션의 단계 요구·검사·모범 답안·해설·꼬리 질문과 주제의 사슬 본문은 평문으로 커밋하지 않고 폴더마다 sealed.json 하나로 묶어
커밋합니다. 암호화는 아니고, 실수로 답을 미리 보지 않게 가려 두는 용도입니다. 학습 페이지는 봉인하지 않습니다.

  python tools/web_seal.py seal [w03 t03 ...] [--keep]    work/ → sealed.json (평문 삭제, --keep 이면 평문 유지)
  python tools/web_seal.py unseal [w03 t03 ...]           sealed.json → work/ (고칠 때)
  python tools/web_seal.py check                          봉인 안 된 평문이 있거나 sealed.json 이 깨졌으면 실패
  python tools/web_seal.py brief w03 --out DIR            다시 풀 사람에게 줄 공개본을 저장소 밖 DIR 에 만듦

--bank DIR 로 은행 폴더를 바꿀 수 있습니다(기본 web/).
"""


def item_dirs(bank_dir):
    """봉인 대상 폴더를 [(id, 종류, 경로)] 로. missions/ 와 drills/ 아래 폴더 전부(출제 전 폴더도 평문이 있으면 봄)."""
    out = []
    for kind in SEALED_KINDS:
        parent = os.path.join(bank_dir, bank.FOLDERS[kind])
        try:
            names = sorted(os.listdir(parent))
        except OSError:
            continue
        for name in names:
            path = os.path.join(parent, name)
            if os.path.isdir(path) and not name.startswith("."):
                out.append((name, kind, path))
    return out


def targets(bank_dir, tokens):
    found = {iid: (kind, path) for iid, kind, path in item_dirs(bank_dir)}
    for token in tokens:
        if token not in found:
            raise SystemExit("미션이나 주제 폴더가 없습니다: %s (은행 %s)" % (token, bank_dir))
    picked = tokens or sorted(found)
    return [(iid,) + found[iid] for iid in picked]


def secrets_of(idir, iid):
    """bank.load_secrets 와 같음. sealed.json 이 풀리지 않으면 이유를 적고 멈춤."""
    try:
        return bank.load_secrets(idir)
    except bank.BankError as error:
        raise SystemExit("%s: %s\nsealed.json 을 git 에서 되돌리거나, 평문 작업본만으로 다시 묶으려면 sealed.json 을 지운 뒤 "
                         "seal 하세요." % (iid, error))


def remove_plain(idir):
    wdir = os.path.join(idir, bank.WORK_DIR)
    if os.path.isdir(wdir):
        shutil.rmtree(wdir)


def seal(bank_dir, iid, keep=False):
    """평문과 기존 봉인을 합쳐(평문이 이김) sealed.json 을 씀. 남은 것이 없으면 sealed.json 을 지움."""
    idir = os.path.join(bank_dir, bank.FOLDERS[kind_of(bank_dir, iid)], iid)
    files = secrets_of(idir, iid)
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
        remove_plain(idir)
    print("봉인: %s (파일 %d개%s)" % (iid, len(files), ", 평문 유지" if keep else ""))


def unseal(bank_dir, iid):
    idir = os.path.join(bank_dir, bank.FOLDERS[kind_of(bank_dir, iid)], iid)
    files = secrets_of(idir, iid)
    for rel, text in sorted(files.items()):
        study.write_text(os.path.join(idir, bank.WORK_DIR, *rel.split("/")), text)
    print("봉인 해제: %s (파일 %d개). 고친 뒤 verify_web.py 와 web_lint.py 로 확인하고 seal 로 다시 묶으세요." % (iid, len(files)))


def kind_of(bank_dir, iid):
    for name, kind, _ in item_dirs(bank_dir):
        if name == iid:
            return kind
    raise SystemExit("미션이나 주제 폴더가 없습니다: %s" % iid)


def sealed_problem(idir):
    """sealed.json 이 풀리지 않으면 그 이유, 괜찮거나 없으면 None."""
    if not os.path.isfile(os.path.join(idir, bank.SEALED_NAME)):
        return None
    wdir = os.path.join(idir, bank.WORK_DIR)
    try:
        if os.path.isdir(wdir):  # 평문이 있으면 load_secrets 가 평문을 덮으므로 봉인만 따로 풂
            blob = study.unseal_blob(study.read_json(os.path.join(idir, bank.SEALED_NAME))["blob"])
            if not isinstance(blob, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in blob.items()):
                return "묶음이 {경로: 글} 꼴이 아닙니다"
        else:
            bank.load_secrets(idir)
    except bank.BankError as error:
        return str(error)
    except Exception as error:  # noqa: BLE001 - 깨진 파일은 어떤 예외든 이유만 보여 줌
        return str(error) or type(error).__name__
    return None


def check(bank_dir):
    dirty, broken = [], []
    for iid, kind, idir in item_dirs(bank_dir):
        rel = "%s/%s" % (bank.FOLDERS[kind], iid)
        dirty += ["%s/%s/%s" % (rel, bank.WORK_DIR, name) for name in bank.plain_secret_paths(idir)]
        why = sealed_problem(idir)
        if why:
            broken.append("%s/%s: %s" % (rel, bank.SEALED_NAME, why))
    shown = study.shown_path(bank_dir).replace(os.sep, "/")
    if dirty:
        print("봉인되지 않은 평문 작업본이 있습니다. `python tools/web_seal.py seal` 을 실행하세요:")
        for line in dirty:
            print("  %s/%s" % (shown, line))
    if broken:
        print("풀리지 않는 sealed.json 이 있습니다:")
        for line in broken:
            print("  %s/%s" % (shown, line))
    if dirty or broken:
        return 1
    print("OK: 웹 면접 준비 은행에 봉인되지 않은 평문 작업본이 없습니다.")
    return 0


def inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def brief(bank_dir, mid, out_dir):
    """다시 풀 사람에게 줄 공개본. brief.md, meta.json 의 공개 키, 템플릿 app/ 만 넣음. 단계 요구·검사·힌트·해설·모범 답안은
    넣지 않음."""
    mdir = os.path.join(bank_dir, bank.FOLDERS["mission"], mid)
    for name in ("meta.json", "brief.md"):
        if not os.path.isfile(os.path.join(mdir, name)):
            raise SystemExit("미션의 meta.json 과 brief.md 가 있어야 합니다: %s" % mid)
    if not os.path.isdir(os.path.join(mdir, bank.APP_DIR)):
        raise SystemExit("미션에 템플릿 폴더 app/ 이 없습니다: %s" % mid)
    for folder in (ROOT, bank_dir):
        if inside(out_dir, folder):
            raise SystemExit("공개본은 저장소 밖에 만들어 주세요. 저장소 안에 두면 커밋에 섞일 수 있습니다: %s" % out_dir)
    data = study.read_json(os.path.join(mdir, "meta.json"))
    public = {key: data[key] for key in BRIEF_KEYS if key in data}
    os.makedirs(out_dir, exist_ok=True)
    shutil.copyfile(os.path.join(mdir, "brief.md"), os.path.join(out_dir, "brief.md"))
    study.write_text(os.path.join(out_dir, "meta.json"), json.dumps(public, ensure_ascii=False, indent=1) + "\n")
    app_out = os.path.join(out_dir, bank.APP_DIR)
    if os.path.isdir(app_out):
        shutil.rmtree(app_out)
    shutil.copytree(os.path.join(mdir, bank.APP_DIR), app_out, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    print("공개본을 만들었습니다: %s" % out_dir)
    print("다시 풀 사람은 brief.md 를 읽고 app/ 을 자기 에디터에서 고칩니다. 단계 요구는 출제자가 실전 시간에 하나씩 건네고, "
          "끝나면 출제자가 아닌 사람이 `python tools/verify_web.py %s` 의 결과와 기록을 보고 목표 시간을 고칩니다." % mid)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("seal", "unseal", "check", "brief"):
        print(USAGE)
        return 2
    parser = argparse.ArgumentParser(prog="web_seal.py %s" % argv[0])
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
            raise SystemExit("쓰는 법: python tools/web_seal.py brief w03 --out DIR")
        brief(bank_dir, opts.targets[0], os.path.abspath(opts.out))
        return 0
    for iid, kind, idir in targets(bank_dir, opts.targets):
        if command == "seal":
            seal(bank_dir, iid, opts.keep)
        elif os.path.isfile(os.path.join(idir, bank.SEALED_NAME)):
            unseal(bank_dir, iid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
