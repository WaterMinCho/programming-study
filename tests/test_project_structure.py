# -*- coding: utf-8 -*-
"""기존 import의 호환성과 서버 배포 파일의 의존성을 확인함."""
import importlib
import io
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class SharedDataStructureTest(unittest.TestCase):
    def test_legacy_paths_share_the_same_module_and_patch_targets(self):
        pairs = {"aiprep.collection": "learning_data.collection", "aiprep.privacy": "learning_data.privacy",
                 "aiprep.sharing": "learning_data.sharing", "aiprep.goals": "learning_data.goals",
                 "aiprep.sync_schedule": "learning_data.sync_schedule", "python_collection": "learning_data.python",
                 "submission_api": "learning_data.submission"}
        for old, new in pairs.items():
            with self.subTest(path=old):
                self.assertIs(importlib.import_module(old), importlib.import_module(new))
        privacy = importlib.import_module("learning_data.privacy")
        with mock.patch("aiprep.privacy.save", return_value="saved"):
            self.assertEqual("saved", privacy.save("unused", {}))

    def test_runtime_revision_hashes_implementation_instead_of_import_adapter(self):
        from learning_data import collection
        actual_open = open
        target = ROOT / "learning_data/collection.py"
        raw = target.read_bytes()
        for track in ("ai", "python"):
            with self.subTest(track=track):
                collection.runtime_revision.cache_clear()
                self.addCleanup(collection.runtime_revision.cache_clear)
                before = collection.runtime_revision(track)
                opened = []

                def changed(path, *args, **kwargs):
                    opened.append(Path(path))
                    if Path(path) == target:
                        return io.BytesIO(raw + b"\n# implementation changed\n")
                    return actual_open(path, *args, **kwargs)

                collection.runtime_revision.cache_clear()
                with mock.patch("builtins.open", side_effect=changed):
                    after = collection.runtime_revision(track)
                self.assertNotEqual(before, after)
                self.assertIn(target, opened)
                self.assertNotIn(ROOT / "aiprep/collection.py", opened)
                self.assertNotIn(ROOT / "python_collection.py", opened)

    def test_docker_copy_files_handle_registration_without_app_packages(self):
        with tempfile.TemporaryDirectory(prefix="collector-package-") as temporary:
            target = Path(temporary) / "app"
            target.mkdir()
            for line in (ROOT / "learning_server/Dockerfile").read_text().splitlines():
                parts = shlex.split(line)
                if not parts or parts[0] != "COPY":
                    continue
                destination = target / parts[-1].removeprefix("/app/")
                for name in parts[1:-1]:
                    source = ROOT / name
                    if source.is_dir():
                        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, destination)
            probe = r'''
import io, json, os, sys, uuid
from pathlib import Path
sys.path.insert(0, sys.argv[1])
os.environ["STUDY_DATA_DB"] = str(Path(sys.argv[1]).parent / "private/learning.sqlite3")
os.environ["STUDY_OPEN_REGISTRATION"] = "1"
from learning_server.wsgi import application
from learning_data.collection import NOTICE
from learning_data.privacy import receipt
body = json.dumps({"participant": str(uuid.uuid4()), "registration_secret": "a" * 64,
                   "notice": NOTICE, "consent": receipt()}).encode()
status = []
result = json.loads(b"".join(application({"REQUEST_METHOD": "POST", "PATH_INFO": "/v1/enroll/open",
    "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)},
    lambda value, headers: status.append(value))))
assert status == ["200 OK"], status
assert len(result["token"]) == 64
assert not any(name.split(".")[0] in {"aiprep", "gui", "study", "adaptive"} for name in sys.modules)
print("isolated registration OK")
'''
            result = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(target)], cwd=target,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("isolated registration OK", result.stdout)
