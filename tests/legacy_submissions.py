# -*- coding: utf-8 -*-
"""종료한 공개 게시의 기존 계약을 검사할 때만 불러옴."""
import datetime
import json
import re
import secrets
import zlib

from aiprep.collection import digest
from learning_server.app import ApiError
from learning_server.submissions import Submissions as PrivateSubmissions, clean_files
from tests.legacy_github import Publisher, PublishError


class Submissions(PrivateSubmissions):
    def __init__(self, database, publisher=None):
        super().__init__(database)
        self.publisher = publisher

    def publish(self, participant, data):
        current = data.get("digest")
        if not isinstance(current, str) or not re.fullmatch(r"[a-f0-9]{64}", current):
            raise ApiError(400, "풀이 접수 번호를 확인해 주세요.")
        lease = secrets.token_hex(16)
        now = datetime.datetime.now(datetime.timezone.utc)
        with self.database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM participants WHERE participant=? AND revoked=0", (participant,)).fetchone():
                raise ApiError(401, "철회한 참가자입니다.")
            row = db.execute("SELECT s.payload, s.pr_url, s.lease_until, a.display_id, a.latest, a.public_id FROM api_submissions s "
                             "JOIN submission_accounts a ON a.participant=s.participant WHERE s.participant=? AND s.digest=?",
                             (participant, current)).fetchone()
            if not row:
                raise ApiError(404, "서버에 저장된 풀이 접수를 찾지 못했습니다.")
            payload, url, until, display, latest, public_id = row
            if url:
                return self.receipt(current, url)
            if latest != current or payload is None:
                raise ApiError(409, "더 최근 풀이가 저장돼 이전 접수의 게시를 멈췄습니다.")
            if until and datetime.datetime.fromisoformat(until) > now:
                raise ApiError(409, "GitHub에 게시 중입니다. 잠시 뒤 다시 확인해 주세요.")
            db.execute("UPDATE api_submissions SET lease=?, lease_until=? WHERE participant=? AND digest=?",
                       (lease, (now + datetime.timedelta(seconds=90)).isoformat(), participant, current))
        try:
            envelope = json.loads(zlib.decompress(payload))
            if digest(envelope) != current:
                raise ApiError(503, "저장한 풀이의 무결성을 확인하지 못했습니다.")
            files = envelope["files"]
            clean_files(files)
            publisher = self.publisher or Publisher.configured()
            def before_write():
                with self.database.connect() as db:
                    owned = db.execute("SELECT 1 FROM api_submissions s JOIN participants p ON p.participant=s.participant "
                                       "WHERE s.participant=? AND s.digest=? AND s.lease=? AND s.lease_until>? AND p.revoked=0",
                                       (participant, current, lease, datetime.datetime.now(datetime.timezone.utc).isoformat())).fetchone()
                if not owned:
                    raise PublishError("게시 확인 시간이 지나 멈췄습니다. 다시 제출해 주세요.")

            url = publisher.publish(public_id, display, current, files, before_write=before_write)
            with self.database.connect() as db:
                updated = db.execute("UPDATE api_submissions SET pr_url=? WHERE participant=? AND digest=? AND lease=?",
                                     (url, participant, current, lease)).rowcount
                if not updated:
                    raise PublishError("GitHub 게시 후 서버의 접수 상태를 다시 확인해 주세요.")
            return self.receipt(current, url)
        except PublishError as error:
            raise ApiError(503, str(error)) from None
        except (zlib.error, ValueError, KeyError):
            raise ApiError(503, "저장한 풀이 내용을 확인하지 못했습니다. 관리자에게 알려 주세요.") from None
        finally:
            with self.database.connect() as db:
                db.execute("UPDATE api_submissions SET lease=NULL, lease_until=NULL WHERE participant=? AND digest=? AND lease=?",
                           (participant, current, lease))
