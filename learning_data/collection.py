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

from learning_data import generation, goals

AI_INPUT_SCHEMA = 1
FORMAT = 1
NOTICE = "2026-11-08-v2"
FILENAME = "learning-data.sqlite3"
SYNC_FILENAME = "learning-data-sharing.json"
CURRENT_CONTEXT = object()


class CollectionError(Exception):
    """추가 풀이 데이터를 저장하거나 내보내지 못함."""
    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status, self.code = status, code


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(packed(value).encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=2)
def runtime_revision(track="ai"):
    folder = os.path.dirname(os.path.dirname(__file__))
    values = {}
    paths = ("learning_data/collection.py", "learning_data/generation.py", "aiprep/bank.py",
             "aiprep/service.py", "aiprep/mock.py", "aiprep/grade.py", "aiprep/gen.py", "aiprep/skel.py")
    if track == "python":
        paths = ("session.py", "learning_data/python.py", "adaptive.py", "study.py", "learning_data/collection.py")
    for name in paths:
        with open(os.path.join(folder, name), "rb") as source:
            values[name] = hashlib.sha256(source.read()).hexdigest()
    return digest(values)


def inside(path, folder):
    try:
        return os.path.commonpath((os.path.realpath(path), os.path.realpath(folder))) == os.path.realpath(folder)
    except ValueError:  # Windows의 서로 다른 드라이브를 다룸
        return False


def question(item, **metadata):
    """실제 지문·보기 순서를 보관하고 채점용 답과 해설은 제외함. 문항 버전 해시는 채점 조건도 포함함."""
    order = metadata.pop("option_order", list(range(len(item.get("options") or []))))
    visible = {key: item[key] for key in ("stem", "kind", "pick", "multi") if key in item}
    visible["blanks"] = [{key: b[key] for key in ("mode", "hint", "slot") if key in b} for b in item.get("blanks") or []]
    visible["options"] = [{"no": n, "text": item["options"][n]["text"]} for n in order]
    if item.get("_generation") is not None:
        visible["generation"] = generation.capture(item["_generation"], item, visible)
    metadata["runtime_revision"] = runtime_revision(metadata.pop("track", "ai"))
    visible.update(metadata)
    revision = digest({"item": item, "metadata": metadata, "order": order})
    return {"revision": revision, "content": visible}


