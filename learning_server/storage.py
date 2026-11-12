# -*- coding: utf-8 -*-
"""저장·삭제와 같은 트랜잭션에서 논리 보관량을 갱신함."""

TABLE = "storage_totals"
TRIGGERS = {"storage_%s_%s" % (table, action)
            for table in ("events", "files") for action in ("insert", "delete", "update")}


def initialize(db):
    """기존 기록을 바꾸지 않고 첫 이관 때만 보관량을 집계함."""
    db.execute("BEGIN IMMEDIATE")
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if not TRIGGERS <= names or db.execute("SELECT 1 FROM storage_totals WHERE participant=''").fetchone() is None:
            raise ValueError("기록 보관량 집계의 무결성을 확인해 주세요.")
        return
    db.execute("""CREATE TABLE storage_totals (
        participant TEXT PRIMARY KEY, events INTEGER NOT NULL CHECK(events>=0),
        bytes INTEGER NOT NULL CHECK(bytes>=0))""")
    db.execute("""INSERT INTO storage_totals
        SELECT participant, count(*), sum(length(CAST(payload AS BLOB))) FROM events GROUP BY participant""")
    db.execute("""INSERT INTO storage_totals
        SELECT participant, 0, coalesce(sum(length(payload)),0) FROM api_submissions GROUP BY participant
        ON CONFLICT(participant) DO UPDATE SET bytes=storage_totals.bytes+excluded.bytes""")
    db.execute("""INSERT INTO storage_totals
        SELECT '', coalesce(sum(events),0), coalesce(sum(bytes),0) FROM storage_totals""")
    for name, table, count in (("events", "events", 1), ("files", "api_submissions", 0)):
        def size(row):
            return "coalesce(length(CAST(%s.payload AS BLOB)),0)" % row

        add = ("INSERT INTO storage_totals VALUES (new.participant, %d, %s), ('', %d, %s) "
               "ON CONFLICT(participant) DO UPDATE SET events=storage_totals.events+excluded.events, "
               "bytes=storage_totals.bytes+excluded.bytes;" % (count, size("new"), count, size("new")))
        remove = ("UPDATE storage_totals SET events=events-%d, bytes=bytes-%s "
                  "WHERE participant IN (old.participant,'');" % (count, size("old")))
        for action, body in (("insert", add), ("delete", remove), ("update", remove + add)):
            when = " WHEN old.participant IS NOT new.participant OR old.payload IS NOT new.payload" if action == "update" else ""
            db.execute("CREATE TRIGGER storage_%s_%s AFTER %s ON %s%s BEGIN %s END" %
                       (name, action, action.upper(), table, when, body))


def usage(db, participant=""):
    row = db.execute("SELECT events, bytes FROM storage_totals WHERE participant=?", (participant,)).fetchone()
    return row or (0, 0)
