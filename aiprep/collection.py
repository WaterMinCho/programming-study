# -*- coding: utf-8 -*-
"""동의한 뒤의 풀이를 저장소 밖 SQLite에 보관함. 서버 전송과 모델 학습은 하지 않음."""
import contextlib
import datetime
import functools
import hashlib
import json
import os
import sqlite3
import tempfile
import uuid

FORMAT = 1
NOTICE = "2026-11-08-v1"
FILENAME = "learning-data.sqlite3"
SYNC_FILENAME = "learning-data-sharing.json"


class CollectionError(Exception):
    """추가 풀이 데이터를 저장하거나 내보내지 못함."""


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(packed(value).encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=1)
def runtime_revision():
    paths = ("collection.py", "service.py", "mock.py", "grade.py", "gen.py", "skel.py")
    values = {}
    for name in paths:
        with open(os.path.join(os.path.dirname(__file__), name), "rb") as source:
            values[name] = hashlib.sha256(source.read()).hexdigest()
    return digest(values)


def inside(path, folder):
    try:
        return os.path.commonpath((os.path.realpath(path), os.path.realpath(folder))) == os.path.realpath(folder)
    except ValueError:  # Windows의 서로 다른 드라이브를 다룸
        return False


def question(item, **metadata):
    """실제 지문·보기 순서를 보관하고 채점용 답과 해설은 제외함. 판 해시는 채점 조건도 포함함."""
    order = metadata.pop("option_order", list(range(len(item.get("options") or []))))
    visible = {key: item[key] for key in ("stem", "kind", "pick", "multi") if key in item}
    visible["blanks"] = [{key: b[key] for key in ("mode", "hint", "slot") if key in b} for b in item.get("blanks") or []]
    visible["options"] = [{"no": n, "text": item["options"][n]["text"]} for n in order]
    metadata["runtime_revision"] = runtime_revision()
    visible.update(metadata)
    revision = digest({"item": item, "metadata": metadata, "order": order})
    return {"revision": revision, "content": visible}


