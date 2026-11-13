# -*- coding: utf-8 -*-
"""개인별 초대·실제 전송·운영 백업과 복구의 보존 범위를 확인함."""
import contextlib
import datetime
import importlib.util
import io
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from aiprep import collection, sharing
from learning_server import app, operations
from learning_server.__main__ import main


def run_server(path, ready):
    from waitress import create_server
    server = create_server(app.application(app.Database(path)), host="127.0.0.1", port=0, threads=4)
    ready.send(server.effective_port)
    ready.close()
    server.run()


class OperationsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="learning_operations_")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "data/learning.sqlite3"
        self.db = app.Database(str(self.path))

    def enroll(self):
        code = self.db.invites()[0]
        packet = {"participant": str(uuid.uuid4()), "invite": code, "notice": collection.NOTICE}
        return packet, self.db.enroll(packet)["token"]

    def test_pilot_issues_two_separate_codes_per_person_without_enrolling(self):
        destination = self.root / "invites"
        stdout = io.StringIO()
        with mock.patch("sys.argv", ["collector", "--db", str(self.path), "pilot", "--url",
                                     "https://collector.example", "--out", str(destination)]):
            with contextlib.redirect_stdout(stdout):
                main()
        codes = []
        for path in sorted(destination.glob("member-*.txt")):
            text = path.read_text(encoding="utf-8")
            self.assertIn("https://collector.example", text)
            self.assertIn("입력 답안 포함은 기본으로 꺼져", text)
            codes.extend(line.split(": ")[1] for line in text.splitlines() if "초대 코드:" in line)
            if os.name != "nt":
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual(8, len(set(codes)))
        self.assertTrue(all(code not in stdout.getvalue() for code in codes))
        self.assertEqual(0, operations.status(self.path)["active_accounts"])
        for code in codes:
            self.db.enroll({"participant": str(uuid.uuid4()), "invite": code, "notice": collection.NOTICE})
        self.assertEqual(8, operations.status(self.path)["active_accounts"])
        if os.name != "nt":
            self.assertEqual(0o700, destination.stat().st_mode & 0o777)

    def test_incomplete_invite_files_roll_back_only_the_new_codes(self):
        self.db.invites(count=1)
        before = operations.status(self.path)
        write_file = operations.write_private

        def fail_manifest(path, data):
            if path.name == "manifest.json":
                raise OSError("manifest write failed")
            write_file(path, data)

        for name, issue in (("pilot", operations.pilot), ("class", operations.class_invites)):
            destination = self.root / name
            with self.subTest(name=name), mock.patch.object(operations, "write_private", side_effect=fail_manifest):
                with self.assertRaises(OSError):
                    issue(self.db, destination, "https://collector.example")
                self.assertFalse(destination.exists())
                self.assertEqual(before, operations.status(self.path))

    def test_pilot_rejects_remote_plaintext_and_existing_output_before_issuing(self):
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("보존", encoding="utf-8")
        before = operations.status(self.path)
        with self.assertRaises(FileExistsError):
            operations.pilot(self.db, destination, "https://collector.example")
        with self.assertRaises(collection.CollectionError):
            operations.pilot(self.db, self.root / "unused", "http://collector.example")
        self.assertEqual(before, operations.status(self.path))
        self.assertEqual("보존", sentinel.read_text(encoding="utf-8"))
        self.assertFalse((self.root / "unused").exists())

    def test_export_uses_an_existing_database_without_initializing_or_replacing_its_key(self):
        output = self.root / "training.jsonl"
        with mock.patch("learning_server.__main__.Database", side_effect=AssertionError("unexpected initialization")):
            with mock.patch("sys.argv", ["collector", "--db", str(self.path), "export", "--out", str(output)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    main()
        self.assertEqual(b"", output.read_bytes())
        for path in (self.root / "missing.sqlite3", self.path):
            Path(str(path) + ".key").unlink(missing_ok=True)
            destination = self.root / "unused.jsonl"
            with self.assertRaises((OSError, ValueError)):
                operations.export(path, destination)
            self.assertFalse(Path(str(path) + ".key").exists())
            self.assertFalse(destination.exists())
        self.assertFalse((self.root / "missing.sqlite3").exists())

    def test_status_never_creates_missing_data_or_key_and_hides_identifiers(self):
        missing = self.root / "missing/server.sqlite3"
        with self.assertRaises((ValueError, OSError)):
            operations.status(missing)
        self.assertFalse(missing.parent.exists())
        packet, token = self.enroll()
        self.db.remove(packet["participant"])
        result = operations.status(self.path)
        self.assertEqual(0, result["active_accounts"])
        self.assertEqual(1, result["revoked_accounts"])
        for secret in (packet["participant"], packet["invite"], token):
            self.assertNotIn(secret, json.dumps(result))
        key = Path(str(self.path) + ".key")
        original = key.read_bytes()
        key.unlink()
        with self.assertRaises(OSError):
            operations.status(self.path)
        self.assertFalse(key.exists())
        key.write_bytes(original)

    def test_status_counts_invite_expiry_as_instants_with_different_timezones(self):
        code = self.db.invites()[0]
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        with self.db.connect() as db:
            db.execute("UPDATE invites SET expires=? WHERE code_hash=?", (future.isoformat(), app.hashed(code)))
        self.assertEqual(1, operations.status(self.path)["available_invites"])
        expired = future - datetime.timedelta(hours=2)
        with self.db.connect() as db:
            db.execute("UPDATE invites SET expires=?", (expired.astimezone(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),))
        self.assertEqual(0, operations.status(self.path)["available_invites"])

    def test_backup_restores_uncheckpointed_writes_key_and_revoked_accounts(self):
        packet, token = self.enroll()
        revoked, revoked_token = self.enroll()
        self.db.remove(revoked["participant"])
        writer = sqlite3.connect(self.path)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")
        for track in ("ai", "python"):
            row = {"participant": packet["participant"], "track": track, "event_id": str(uuid.uuid4()),
                   "sequence": 1, "data": {"response": "보존할 입력"}}
            writer.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?)",
                           (packet["participant"], track, row["event_id"], 1, collection.packed(row)))
        writer.commit()
        backup = self.root / "backup"
        before = self.path.read_bytes()
        result = operations.backup(self.path, backup)
        self.assertEqual(before, self.path.read_bytes())
        with contextlib.closing(sqlite3.connect(backup / "learning.sqlite3")) as standalone:
            self.assertEqual(("delete",), standalone.execute("PRAGMA journal_mode").fetchone())
        self.assertEqual({"ai": 1, "python": 1}, result["state"]["events"])
        restored = self.root / "restored"
        self.assertEqual(result["state"], operations.restore(backup, restored))
        db = app.Database(str(restored / "learning.sqlite3"))
        self.assertEqual(token, db.enroll(packet)["token"])
        with self.assertRaises(app.ApiError):
            db.authenticate("Bearer " + revoked_token)
        with db.connect() as saved:
            self.assertEqual(2, saved.execute("SELECT count(*) FROM events").fetchone()[0])
        if os.name != "nt":
            for name in operations.BACKUP_FILES:
                self.assertEqual(0o600, (restored / name).stat().st_mode & 0o777)

    def test_restore_rejects_tampering_and_existing_output_without_overwriting(self):
        backup = self.root / "backup"
        operations.backup(self.path, backup)
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            operations.restore(backup, destination)
        self.assertEqual(b"keep", sentinel.read_bytes())
        (backup / "learning.sqlite3.key").write_bytes(b"x" * 32)
        with self.assertRaises(ValueError):
            operations.restore(backup, self.root / "bad")
        self.assertFalse((self.root / "bad").exists())

    def test_expired_unused_invite_does_not_invalidate_unchanged_backup(self):
        self.db.invites()[0]
        backup = self.root / "backup"
        operations.backup(self.path, backup)
        self.assertEqual(1, operations.status(self.path)["available_invites"])
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14)
        with mock.patch.object(operations.datetime, "datetime", wraps=datetime.datetime) as clock:
            clock.now.return_value = future
            self.assertEqual(0, operations.status(self.path)["available_invites"])
            operations.verify_backup(backup)
            operations.restore(backup, self.root / "restored")
            self.assertEqual(0, operations.status(self.root / "restored/learning.sqlite3")["available_invites"])

    @unittest.skipIf(os.name == "nt", "심볼릭 링크 생성 권한이 필요한 검사임")
    def test_database_alias_preserves_key_next_to_the_selected_path(self):
        alias = self.path.parent / "alias.sqlite3"
        alias.symlink_to(self.path)
        selected = app.Database(str(alias))
        packet = {"participant": str(uuid.uuid4()), "invite": selected.invites()[0], "notice": collection.NOTICE}
        token = selected.enroll(packet)["token"]
        self.assertEqual(1, operations.status(alias)["active_accounts"])
        backup = self.root / "backup"
        operations.backup(alias, backup)
        self.assertEqual(selected.secret, (backup / "learning.sqlite3.key").read_bytes())
        self.assertNotEqual(self.db.secret, selected.secret)
        operations.restore(backup, self.root / "restored")
        restored = app.Database(str(self.root / "restored/learning.sqlite3"))
        self.assertEqual(token, restored.enroll(packet)["token"])

    def test_backup_rejects_source_directory_and_repository(self):
        with self.assertRaises(ValueError):
            operations.backup(self.path, self.path.parent / "backup")
        with self.assertRaises(ValueError):
            operations.backup(self.path, Path(app.REPOSITORY) / "private-backup")

    def test_health_reports_missing_database_without_recreating_it(self):
        application = app.application(self.db)
        self.path.unlink()
        result = []
        body = b"".join(application({"REQUEST_METHOD": "GET", "PATH_INFO": "/health"},
                                    lambda status, headers: result.append(status)))
        self.assertTrue(result[0].startswith("503 "))
        self.assertNotIn(b"Traceback", body)
        self.assertFalse(self.path.exists())

    def test_production_entrypoint_uses_bounded_waitress_and_status_is_read_only(self):
        serve = mock.Mock()
        with mock.patch.dict("sys.modules", {"waitress": mock.Mock(serve=serve)}):
            with mock.patch("sys.argv", ["collector", "--db", str(self.path), "serve", "--production"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    main()
        options = serve.call_args.kwargs
        self.assertEqual("127.0.0.1", options["host"])
        self.assertEqual(4, options["threads"])
        self.assertEqual(6 * app.MAX_BODY, options["max_request_body_size"])
        self.assertFalse(options["expose_tracebacks"])
        with mock.patch.object(app.Database, "__init__", side_effect=AssertionError("must not create")):
            with mock.patch("sys.argv", ["collector", "--db", str(self.path), "status"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    main()

    @unittest.skipUnless(importlib.util.find_spec("waitress"), "운영 서버 패키지가 필요한 검사임")
    def test_four_people_sync_both_tracks_retry_delete_and_export_over_real_http(self):
        context = multiprocessing.get_context("spawn")
        ready, child = context.Pipe(duplex=False)
        server = context.Process(target=run_server, args=(str(self.path), child))
        server.start()
        child.close()
        try:
            self.assertTrue(ready.poll(20), "운영 서버가 시작하지 못함")
            url = "http://127.0.0.1:%s" % ready.recv()
            self.assertEqual("ok", operations.check(url)["status"])
            codes = iter(self.db.invites(8))
            clients = []
            for person in range(4):
                for track in ("ai", "python"):
                    store = collection.Collection(str(self.root / ("member-%d-%s" % (person, track))),
                                                  str(self.root / "repository"), track=track)
                    store.set_enabled(True)
                    store.emit("answer", {"response": "개인 입력", "result": "pass"})
                    clients.append((sharing.Sharing(store), next(codes)))
            with ThreadPoolExecutor(max_workers=4) as pool:
                sent = list(pool.map(lambda pair: pair[0].sync(url, pair[1])["sent"], clients))
            self.assertEqual([2] * 8, sent)
            self.assertEqual({"ai": 8, "python": 8}, operations.status(self.path)["events"])
            for client, code in clients:
                self.assertEqual(0, client.sync(url)["sent"])
            preserved = Path(clients[0][0].collection.path).read_bytes()
            clients[0][0].delete_remote()
            self.assertEqual(preserved, Path(clients[0][0].collection.path).read_bytes())
            self.assertEqual({"ai": 6, "python": 8}, operations.status(self.path)["events"])
            output = self.root / "events.jsonl"
            self.assertEqual(14, self.db.export(str(output))["events"])
            self.assertNotIn("개인 입력", output.read_text(encoding="utf-8"))
            self.assertTrue(server.is_alive(), "직접 종료하기 전에 운영 서버가 중단됨")
            self.assertIsNone(server.exitcode)
        finally:
            ready.close()
            server.terminate()
            server.join(5)
            if server.is_alive():
                server.kill()
                server.join(5)
            self.assertFalse(server.is_alive())
