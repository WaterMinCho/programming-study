"""기존 화면 검사 모듈을 두 프로세스에 나누고 모든 결과를 합침."""
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
# 느린 모듈이 걸리는 시간(초). 2026-11-18 에 잰 값이고 묶음을 나눌 때 비율로만 씀. 표에 없는 모듈은 테스트 하나를 REST 초로 셈.
# 테스트 수로만 나누면 느린 모듈이 한 묶음에 몰려 시간 제한에 닿음(958초와 551초였음). 세 프로세스로 나누면 GitHub 러너에서 묶음마다 느려져 전체 시간이 늘었음
SLOW = {"tests.test_gui_ai": 142, "tests.test_gui_section_browser": 141, "tests.test_gui": 137,
        "tests.test_gui_career_learning_path": 114, "tests.test_gui_web": 94, "tests.test_gui_ai_courses": 54,
        "tests.test_gui_global_consistency": 46, "tests.test_gui_settings_menu": 45, "tests.test_gui_hub": 33,
        "tests.test_gui_design_system": 30, "tests.test_gui_refresh": 30, "tests.test_gui_career_integration": 28,
        "tests.test_gui_journey": 27, "tests.test_gui_ai_mixed_mock": 23, "tests.test_gui_career": 23,
        "tests.test_gui_ai_mock": 21}
REST = 0.7
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
    batches, sizes, loads = [[], []], [0, 0], [0.0, 0.0]
    for name, count in sorted(counted, key=lambda item: (-SLOW.get(item[0], item[1] * REST), item[0])):
        target = min(range(2), key=lambda index: loads[index])
        batches[target].append(name)
        sizes[target] += count
        loads[target] += SLOW.get(name, count * REST)
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
