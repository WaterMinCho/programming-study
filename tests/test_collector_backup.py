# -*- coding: utf-8 -*-
"""호스팅 백업의 재시도·무결성·자기 사본 정리 범위를 합성 DB로 확인함."""
import json
from pathlib import Path
import shlex
import shutil
import tempfile
import unittest
from unittest import mock

from learning_server import app, operations
from tools import collector_backup as backup


class BackupTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="offsite_")
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / "server/learning.sqlite3"
        app.Database(str(self.path))
        self.server = self.root / "remote"
        operations.backup(self.path, self.server)
        self.config = {"destination": str(self.root / "local"), "console": 123,
                       "repo": "/home/example/repo", "db": "/home/example/data/learning.sqlite3",
                       "remote_root": "/home/example/backups", "username": "example"}
        test = self
        class Api:
            missing = False
            corrupt = False
            identity = None
            def call(self, path, data=None):
                self.identity = json.loads((Path(test.config["destination"]) / "state.json").read_bytes())["pending"]
                return b'{}'
            def file(self, path, maximum=1024*1024):
                if path.endswith("checkpoint.json"):
                    if self.missing:
                        return None
                    return json.dumps({"purpose": "offsite_checkpoint", "identity": self.identity,
                                       "capacity": {"status": "ok"}}).encode()
                raw = (test.server / Path(path).name).read_bytes()
                return b"corrupt" if self.corrupt and path.endswith(".key") else raw
        self.api = Api()

    def test_download_readback_and_retry_reuse_same_checkpoint_after_unknown_ack(self):
        self.api.missing = True
        with self.assertRaises(ValueError):
            backup.run(self.config, self.api, polls=1)
        identity = self.api.identity
        staging = Path(self.config["destination"]) / (identity + ".pending")
        staging.mkdir()
        (staging / "partial").write_text("interrupted")
        self.api.missing = False
        result = backup.run(self.config, self.api, polls=1)
        self.assertTrue(result["verified"])
        self.assertEqual(identity, self.api.identity)
        folder = Path(self.config["destination"]) / identity
        operations.restore(folder, self.root / "restored")
        state = json.loads((folder.parent / "state.json").read_bytes())
        self.assertIsNone(state["pending"])
        self.assertEqual(identity, state["latest"])
        self.assertFalse(staging.exists())

    def test_bad_hash_removes_partial_copy_and_keeps_pending(self):
        self.api.corrupt = True
        with self.assertRaises(ValueError):
            backup.run(self.config, self.api, polls=1)
        root = Path(self.config["destination"])
        self.assertFalse((root / self.api.identity).exists())
        self.assertFalse((root / (self.api.identity + ".pending")).exists())
        self.assertEqual(self.api.identity, json.loads((root / "state.json").read_bytes())["pending"])

    def test_command_does_not_change_database_and_only_removes_confirmed_owned_copy(self):
        config = dict(self.config, repo=str(Path(__file__).resolve().parents[1]), db=str(self.path), remote_root=str(self.root / "managed"))
        previous, current = "833f8dcf-6503-4514-a620-f84c955bfe53", "d0d36025-80be-44d1-a6de-dba394bda732"
        before = (self.path.read_bytes(), operations.read_key(self.path))
        unrelated = self.root / "managed/manual-backup"
        unrelated.mkdir(parents=True)
        (unrelated / "keep").write_text("keep")
        def execute(identity, old=None):
            code = shlex.split(backup.command(config, identity, old))[2]
            with mock.patch("learning_server.capacity.report", return_value={"status": "ok"}):
                exec(code, {})
        execute(previous)
        (self.root / "managed" / previous / "checkpoint.json").write_bytes(b"")
        execute(previous)
        self.assertEqual(previous, json.loads((self.root / "managed" / previous / "checkpoint.json").read_bytes())["identity"])
        operations.verify_backup(self.root / "managed" / previous)
        execute(current, previous)
        self.assertFalse((self.root / "managed" / previous).exists())
        self.assertEqual("keep", (unrelated / "keep").read_text())
        self.assertEqual(before, (self.path.read_bytes(), operations.read_key(self.path)))
        operations.verify_backup(self.root / "managed" / current)

    def test_missing_local_copy_does_not_authorize_remote_previous_cleanup(self):
        backup.run(self.config, self.api, polls=1)
        root = Path(self.config["destination"])
        previous = self.api.identity
        shutil.rmtree(root / previous)
        with mock.patch.object(backup, "command", wraps=backup.command) as command:
            backup.run(self.config, self.api, polls=1)
        self.assertIsNone(command.call_args.args[2])

    def test_remote_interrupted_staging_is_rebuilt_without_touching_source(self):
        config = dict(self.config, repo=str(Path(__file__).resolve().parents[1]), db=str(self.path), remote_root=str(self.root / "managed"))
        identity = "517832fb-7ee6-410f-9578-45cc31bfc22d"
        staging = self.root / "managed" / (identity + ".pending")
        staging.mkdir(parents=True)
        (staging / "learning.sqlite3").write_bytes(b"interrupted")
        before = (self.path.read_bytes(), operations.read_key(self.path))
        with mock.patch("learning_server.capacity.report", return_value={"status": "ok"}):
            exec(shlex.split(backup.command(config, identity))[2], {})
        self.assertFalse(staging.exists())
        operations.verify_backup(staging.with_name(identity))
        self.assertEqual(before, (self.path.read_bytes(), operations.read_key(self.path)))

    def test_configuration_rejects_foreign_host_public_path_and_shared_token_file(self):
        token = self.root / "token"
        token.write_text("a" * 40)
        token.chmod(0o600)
        config = dict(self.config, host="www.pythonanywhere.com", token_file=str(token))
        path = self.root / "config.json"
        for change in ({"host": "attacker.invalid"}, {"remote_root": config["repo"] + "/backup"}, {"db": "/home/other/data"}):
            path.write_text(json.dumps(dict(config, **change)))
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                backup.configuration(path)
        path.write_text(json.dumps(config))
        path.chmod(0o600)
        loaded, secret = backup.configuration(path)
        self.assertEqual("a" * 40, secret)
        self.assertEqual(config["host"], loaded["host"])
