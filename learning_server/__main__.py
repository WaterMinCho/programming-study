# -*- coding: utf-8 -*-
"""서버 실행·초대 코드 발급·학습용 비공개 내보내기를 제공함."""
import argparse
import json
from pathlib import Path
import sqlite3

from learning_data.collection import CollectionError, packed
from learning_server.app import MAX_BODY, Database, application


def main():
    parser = argparse.ArgumentParser(description="비공개 학습 데이터 수집 서버입니다.")
    parser.add_argument("--db", help="공개 저장소 밖의 SQLite 파일")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--production", action="store_true", help="Waitress로 운영용 서버를 실행합니다.")
    invite = sub.add_parser("invite")
    invite.add_argument("--count", type=int, default=1)
    invite.add_argument("--days", type=int, default=7)
    export = sub.add_parser("export")
    export.add_argument("--out", required=True)
    export.add_argument("--include-answers", action="store_true")
    pilot = sub.add_parser("pilot", help="이전 시범 API용입니다. 네 명에게 과목별 초대 코드를 발급합니다.")
    pilot.add_argument("--url", required=True, help="참가자가 접속할 HTTPS 주소")
    pilot.add_argument("--out", required=True, help="저장소와 데이터 폴더 밖의 새 폴더")
    pilot.add_argument("--days", type=int, default=7)
    class_invites = sub.add_parser("class-invites", help="이전 시범 API용입니다. 참가자마다 초대 파일 하나를 발급합니다.")
    class_invites.add_argument("--url", required=True)
    class_invites.add_argument("--out", required=True)
    class_invites.add_argument("--count", type=int, default=100)
    class_invites.add_argument("--days", type=int, default=7)
    sub.add_parser("status", help="기존 DB의 무결성과 과목별 기록 수를 확인합니다.")
    capacity = sub.add_parser("capacity", help="운영 폴더 전체의 용량과 보관량 상한을 확인합니다.")
    capacity.add_argument("--storage-root", required=True)
    capacity.add_argument("--quota-mib", type=int, required=True)
    capacity.add_argument("--warn-percent", type=int, default=80)
    capacity.add_argument("--verify", action="store_true", help="원본 전체와 누적 보관량을 별도로 대조합니다.")
    backup = sub.add_parser("backup", help="기존 DB와 인증 키를 함께 백업합니다.")
    backup.add_argument("--out", required=True)
    restore = sub.add_parser("restore", help="검증한 백업을 새 폴더에 복구합니다.")
    restore.add_argument("--from", dest="source", required=True)
    restore.add_argument("--out", required=True)
    check = sub.add_parser("check", help="참가자가 쓰는 주소로 서버 상태를 확인합니다.")
    check.add_argument("--url", required=True)
    cohorts = sub.add_parser("cohorts", help="희망 직무별 풀이 경향을 비공개로 집계합니다.")
    cohorts.add_argument("--input", help="내보낸 JSONL 파일")
    cohorts.add_argument("--out", required=True, help="원본·저장소 밖의 새 폴더")
    cohorts.add_argument("--synthetic", action="store_true", help="합성 입력임을 명시합니다.")
    legacy_import = sub.add_parser("legacy-import", help="동의를 확인한 기존 프로필을 로컬 DB에 이관합니다.")
    legacy_import.add_argument("--manifest", required=True, help="비공개 이관 목록 JSON 파일")
    legacy_import.add_argument("--catalog", help="문제 은행을 두지 않은 서버에서 사용할 개념 목록 JSON 파일")
    legacy_import.add_argument("--dry-run", action="store_true", help="원본과 기존 DB를 읽고 저장 예정 건수만 확인합니다.")
    legacy_ai = sub.add_parser("legacy-ai-import", help="동의를 확인한 과거 AI 판정을 보관합니다.")
    legacy_ai.add_argument("--manifest", required=True)
    legacy_ai.add_argument("--dry-run", action="store_true")
    legacy_remove = sub.add_parser("legacy-remove", help="기존 프로필 이관을 되돌리거나 철회를 처리합니다.")
    legacy_remove.add_argument("--participant", required=True, help="비공개 이관 목록에 고정한 UUID 가명값")
    legacy_remove.add_argument("--reason", required=True, choices=("rollback", "withdrawal"))
    args = parser.parse_args()
    if args.command in ("legacy-import", "legacy-ai-import", "legacy-remove"):
        try:
            from learning_server import legacy
            from learning_server.app import ApiError
            if not args.db:
                raise ValueError("기존 서버 데이터 파일을 --db로 지정해 주세요.")
            if args.command == "legacy-ai-import":
                from learning_server import legacy_ai
                result = legacy_ai.transfer(args.db, args.manifest, dry_run=args.dry_run)
            elif args.command == "legacy-import":
                if args.catalog:
                    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
                    if not isinstance(catalog, dict) or not catalog or any(
                            not isinstance(key, str) or not isinstance(row, dict) or set(row) != {"unit", "tags", "kind", "type"}
                            or any(not isinstance(row[name], str) for name in ("unit", "kind", "type"))
                            or not isinstance(row["tags"], list) or any(not isinstance(tag, str) for tag in row["tags"])
                            for key, row in catalog.items()):
                        raise ValueError("개념 목록의 형식을 확인해 주세요.")
                else:
                    try:
                        import adaptive
                    except ModuleNotFoundError as error:
                        if error.name != "adaptive":
                            raise
                        raise ValueError("문제 은행이 없는 서버에서는 --catalog를 지정해 주세요.") from None
                    catalog = adaptive.catalog()
                    if not catalog:
                        raise ValueError("문제 은행이 비어 있습니다. --catalog를 지정해 주세요.")
                result = legacy.transfer(args.db, args.manifest, catalog, dry_run=args.dry_run)
            else:
                result = legacy.remove_transfer(args.db, args.participant, reason=args.reason)
            print(packed(result))
            return
        except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error, ApiError):
            parser.exit(1, packed({"status": "error", "code": "legacy_transfer_failed"}) + "\n")
    try:
        if args.command in ("check", "restore", "status", "backup", "capacity"):
            from learning_server import operations
            if args.command == "check":
                result = operations.check(args.url)
            elif args.command == "restore":
                result = operations.restore(args.source, args.out)
            elif not args.db:
                raise ValueError("기존 서버 데이터 파일을 --db로 지정해 주세요.")
            elif args.command == "status":
                result = operations.status(args.db)
            elif args.command == "capacity":
                from learning_server.capacity import report
                result = report(args.db, args.storage_root, args.quota_mib, args.warn_percent, args.verify)
            else:
                result = operations.backup(args.db, args.out)
            print(packed(result))
            if args.command == "capacity" and result["warnings"]:
                parser.exit(2)
            return
        if args.command == "cohorts":
            from learning_server.cohorts import export as export_cohorts
            if bool(args.input) == bool(args.db):
                raise ValueError("--input 또는 --db 중 하나를 지정해 주세요.")
            result = export_cohorts(args.input or args.db, args.out, database=bool(args.db), synthetic=args.synthetic)
            print("희망 직무별 집계 파일을 저장하고 다시 읽어 확인했습니다. %s\n%s" % (args.out, result["cohorts_sha256"]))
            return
        if not args.db:
            raise ValueError("서버 데이터 파일을 --db로 지정해 주세요.")
        if args.command == "export":
            from learning_server.operations import export
            result = export(args.db, args.out, include_answers=args.include_answers)
            print("학습용 파일을 다시 읽어 %d건을 확인했습니다. %s\nSHA-256: %s" % (result["events"], args.out, result["sha256"]))
            return
        db = Database(args.db)
        if args.command == "invite":
            for code in db.invites(args.count, args.days):
                print(code)
        elif args.command == "pilot":
            from learning_server.operations import pilot
            pilot(db, args.out, args.url, args.days)
            print("네 명의 개인 초대 파일을 저장하고 다시 읽어 확인했습니다. 초대 코드는 화면에 출력하지 않습니다.")
        elif args.command == "class-invites":
            from learning_server.operations import class_invites
            result = class_invites(db, args.out, args.url, args.count, args.days)
            print("%d명의 API 개인 초대를 파일로 저장하고 다시 읽어 확인했습니다." % result["members"])
        elif args.production:
            try:
                from waitress import serve
            except ImportError:
                raise ValueError("learning_server/requirements.txt의 운영 패키지를 먼저 설치해 주세요.") from None
            print("운영용 수집 서버를 시작했습니다. 외부 연결은 HTTPS 프록시에서 처리해 주세요.")
            serve(application(db), host=args.host, port=args.port, threads=4,
                  max_request_body_size=6 * MAX_BODY, channel_timeout=30, expose_tracebacks=False)
        else:
            from wsgiref.simple_server import make_server
            with make_server(args.host, args.port, application(db)) as server:
                print("개발용 수집 서버를 시작했습니다. 종료하려면 Ctrl+C를 누르세요.")
                server.serve_forever()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, CollectionError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
