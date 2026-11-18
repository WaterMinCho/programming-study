# -*- coding: utf-8 -*-
"""호스팅 백업의 재시도·무결성·자기 사본 정리 범위와 콘솔이 꺼졌을 때의 직접 받기·알림을 합성 DB로 확인함."""
import contextlib
import datetime
import io
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
            status = None
            capacity = "ok"
            def __init__(self):
                self.direct = {}
                self.requests = []
            def call(self, path, data=None):
                self.identity = json.loads((Path(test.config["destination"]) / "state.json").read_bytes())["pending"]
                if self.status:
                    raise backup.ApiError("호스팅 API 요청에 실패했습니다.", self.status)
                return b'{}'
            def file(self, path, maximum=1024*1024):
                self.requests.append(path)
                if path.startswith(test.config["db"]):
                    suffix = path[len(test.config["db"]):]
                    value = self.direct.get(suffix, {"": test.path.read_bytes(), ".key": operations.read_key(test.path)}.get(suffix))
                    if isinstance(value, list):
                        value = value.pop(0) if len(value) > 1 else value[0]
                    return value
                if path.endswith("checkpoint.json"):
                    if self.missing:
                        return None
                    return json.dumps({"purpose": "offsite_checkpoint", "identity": self.identity,
                                       "capacity": {"status": self.capacity}}).encode()
                raw = (test.server / Path(path).name).read_bytes()
                return b"corrupt" if self.corrupt and path.endswith(".key") else raw
        self.api = Api()
        patcher = mock.patch.object(backup, "notify", return_value=True)
        self.notify = patcher.start()
        self.addCleanup(patcher.stop)

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
        (self.root / "managed" / previous / ".checkpoint-interrupted").write_bytes(b"partial")
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
        for change in ({"host": "attacker.invalid"}, {"remote_root": config["repo"] + "/backup"}, {"db": "/home/other/data"}, {"remote_root": "/home/example/data/offsite"}):
            path.write_text(json.dumps(dict(config, **change)))
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                backup.configuration(path)
        path.write_text(json.dumps(config))
        path.chmod(0o600)
        loaded, secret = backup.configuration(path)
        self.assertEqual("a" * 40, secret)
        self.assertEqual(config["host"], loaded["host"])


TOKEN = "tok_" + "s" * 30