class Collection:
    def __init__(self, home, repository, track="ai"):
        if track not in ("ai", "python"):
            raise ValueError("수집 과목을 확인해 주세요.")
        self.track = track
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
            os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
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
                conn.execute("INSERT OR IGNORE INTO meta VALUES ('track', ?)", (self.track,))
            else:
                from pathlib import Path
                conn = sqlite3.connect(Path(self.path).absolute().as_uri() + "?mode=rw", uri=True, timeout=0.2)
            version = conn.execute("SELECT value FROM meta WHERE key='format'").fetchone()
            if version != (str(FORMAT),):
                raise CollectionError("학습 데이터의 파일 형식을 확인해 주세요.")
            saved_track = conn.execute("SELECT value FROM meta WHERE key='track'").fetchone()
            if (saved_track[0] if saved_track else "ai") != self.track:
                raise CollectionError("학습 데이터 파일의 과목이 맞지 않습니다.")
            with conn:
                yield conn
        except (OSError, sqlite3.Error, TypeError, ValueError) as error:
            raise CollectionError("학습 데이터를 읽거나 저장하지 못했습니다. %s" % error) from error
        finally:
            if conn is not None:
                conn.close()

    @property
    def stop_path(self):
        return self.path + ".stopped"

    def _remember_stop(self, stopped):
        self._check_path()
        try:
            if stopped:
                os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
                try:
                    fd = os.open(self.stop_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    return
                os.close(fd)
            elif os.path.exists(self.stop_path):
                os.unlink(self.stop_path)
        except OSError as error:
            raise CollectionError("수집 중단 설정을 저장하지 못했습니다. %s" % error) from error

    def initialize_distribution(self):
        """첫 실행의 명시적 선택 전에는 수집하지 않음. 이전 버전의 기록을 보존하고 수집만 멈춤."""
        from learning_data.privacy import SUPPORTED_POLICIES
        if not os.path.exists(self.path):
            return
        with self._connect() as conn:
            policy = conn.execute("SELECT value FROM meta WHERE key='consent_policy'").fetchone()
            if policy is None or policy[0] not in SUPPORTED_POLICIES:
                conn.execute("INSERT OR REPLACE INTO meta VALUES ('enabled', '0')")

    def latest_sequence(self):
        if not os.path.exists(self.path):
            return 0
        with self._connect() as conn:
            return conn.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0]

    def status(self):
        out = {"enabled": False, "events": 0, "items": 0, "path": self.path, "error": self.error,
               "missed": self.missed, "goal": goals.unselected()}
        if not os.path.exists(self.path):
            return out
        try:
            with self._connect() as conn:
                meta = dict(conn.execute("SELECT key, value FROM meta"))
                out.update(enabled=self._active(meta) and not os.path.exists(self.stop_path), participant=meta.get("participant"), epoch=meta.get("epoch"), notice=meta.get("notice"),
                           goal=json.loads(meta["goal"]) if "goal" in meta else goals.unselected(),
                           events=conn.execute("SELECT count(*) FROM events WHERE kind NOT IN ('consent', 'withdraw', 'goal_changed')").fetchone()[0],
                           items=conn.execute("SELECT count(*) FROM items").fetchone()[0])
        except CollectionError as error:
            out["error"] = str(error)
        return out

    @staticmethod
    def _active(meta):
        if meta.get("enabled") != "1":
            return False
        if meta.get("privacy_state_path"):
            try:
                with open(meta["privacy_state_path"], encoding="utf-8") as source:
                    state = json.load(source)
                from learning_data.privacy import known_policy
                return (state.get("accepted") is True and known_policy(state)
                        and not state.get("withdraw_pending"))
            except (OSError, ValueError, AttributeError):
                return False
        return True

    def set_enabled(self, enabled, renew=False, privacy_state=None):
        from learning_data.privacy import POLICY_VERSION, POLICY_HASH
        if not enabled:
            self._remember_stop(True)
        if not enabled and not os.path.exists(self.path):
            return
        with self._connect(create=not os.path.exists(self.path)) as conn:
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute("SELECT value FROM meta WHERE key='enabled'").fetchone()
            if previous == ("1" if enabled else "0",) and not (enabled and (renew or os.path.exists(self.stop_path))):
                if enabled:
                    self._remember_stop(False)
                return
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('enabled', ?)", ("1" if enabled else "0",))
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('notice', ?)", (NOTICE,))
            goal = goals.unselected()
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('goal', ?)", (packed(goal),))
            if enabled:
                conn.execute("INSERT OR REPLACE INTO meta VALUES ('epoch', ?)", (str(uuid.uuid4()),))
                conn.execute("INSERT OR REPLACE INTO meta VALUES ('consent_policy', ?)", (POLICY_VERSION,))
                if privacy_state is not None:
                    conn.execute("INSERT OR REPLACE INTO meta VALUES ('privacy_state_path', ?)", (str(privacy_state),))
            conn.execute("INSERT INTO events(event_id, at, kind, payload) VALUES (?, ?, ?, ?)",
                         (str(uuid.uuid4()), stamp(), "consent" if enabled else "withdraw", packed({"notice": NOTICE, "goal": goal,
                          "policy": POLICY_VERSION, "policy_hash": POLICY_HASH})))

        if enabled:
            self._remember_stop(False)

    def set_goal(self, goal_id):
        """동의 중에만 선택을 저장함. 같은 목표도 저장할 때마다 현재 로드맵 버전을 읽음."""
        if not os.path.exists(self.path):
            raise CollectionError("추가 데이터 수집을 다시 시작한 뒤 희망 직무를 저장해 주세요.")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if os.path.exists(self.stop_path) or conn.execute("SELECT value FROM meta WHERE key='enabled'").fetchone() != ("1",):
                raise CollectionError("추가 데이터 수집을 다시 시작한 뒤 희망 직무를 저장해 주세요.")
            goal = goals.selection(goal_id, goals.catalog(self.repository), stamp())
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('goal', ?)", (packed(goal),))
            conn.execute("INSERT INTO events(event_id, at, kind, payload) VALUES (?, ?, 'goal_changed', ?)",
                         (str(uuid.uuid4()), goal["selected_at"], packed({"goal": goal})))
        return goal

    def observation_context(self):
        """한 읽기 트랜잭션에서 동의 차수·목표·관찰 시각을 함께 읽음."""
        if not os.path.exists(self.path) or os.path.exists(self.stop_path):
            return None
        try:
            with self._connect() as conn:
                conn.execute("BEGIN")
                meta = dict(conn.execute("SELECT key, value FROM meta"))
                if not self._active(meta):
                    return None
                return {"epoch": meta.get("epoch"),
                        "goal": json.loads(meta["goal"]) if "goal" in meta else goals.unselected(),
                        "observed_at": stamp()}
        except CollectionError as error:
            self.error = str(error)
            return None

    def emit(self, kind, payload, item=None, key=None, at=None, *, observation_context=CURRENT_CONTEXT):
        """수집 실패가 채점·학습을 막지 않게 함. 실패 수와 까닭을 관리 화면에 남김."""
        if not os.path.exists(self.path) or os.path.exists(self.stop_path):
            return False
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                meta = dict(conn.execute("SELECT key, value FROM meta"))
                if not self._active(meta):
                    return False
                payload = dict(payload)
                if observation_context is CURRENT_CONTEXT:
                    payload["goal"] = json.loads(meta["goal"]) if "goal" in meta else goals.unselected()
                else:
                    allowed = {"mock_answer", "mock_submit"}
                    allowed.update({"answer", "python_input", "question_returned"} if self.track == "python" else {"ai_input"})
                    if kind not in allowed:
                        raise ValueError("관찰 문맥을 지정할 수 없는 기록입니다.")
                    context = observation_context or {}
                    payload["goal"] = context.get("goal")
                    payload["observed_at"] = context.get("observed_at")
                    if context.get("epoch") != meta.get("epoch"):
                        if kind in ("mock_submit", "python_input", "ai_input", "question_returned"):
                            return False
                        payload.update(response=None, goal=None, observed_at=None)
                        if payload.get("result") != "blank":
                            payload["result"] = "not_collected"
                if kind in ("answer", "mock_answer") and payload.get("result") != "not_collected" and "response" in payload:
                    response = payload["response"]
                    values = response if isinstance(response, (list, tuple)) else [response]
                    payload["answered"] = any(v is not None and str(v).strip() for v in values)
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
        """현재 저장한 기록을 읽음. 전송을 확인한 순서 뒤부터 묶어 읽을 수 있음."""
        with self._connect() as conn:
            conn.execute("BEGIN")
            meta = dict(conn.execute("SELECT key, value FROM meta"))
            header = {"kind": "manifest", "format": FORMAT, "track": self.track, "participant": meta["participant"],
                      "exported_at": stamp(), "include_answers": bool(include_answers), "notice": meta.get("notice"), "synthetic": False}
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
                rows.append({"format": FORMAT, "track": self.track, "participant": meta["participant"], "sequence": seq,
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
        self._remember_stop(True)
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
    user = study.current_user(args)
    if getattr(args, "track", "ai") == "python":
        from learning_data.python import PythonCollection, home_dir
        store = PythonCollection(os.path.join(home_dir(), user), study.ROOT)
    else:
        from aiprep.service import home_dir
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
