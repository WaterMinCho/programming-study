# -*- coding: utf-8 -*-
"""서버 실행·초대 코드 발급·학습용 비공개 내보내기를 제공함."""
import argparse

from learning_server.app import Database, application


def main():
    parser = argparse.ArgumentParser(description="비공개 학습 데이터 수집 서버입니다.")
    parser.add_argument("--db", required=True, help="공개 저장소 밖의 SQLite 파일")
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
    args = parser.parse_args()
    try:
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
    except (OSError, ValueError) as error:
        parser.exit(1, "오류: %s\n" % error)


if __name__ == "__main__":
    main()
