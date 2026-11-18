"""기존 화면 검사 모듈을 두 프로세스에 나누고 모든 결과를 합침."""
import argparse
from collections import Counter
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def case_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from case_ids(item)
        else:
            yield item.id()


def groups():
    modules = ["tests." + path.stem for path in sorted((ROOT / "tests").glob("test_gui*.py"))]
    counted = [(name, unittest.defaultTestLoader.loadTestsFromName(name).countTestCases()) for name in modules]
    discovered = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_gui*.py", top_level_dir=str(ROOT))
    planned = unittest.defaultTestLoader.loadTestsFromNames(modules)
    if Counter(case_ids(discovered)) != Counter(case_ids(planned)):
        raise RuntimeError("화면 검사 목록에 누락이나 중복이 있습니다.")
    batches, sizes = [[], []], [0, 0]
    for name, count in sorted(counted, key=lambda item: (-item[1], item[0])):
        target = min(range(2), key=lambda index: sizes[index])
        batches[target].append(name)
        sizes[target] += count
    return [sorted(batch) for batch in batches], sizes


def worker(modules):
    faulthandler.dump_traceback_later(480, repeat=True)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        faulthandler.cancel_dump_traceback_later()


def scaled_environment(scale, directory):
    """화면 배율 scale 로 검사를 돌릴 환경 변수. 화면 없는 플랫폼의 기본 화면은 800×800 화소라 배율만 주면 논리 크기가 줄어 창이 요구한 크기를
    받지 못함. 가상 화면을 800 × 배율로 키우는 설정 파일을 directory 에 쓰고 그 경로를 같이 넘김."""
    side = round(800 * scale)
    config = Path(directory) / "screen.json"
    config.write_text(json.dumps({"screens": [{"name": "scaled", "x": 0, "y": 0, "width": side, "height": side,
                                               "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]}), encoding="utf-8")
    return dict(os.environ, QT_QPA_PLATFORM=f"offscreen:configfile={config}", QT_SCALE_FACTOR=f"{scale:g}")


def run(batches, timeout_seconds=17 * 60, scale=1):
    jobs = []
    with tempfile.TemporaryDirectory(prefix="study-gui-check-") as directory:
        environment = scaled_environment(scale, directory) if scale != 1 else None
        try:
            for index, batch in enumerate(batches):
                path = Path(directory) / f"{index}.log"
                with path.open("w", encoding="utf-8") as stream:
                    process = subprocess.Popen([sys.executable, __file__, "--worker", *batch],
                                               cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=environment)
                jobs.append((process, path))
            success = True
            deadline = time.monotonic() + timeout_seconds
            for index, (process, path) in enumerate(jobs):
                try:
                    code = process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    code = 1
                    print(f"화면 검사 {index + 1}/{len(jobs)} · 시간 초과", flush=True)
                print(f"화면 검사 {index + 1}/{len(jobs)} · 종료 코드 {code}", flush=True)
                sys.stdout.write(path.read_text(encoding="utf-8", errors="replace"))
                success = success and code == 0
            return 0 if success else 1
        finally:
            for process, _ in jobs:
                if process.poll() is None:
                    process.terminate()
            for process, _ in jobs:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--worker", nargs="+")
    parser.add_argument("--scale", type=float, default=1, help="화면 배율. 1.5 를 주면 QT_SCALE_FACTOR=1.5 와 1200×1200 가상 화면으로 돌림")
    args = parser.parse_args()
    if args.scale < 1:
        parser.error("--scale 은 1 이상이어야 합니다.")
    if args.worker:
        return worker(args.worker)
    batches, sizes = groups()
    print(json.dumps({"groups": batches, "tests": sizes}, ensure_ascii=False), flush=True)
    return 0 if args.plan else run(batches, scale=args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