class FallbackAlertTest(unittest.TestCase):
    setUp = BackupTest.setUp

    def state(self):
        return json.loads((Path(self.config["destination"]) / "state.json").read_bytes())

    def write_state(self, value):
        root = Path(self.config["destination"])
        root.mkdir(parents=True, exist_ok=True)
        (root / "state.json").write_text(json.dumps(value))

    def direct_requests(self):
        return [path for path in self.api.requests if path.startswith(self.config["db"])]

    def main(self):
        out = io.StringIO()
        with mock.patch.object(backup, "configuration", return_value=(self.config, TOKEN)), \
                mock.patch.object(backup, "Api", return_value=self.api), \
                mock.patch("sys.argv", ["collector_backup", "--config", "unused"]), \
                contextlib.redirect_stdout(out):
            code = backup.main()
        return code, out.getvalue()

    def test_normal_console_run_does_not_use_direct_copy_or_alert(self):
        notifier = mock.Mock(return_value=True)
        result = backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.assertEqual(("ok", "console", []), (result["status"], result["path"], result["problems"]))
        self.assertEqual([], self.direct_requests())
        notifier.assert_not_called()
        state = self.state()
        self.assertEqual(state["latest"], state["remote_latest"])
        self.assertEqual(0, state["consecutive_failures"])

    def test_console_412_falls_back_to_verified_direct_copy(self):
        backup.run(self.config, self.api, polls=1)
        before = self.state()
        self.api.status = 412
        notifier = mock.Mock(return_value=True)
        result = backup.run(self.config, self.api, polls=1, notifier=notifier, pause=lambda seconds: None)
        self.assertEqual(("warning", "files", True), (result["status"], result["path"], result["verified"]))
        self.assertIn("console_unavailable", result["problems"])
        state = self.state()
        self.assertEqual(before["capacity"], state["capacity"])
        self.assertEqual(before["capacity_checked_at"], state["capacity_checked_at"])
        self.assertEqual(before["latest"], state["remote_latest"])
        self.assertEqual(self.api.identity, state["latest"])
        self.assertIsNone(state["pending"])
        root = Path(self.config["destination"])
        folder = root / self.api.identity
        self.assertEqual("files", json.loads((folder / "checkpoint.json").read_bytes())["path"])
        operations.restore(folder, self.root / "restored")
        self.assertEqual(operations.read_key(self.path), operations.read_key(self.root / "restored/learning.sqlite3"))
        self.assertEqual([], list(root.glob("*.direct")) + list(root.glob("*.pending")))
        self.assertEqual(1, notifier.call_count)
        self.assertIn("전용 콘솔이 꺼져", notifier.call_args.args[1])

    def test_database_changing_while_downloading_is_not_promoted(self):
        raw = self.path.read_bytes()
        self.api.status = 412
        self.api.direct[""] = [raw + bytes([index]) for index in range(6)] + [raw + b"z"]
        pause = mock.Mock()
        with self.assertRaises(backup.BackupError) as caught:
            backup.run(self.config, self.api, polls=1, pause=pause)
        self.assertEqual("direct_unstable", caught.exception.stage)
        self.assertEqual(2, pause.call_count)
        root = Path(self.config["destination"])
        identity = self.api.identity
        for name in (identity, identity + ".direct", identity + ".pending"):
            self.assertFalse((root / name).exists())
        state = self.state()
        self.assertEqual(identity, state["pending"])
        self.assertNotIn("latest", state)
        self.assertEqual({"stage": "direct_unstable", "http": None}, {k: state["last_error"][k] for k in ("stage", "http")})

    def test_database_changing_only_on_first_try_succeeds_on_second(self):
        raw = self.path.read_bytes()
        self.api.status = 412
        self.api.direct[""] = [raw, raw + b"x", raw]
        pause = mock.Mock()
        result = backup.run(self.config, self.api, polls=1, pause=pause)
        self.assertEqual("files", result["path"])
        self.assertEqual(1, pause.call_count)

    def test_journal_retries_without_database_download_and_wal_stops(self):
        self.api.status = 412
        self.api.direct["-journal"] = b"busy"
        pause = mock.Mock()
        with self.assertRaises(backup.BackupError) as caught:
            backup.run(self.config, self.api, polls=1, pause=pause)
        self.assertEqual("direct_busy", caught.exception.stage)
        self.assertEqual(2, pause.call_count)
        self.assertNotIn(self.config["db"], self.direct_requests())
        self.api.direct = {"-wal": b"wal"}
        pause.reset_mock()
        with self.assertRaises(backup.BackupError) as caught:
            backup.run(self.config, self.api, polls=1, pause=pause)
        self.assertEqual("direct_wal", caught.exception.stage)
        pause.assert_not_called()

    def test_key_changing_during_direct_copy_fails(self):
        self.api.status = 412
        self.api.direct[".key"] = [operations.read_key(self.path), b"k" * 32]
        with self.assertRaises(backup.BackupError) as caught:
            backup.run(self.config, self.api, polls=1, pause=lambda seconds: None)
        self.assertEqual("direct_key", caught.exception.stage)
        self.assertFalse((Path(self.config["destination"]) / self.api.identity).exists())

    def test_other_http_errors_do_not_fall_back_and_log_has_no_secrets(self):
        for status in (401, 429, 500):
            with self.subTest(status=status):
                self.api.status = status
                self.api.requests = []
                code, output = self.main()
                self.assertEqual(1, code)
                line = json.loads(output)
                self.assertEqual(("error", "offsite_backup_failed", "send_input", status),
                                 (line["status"], line["code"], line["stage"], line["http"]))
                datetime.datetime.fromisoformat(line["at"])
                for secret in (TOKEN, self.config["db"], self.config["destination"], self.config["remote_root"]):
                    self.assertNotIn(secret, output)
                self.assertEqual([], self.direct_requests())

    def test_console_after_direct_copy_cleans_remote_latest(self):
        backup.run(self.config, self.api, polls=1)
        remote = self.api.identity
        self.api.status = 412
        backup.run(self.config, self.api, polls=1, pause=lambda seconds: None)
        self.assertNotEqual(remote, self.api.identity)
        self.api.status = None
        with mock.patch.object(backup, "command", wraps=backup.command) as command:
            backup.run(self.config, self.api, polls=1)
        self.assertEqual(remote, command.call_args.args[2])
        self.assertEqual(self.api.identity, self.state()["remote_latest"])

    def test_alerts_once_per_change_repeat_after_a_day_and_on_recovery(self):
        base = datetime.datetime.now(datetime.timezone.utc)
        self.write_state({"backup_created_at": (base - datetime.timedelta(hours=13)).isoformat(),
                          "checked_at": (base - datetime.timedelta(hours=13)).isoformat()})
        self.api.status = 401
        notifier = mock.Mock(return_value=True)
        counts = []
        for offset in (datetime.timedelta(0), datetime.timedelta(minutes=1), datetime.timedelta(minutes=2),
                       datetime.timedelta(hours=24, minutes=3)):
            with self.assertRaises(ValueError):
                backup.run(self.config, self.api, polls=1, notifier=notifier, now=base + offset)
            counts.append(notifier.call_count)
        self.assertEqual([1, 2, 2, 3], counts)
        texts = [item.args[1] for item in notifier.call_args_list]
        self.assertIn("12시간", texts[0])
        self.assertIn("2번 연속 실패", texts[1])
        self.assertIn("마지막 성공은", texts[1])
        self.assertEqual(["stale", "failed"], self.state()["alert"]["kinds"])
        self.api.status = None
        backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.assertEqual(4, notifier.call_count)
        self.assertEqual("수집 서버 백업이 다시 정상입니다.", notifier.call_args.args[1])
        self.assertIsNone(self.state()["alert"])

    def test_copy_counts_as_stale_only_after_twelve_hours(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        for age, expected in ((datetime.timedelta(hours=12), False), (datetime.timedelta(hours=12, seconds=1), True)):
            state = {"backup_created_at": (now - age).isoformat()}
            self.assertEqual(expected, "stale" in backup.problems(state, now), age)

    def test_single_failure_after_fresh_copy_does_not_alert(self):
        notifier = mock.Mock(return_value=True)
        backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.api.status = 401
        with self.assertRaises(ValueError):
            backup.run(self.config, self.api, polls=1, notifier=notifier)
        notifier.assert_not_called()
        self.assertEqual(1, self.state()["consecutive_failures"])

    def test_failed_notification_keeps_exit_code_and_retries_later(self):
        base = datetime.datetime.now(datetime.timezone.utc)
        self.write_state({"backup_created_at": (base - datetime.timedelta(hours=13)).isoformat()})
        self.api.status = 401
        self.notify.side_effect = OSError("no osascript")
        self.assertEqual(1, self.main()[0])
        self.assertNotIn("alert", self.state())
        self.notify.side_effect = None
        with mock.patch.object(backup, "notify", backup_notify_original), \
                mock.patch.object(backup.subprocess, "run", return_value=mock.Mock(returncode=1)) as run:
            self.assertEqual(1, self.main()[0])
        run.assert_called_once()
        self.assertNotIn("alert", self.state())
        self.notify.return_value = True
        self.assertEqual(1, self.main()[0])
        self.assertEqual(["stale", "failed"], self.state()["alert"]["kinds"])

    def test_notify_passes_text_only_as_argv(self):
        text = 'a" & do shell script "touch /tmp/x'
        with mock.patch.object(backup.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            self.assertTrue(backup_notify_original("제목", text))
        argv = run.call_args.args[0]
        self.assertEqual(["제목", text], argv[-2:])
        scripts = [argv[index + 1] for index, value in enumerate(argv) if value == "-e"]
        self.assertTrue(all(text not in script and "제목" not in script for script in scripts))
        self.assertEqual(10, run.call_args.kwargs["timeout"])

    def test_capacity_warning_alone_repeats_once_a_day(self):
        self.api.capacity = "warning"
        notifier = mock.Mock(return_value=True)
        for _ in range(2):
            result = backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.assertEqual(["capacity"], result["problems"])
        self.assertEqual(1, notifier.call_count)
        state = self.state()
        sent = datetime.datetime.fromisoformat(state["alert"]["sent_at"]) - datetime.timedelta(hours=25)
        state["alert"]["sent_at"] = sent.isoformat()
        self.write_state(state)
        backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.assertEqual(2, notifier.call_count)

    def test_main_exit_codes_and_output_lines(self):
        code, output = self.main()
        line = json.loads(output)
        self.assertEqual((0, "ok", "console", []), (code, line["status"], line["path"], line["problems"]))
        self.api.capacity = "warning"
        code, output = self.main()
        self.assertEqual((2, "warning", ["capacity"]), (code, json.loads(output)["status"], json.loads(output)["problems"]))
        self.assertEqual(1, len(output.strip().splitlines()))

    def test_failure_after_direct_copy_does_not_send_recovery(self):
        backup.run(self.config, self.api, polls=1)
        self.api.status = 412
        notifier = mock.Mock(return_value=True)
        backup.run(self.config, self.api, polls=1, notifier=notifier, pause=lambda seconds: None)
        self.api.status = 500
        with self.assertRaises(backup.BackupError):
            backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.assertEqual(1, notifier.call_count)
        self.assertEqual(["console_unavailable"], self.state()["alert"]["kinds"])
        self.assertEqual(1, self.state()["consecutive_failures"])

    def test_unreadable_database_bytes_fail_at_verify_with_one_line(self):
        self.api.status = 412
        self.api.direct[""] = b"\0" * 8192
        code, output = self.main()
        self.assertEqual(1, code)
        self.assertEqual(1, len(output.strip().splitlines()))
        self.assertEqual("verify", json.loads(output)["stage"])
        state = self.state()
        self.assertEqual(("verify", 1), (state["last_error"]["stage"], state["consecutive_failures"]))
        root = Path(self.config["destination"])
        self.assertEqual([], list(root.glob("*.direct")) + list(root.glob("*.pending")))

    def test_incomplete_response_becomes_api_error(self):
        api = backup.Api({"host": "www.pythonanywhere.com", "username": "example"}, TOKEN)
        response = mock.MagicMock()
        response.__enter__.return_value.read.side_effect = backup.http.client.IncompleteRead(b"", 10)
        api.opener = mock.Mock(open=mock.Mock(return_value=response))
        with self.assertRaises(backup.ApiError) as caught:
            api.file("/home/example/data/learning.sqlite3")
        self.assertIsNone(caught.exception.status)

    def test_wal_probe_request_failure_is_download_stage(self):
        self.api.status = 412
        original = self.api.file
        def file(path, maximum=1024*1024):
            if path.endswith("-wal"):
                raise backup.ApiError("호스팅 API 요청에 실패했습니다.", 503)
            return original(path, maximum)
        self.api.file = file
        with self.assertRaises(backup.BackupError) as caught:
            backup.run(self.config, self.api, polls=1, pause=lambda seconds: None)
        self.assertEqual(("download", 503), (caught.exception.stage, caught.exception.http))

    def test_pending_sent_to_console_is_kept_for_next_console_run(self):
        backup.run(self.config, self.api, polls=1)
        remote = self.state()["remote_latest"]
        self.api.missing = True
        with self.assertRaises(backup.BackupError):
            backup.run(self.config, self.api, polls=1)
        sent = self.state()["pending"]
        self.api.missing = False
        self.api.status = 412
        result = backup.run(self.config, self.api, polls=1, pause=lambda seconds: None)
        state = self.state()
        self.assertEqual("files", result["path"])
        self.assertNotEqual(sent, state["latest"])
        self.assertEqual(sent, state["pending"])
        self.assertEqual(remote, state["remote_latest"])
        self.api.status = None
        with mock.patch.object(backup, "command", wraps=backup.command) as command:
            backup.run(self.config, self.api, polls=1)
        self.assertEqual((sent, remote), command.call_args.args[1:3])
        state = self.state()
        self.assertEqual((sent, sent, None), (state["latest"], state["remote_latest"], state["pending"]))

    def test_alert_without_sent_at_is_sent_again_and_backup_succeeds(self):
        self.write_state({"alert": {"kinds": ["capacity"]}})
        self.api.capacity = "warning"
        notifier = mock.Mock(return_value=True)
        result = backup.run(self.config, self.api, polls=1, notifier=notifier)
        self.assertEqual((True, ["capacity"]), (result["verified"], result["problems"]))
        self.assertEqual(1, notifier.call_count)
        self.assertIn("sent_at", self.state()["alert"])

    def test_configuration_failure_notifies_once_per_run(self):
        out = io.StringIO()
        with mock.patch.object(backup, "configuration", side_effect=PermissionError("denied")), \
                mock.patch("sys.argv", ["collector_backup", "--config", "unused"]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(1, backup.main())
        self.assertEqual("config", json.loads(out.getvalue())["stage"])
        self.notify.assert_called_once_with(backup.TITLE, backup.START_FAILED)

    def test_leftover_direct_folder_is_removed_at_start(self):
        leftover = Path(self.config["destination"]) / "0d1c0d1c-0000-4000-8000-000000000000.direct"
        leftover.mkdir(parents=True)
        (leftover / "learning.sqlite3").write_bytes(b"partial")
        backup.run(self.config, self.api, polls=1)
        self.assertFalse(leftover.exists())


backup_notify_original = backup.notify