class Collection:
    def __init__(self, home, repository):
        self.path = os.path.join(home, FILENAME)
        self.repository = repository
        self.error = ""
        self.missed = 0

    def _check_path(self):
        if inside(self.path, self.repository):
            raise CollectionError("추가 학습 데이터는 공개 저장소 밖에 보관해야 합니다.")

    @contextlib.contextmanager
    def _connect(self, create=False):
        self._check_path()
        if create:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        conn = None
        try:
            if create:
                try:
                    fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(fd)
                conn = sqlite3.connect(self.path, timeout=0.2)
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS items (revision TEXT PRIMARY KEY, payload TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                        at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, item_revision TEXT
                    );
                """)
                conn.execute("INSERT OR IGNORE INTO meta VALUES ('format', ?)", (str(FORMAT),))
                conn.execute("INSERT OR IGNORE INTO meta VALUES ('participant', ?)", (str(uuid.uuid4()),))
            else:
                from pathlib import Path
                conn = sqlite3.connect(Path(self.path).absolute().as_uri() + "?mode=rw", uri=True, timeout=0.2)
            version = conn.execute("SELECT value FROM meta WHERE key='format'").fetchone()
            if version != (str(FORMAT),):
                raise CollectionError("학습 데이터의 파일 형식을 확인해 주세요.")
            with conn:
                yield conn
        except (OSError, sqlite3.Error, TypeError, ValueError) as error:
            raise CollectionError("학습 데이터를 읽거나 저장하지 못했습니다. %s" % error) from error
        finally:
            if conn is not None:
                conn.close()

    def status(self):
        out = {"enabled": False, "events": 0, "items": 0, "path": self.path, "error": self.error, "missed": self.missed}
        if not os.path.exists(self.path):
            return out
        try:
            with self._connect() as conn:
                meta = dict(conn.execute("SELECT key, value FROM meta"))
                out.update(enabled=meta.get("enabled") == "1", participant=meta.get("participant"), epoch=meta.get("epoch"), notice=meta.get("notice"),
                           events=conn.execute("SELECT count(*) FROM events WHERE kind NOT IN ('consent', 'withdraw')").fetchone()[0],
                           items=conn.execute("SELECT count(*) FROM items").fetchone()[0])
        except CollectionError as error:
            out["error"] = str(error)
        return out

    def set_enabled(self, enabled):
        if not enabled and not os.path.exists(self.path):
            return
        with self._connect(create=not os.path.exists(self.path)) as conn:
            previous = conn.execute("SELECT value FROM meta WHERE key='enabled'").fetchone()
            if previous == ("1" if enabled else "0",):
                return
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('enabled', ?)", ("1" if enabled else "0",))
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('notice', ?)", (NOTICE,))
            if enabled:
                conn.execute("INSERT OR REPLACE INTO meta VALUES ('epoch', ?)", (str(uuid.uuid4()),))
            conn.execute("INSERT INTO events(event_id, at, kind, payload) VALUES (?, ?, ?, ?)",
                         (str(uuid.uuid4()), stamp(), "consent" if enabled else "withdraw", packed({"notice": NOTICE})))

    def emit(self, kind, payload, item=None, key=None, at=None):
        """수집 실패가 채점·학습을 막지 않게 함. 실패 수와 까닭을 관리 화면에 남김."""
        if not os.path.exists(self.path):
            return False
        try:
            with self._connect() as conn:
                meta = dict(conn.execute("SELECT key, value FROM meta"))
                if meta.get("enabled") != "1":
                    return False
                payload = dict(payload)
                if at is not None:
                    payload["source_at"] = at
                eid = str(uuid.uuid5(uuid.UUID(meta["participant"]), key)) if key else str(uuid.uuid4())
                revision = item["revision"] if item else None
                if item:
                    conn.execute("INSERT OR IGNORE INTO items VALUES (?, ?)", (revision, packed(item["content"])))
                conn.execute("INSERT OR IGNORE INTO events(event_id, at, kind, payload, item_revision) VALUES (?, ?, ?, ?, ?)",
                             (eid, stamp(), kind, packed(payload), revision))
            return True
        except (CollectionError, KeyError, ValueError) as error:
            self.missed += 1
            self.error = "추가 학습 데이터 %d건을 저장하지 못했습니다. 기존 풀이 기록은 유지됩니다. %s" % (self.missed, error)
            return False

    def snapshot(self, after=0, limit=None, include_answers=False):
        """현재 저장한 판을 읽음. 전송을 확인한 순서 뒤부터 묶어 읽을 수 있음."""
        with self._connect() as conn:
            conn.execute("BEGIN")
            meta = dict(conn.execute("SELECT key, value FROM meta"))
            header = {"kind": "manifest", "format": FORMAT, "track": "ai", "participant": meta["participant"],
                      "exported_at": stamp(), "include_answers": bool(include_answers), "notice": meta.get("notice")}
            sql = "SELECT seq, event_id, at, kind, payload, item_revision FROM events WHERE seq>? ORDER BY seq"
            params = (after,)
            if limit is not None:
                sql += " LIMIT ?"
                params += (limit,)
            rows = [header]
            for seq, eid, at, kind, payload, revision in conn.execute(sql, params):
                data = json.loads(payload)
                if not include_answers:
                    data.pop("response", None)
                item = conn.execute("SELECT payload FROM items WHERE revision=?", (revision,)).fetchone() if revision else None
                rows.append({"format": FORMAT, "track": "ai", "participant": meta["participant"], "sequence": seq,
                             "event_id": eid, "at": at, "kind": kind, "data": data,
                             "item_revision": revision, "item": json.loads(item[0]) if item else None})
        return rows

    def export(self, destination, include_answers=False):
        """일관된 스냅샷을 임시 파일에 쓰고 다시 읽어 확인한 뒤 내보냄. 기존 파일은 덮어쓰지 않음."""
        destination = os.path.abspath(destination)
        if inside(destination, self.repository) or inside(destination, os.path.dirname(self.path)):
            raise CollectionError("공개 저장소와 학습 데이터 폴더 밖의 새 파일을 골라 주세요.")
        if os.path.lexists(destination):
            raise CollectionError("이미 있는 파일입니다. 다른 이름을 골라 주세요.")
        temp = None
        try:
            rows = self.snapshot(include_answers=include_answers)
            fd, temp = tempfile.mkstemp(prefix=".learning-data-", dir=os.path.dirname(destination))
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                for row in rows:
                    output.write(packed(row) + "\n")
                output.flush()
                os.fsync(output.fileno())
            with open(temp, encoding="utf-8") as saved:
                if [json.loads(line) for line in saved] != rows:
                    raise CollectionError("내보낸 파일의 내용을 확인하지 못했습니다.")
            os.link(temp, destination)  # 다른 실행이 먼저 만든 파일을 덮어쓰지 않음
            with open(temp, "rb") as saved:
                checksum = hashlib.sha256(saved.read()).hexdigest()
            return {"path": destination, "events": len(rows) - 1, "sha256": checksum}
        except (OSError, sqlite3.Error, ValueError) as error:
            raise CollectionError("학습 데이터를 내보내지 못했습니다. %s" % error) from error
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)

    def delete(self):
        """수집을 중단하고 이 기기의 추가 데이터 파일을 지움. 제출·학습 기록은 건드리지 않음."""
        self._check_path()
        if os.path.exists(self.path):
            try:
                self.set_enabled(False)
            except CollectionError:  # 읽지 못하는 추가 파일도 사용자가 삭제할 수 있게 함
                pass
            try:
                os.unlink(self.path)
            except OSError as error:
                raise CollectionError("추가 학습 데이터를 지우지 못했습니다. %s" % error) from error
        self.error, self.missed = "", 0


def command(args):
    import study
    from aiprep.service import home_dir
    user = study.current_user(args)
    store = Collection(os.path.join(home_dir(), user), study.ROOT)
    try:
        if args.action in ("enable", "delete") and not args.agree:
            raise CollectionError("수집 항목은 README의 학습 데이터 안내에서 확인해 주세요. 동의한 뒤 --agree를 붙여 실행해 주세요.")
        if args.action in ("enable", "disable"):
            store.set_enabled(args.action == "enable")
        elif args.action == "delete":
            store.delete()
        elif args.action == "export":
            if not args.out:
                raise CollectionError("내보낼 새 파일을 --out으로 지정해 주세요.")
            result = store.export(args.out, include_answers=args.include_answers)
            print("파일을 다시 읽어 %d건을 확인했습니다.\n%s\nSHA-256: %s" % (result["events"], result["path"], result["sha256"]))
            return
        status = store.status()
        print("%s · 학습 동작 %d건\n%s" % ("수집 중" if status["enabled"] else "수집 안 함", status["events"], status["path"]))
        if status["error"]:
            raise CollectionError(status["error"])
    except CollectionError as error:
        study.die(str(error))
