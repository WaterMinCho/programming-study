"""기존 화면 검사 모듈을 세 프로세스에 나누고 모든 결과를 합침."""
import argparse
from collections import Counter
import faulthandler
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROCESSES = 3  # 둘로 나누면 느린 모듈이 한 묶음에 몰려 시간 제한에 닿은 적이 있음. GitHub 러너의 CPU 는 4개임
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
    batches, sizes = [[] for _ in range(PROCESSES)], [0] * PROCESSES
    for name, count in sorted(counted, key=lambda item: (-item[1], item[0])):
        target = min(range(PROCESSES), key=lambda index: sizes[index])
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


def run(batches, timeout_seconds=17 * 60):
    jobs = []
    with tempfile.TemporaryDirectory(prefix="study-gui-check-") as directory:
        try:
            for index, batch in enumerate(batches):
                path = Path(directory) / f"{index}.log"
                with path.open("w", encoding="utf-8") as stream:
                    process = subprocess.Popen([sys.executable, __file__, "--worker", *batch],
                                               cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
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
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    batches, sizes = groups()
    print(json.dumps({"groups": batches, "tests": sizes}, ensure_ascii=False), flush=True)
    return 0 if args.plan else run(batches)


if __name__ == "__main__":
    raise SystemExit(main())
