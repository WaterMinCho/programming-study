# -*- coding: utf-8 -*-
"""서버 실행·초대 코드 발급·학습용 비공개 내보내기를 제공함."""
import argparse
import sqlite3

from learning_server.app import Database, application


def main():
    parser = argparse.ArgumentParser(description="비공개 학습 데이터 수집 서버입니다.")
    parser.add_argument("--db", help="공개 저장소 밖의 SQLite 파일")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    invite = sub.add_parser("invite")
    invite.add_argument("--count", type=int, default=1)
    invite.add_argument("--days", type=int, default=7)
    export = sub.add_parser("export")
    export.add_argument("--out", required=True)
    export.add_argument("--include-answers", action="store_true")
    cohorts = sub.add_parser("cohorts", help="희망 직무별 풀이 경향을 비공개로 집계합니다.")
    cohorts.add_argument("--input", help="내보낸 JSONL 파일")
    cohorts.add_argument("--out", required=True, help="원본·저장소 밖의 새 폴더")
    cohorts.add_argument("--synthetic", action="store_true", help="합성 입력임을 명시합니다.")
    args = parser.parse_args()
    try:
        if args.command == "cohorts":
            from learning_server.cohorts import export as export_cohorts
            if bool(args.input) == bool(args.db):
                raise ValueError("--input 또는 --db 중 하나를 지정해 주세요.")
            result = export_cohorts(args.input or args.db, args.out, database=bool(args.db), synthetic=args.synthetic)
            print("희망 직무별 집계 파일을 저장하고 다시 읽어 확인했습니다. %s\n%s" % (args.out, result["cohorts_sha256"]))
            return
        if not args.db:
            raise ValueError("서버 데이터 파일을 --db로 지정해 주세요.")
        db = Database(args.db)
        if args.command == "invite":
            for code in db.invites(args.count, args.days):
                print(code)
        elif args.command == "export":
            result = db.export(args.out, include_answers=args.include_answers)
            print("학습용 파일을 다시 읽어 %d건을 확인했습니다. %s\nSHA-256: %s" % (result["events"], args.out, result["sha256"]))
        else:
            from wsgiref.simple_server import make_server
            with make_server(args.host, args.port, application(db)) as server:
                print("개발용 수집 서버를 시작했습니다. 종료하려면 Ctrl+C를 누르세요.")
                server.serve_forever()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
