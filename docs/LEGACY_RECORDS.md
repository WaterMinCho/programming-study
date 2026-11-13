# 기존 풀이를 비공개 연구 DB에 이관합니다

`legacy-import`는 기존 Python `profile.json`을 변환합니다. `legacy-ai-import`는 AI `record.json`의 과거 판정을 별도로 보관합니다. 원본 전체 파일의 비공개 보관과 SHA-256·저장 후 바이트 확인은 운영자가 별도로 처리합니다.

운영자가 배포한 저장소에서 `legacy-import`를 실행합니다. 네트워크나 공개 API를 거치지 않고 기존 서버 SQLite에 기록합니다. 동의를 확인한 `submissions/개인폴더/profile.json`만 명시적으로 고릅니다. 원본 풀이 코드와 답안 파일은 실행하거나 복사하지 않습니다.

`learning_server.starter --profile`은 이미 연구용 파일을 만드는 명령입니다. 서버 DB에는 저장하지 않습니다. `legacy-import`는 같은 `profile_events()` 변환기를 재사용하고 서버의 보관량 검사와 DB·인증 키 점검을 적용합니다. 서버를 새로 만들거나 초대·전송 인증을 발급하지 않습니다.

## 동의 근거와 이관 목록을 준비합니다

기존 풀이의 비공개 서버 이전과 추천 연구 사용 동의를 각각 확인합니다. 앱 첫 실행 동의나 공개 제출을 과거 기록의 이관 동의로 대신하지 않습니다. 동의를 확인한 날짜만 알면 날짜를 적고 시각은 만들지 않습니다. `confirmed_on`은 운영자가 동의를 확인한 날짜이며 과거 풀이 시각과 구분합니다.

운영자가 전달받은 동의 확인 원문의 질문 식별자와 본인의 명시 요청은 각각 비공개 근거로 연결합니다. `evidence_ref`의 등록과 DB의 `imported_at`은 운영 작업 기록입니다. 참가자가 직접 동의한 시각은 이 형식에서 수집하지 않으며 운영자의 확인 날짜나 이관 계정의 `enrolled` 시각으로 대신하지 않습니다.

이관 목록은 공개 저장소 밖의 운영 폴더에 보관합니다. 아래는 형식을 설명하는 가상 예입니다. 실제 목록의 `profiles`에 동의를 확인한 사람의 항목을 넣습니다. `evidence_ref`는 별도로 보관한 비공개 동의 근거와 연결하는 참조명입니다. 이름·계정·인증 키·동의 원문을 출력용 값에 넣지 않습니다.

```json
{
  "format": 1,
  "timezone": "+09:00",
  "profiles": [
    {
      "participant": "fe6dbf8c-c020-42f6-b9cb-6369239455f9",
      "profile": "/srv/programming-study/submissions/example/profile.json",
      "consent": {
        "confirmed_on": "2026-11-12",
        "evidence_ref": "consent-20261112-member-01",
        "private_server_transfer": true,
        "recommendation_research": true
      }
    }
  ]
}
```

`participant`는 이관 전용 UUID 가명값입니다. 사람마다 새 값을 한 번 정하고 같은 원본을 재실행할 때 유지합니다. 기존 앱의 수집 계정과 섞지 않습니다. `python3 -c 'import uuid; print(uuid.uuid4())'`로 값을 만들 수 있습니다. 실제 계정과 가명값의 대응은 비공개 목록으로 관리합니다. 프로필 경로는 절대 경로나 이관 목록 파일을 기준으로 한 상대 경로를 사용합니다.

## 저장 전 점검과 백업을 실행합니다

아래 경로는 운영 환경에 맞춰 바꿉니다. 배포한 저장소 루트에서 `--db`로 기존 DB를 지정합니다. 도구가 같은 경로 끝에 `.key`를 붙여 인증 키를 읽습니다. 백업 폴더는 원본 DB 폴더 밖의 새 경로를 사용합니다.

```sh
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 status
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 backup --out /srv/study-private/backups/before-legacy-20261112
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-import --manifest /srv/study-private/legacy/transfer.json --dry-run
```

`--dry-run`은 원본과 DB를 읽고 신규 저장 예정 건수·기존 이관 건수·제외 건수를 JSON으로 출력합니다. `inserted_profiles`는 이때 저장 예정인 프로필 수입니다. DB·인증 키·이관 표를 만들거나 고치지 않습니다. DB 또는 인증 키가 없으면 중단합니다. 실제 저장 때의 보관량은 다른 기록의 증가에 따라 달라질 수 있어 저장 트랜잭션 안에서 다시 검사합니다.

서버에 문제 은행과 `adaptive.py`를 두지 않았다면 프로그램 담당이 같은 프로그램 버전에서 준비한 개념 목록 JSON을 `--catalog /srv/study-private/legacy/catalog.json`으로 지정합니다. 각 문항 ID 아래에 `unit`, `tags`, `kind`, `type`만 담습니다. 파일의 SHA-256과 준비한 프로그램 버전도 비공개 이력에 남깁니다. 이 방식은 서버에 학습 앱이나 모델 패키지를 설치하지 않습니다.

## 이관하고 같은 목록으로 다시 확인합니다

```sh
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-import --manifest /srv/study-private/legacy/transfer.json
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-import --manifest /srv/study-private/legacy/transfer.json --dry-run
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 status
```

목록 전체를 한 트랜잭션으로 저장합니다. 저장한 이벤트를 다시 읽어 내용과 순서를 대조하며 한 사람이라도 충돌하거나 보관량을 넘으면 목록 전체를 취소합니다. 같은 목록과 문항맵으로 재실행하면 이벤트를 추가하지 않습니다. 재확인 결과의 `inserted_profiles`는 0이고 `existing_profiles`는 이관한 프로필 수입니다. `events`는 묶음 표시를 포함한 이벤트 수이고 `answers`는 재시도를 포함한 정오답 기록 수입니다. 모델 입력에 쓰는 첫 시도 행 수와 구분합니다.

원본 바이트·시간대·연결한 문항의 개념 정보·동의 근거가 바뀌면 중단합니다. 같은 원본을 다른 가명값으로 넣거나 기존 수집 계정에 붙이는 작업도 거절합니다. 변경된 프로필의 추가 시도만 이어 붙이는 명령으로 사용하지 않습니다. 도구가 처리하는 입력·DB 오류는 `legacy_transfer_failed` JSON과 종료 코드 1로 알립니다. 문제 은행을 뺀 서버에서는 `--catalog` 경로를 함께 확인하세요.

## 확인하지 못한 과거 정보는 비워 둡니다

`legacy_transfers`는 원본 SHA-256, 이관 식별자, 변환 근거, 동의 근거, 실제 이관 시각과 상태를 나누어 보관합니다. 동의 근거는 연구 이벤트에 복사하지 않습니다. 원본 파일 경로와 계정 이름도 서버의 연구 이벤트에 넣지 않습니다. 정오답 기록에는 원본 해시와 이관 식별자를 남겨 원본과 대조할 수 있습니다.

과거 문항 버전은 `null`이며 개념은 현재 문항맵에서 연결했다는 표시와 해시를 남깁니다. 시간대가 없는 채점 시각에는 목록의 시간대를 가정하고 원래 문자열도 보존합니다. 실제 화면 표시·입력 시각과 희망 직무는 복원하지 않습니다. 원본에 회차 생성 시각이 있을 때만 기존 변환기의 예측 기준 시각으로 사용합니다. 묶음 표시인 `batch_start`의 시각은 채점 시각을 따른 정리용 값이며 실제 문제 표시 시각을 관찰한 값으로 쓰지 않습니다.

시각 없음·현재 문항맵에 없음·건너뛰기는 제외 건수로 남깁니다. 변환할 기록이 없는 프로필이나 거꾸로 흐르는 채점 시각은 저장하지 않습니다. 새 시간이나 과거 문항 버전을 추정해 채우지 않습니다. DB에서 내보낸 이벤트는 기존 `learning_server.starter --input`으로 별도 연구 자료를 만들 수 있습니다. 내보낸 사본과 백업도 철회 처리 목록에 포함합니다.

## 과거 AI 판정은 학습 입력과 나눠 보관합니다

과거 AI 기록에는 문제를 보여준 시각과 문항 버전이 없을 수 있습니다. `legacy-ai-import`는 이 값을 추정하지 않습니다. `pass`·`stuck`·`partial` 판정을 `legacy_answer`로 보관하고, 직접 입력한 답안 본문과 선택지 값은 옮기지 않습니다. 기존 `starter`는 이 보관용 이벤트를 모델 입력에서 제외합니다.

운영자는 위와 같은 동의 근거를 준비하고, Python 이관 계정과 겹치지 않는 별도 UUID를 지정합니다. 비공개 목록 형식은 아래와 같습니다. `archived_at`은 운영자가 이 목록을 만든 보관 작업 시각입니다. 실제 과거 풀이 시각이나 동의 시각으로 쓰지 않으며, 재실행할 때도 바꾸지 않습니다.

```json
{
  "format": 1,
  "archived_at": "2026-11-12T16:00:00+09:00",
  "profiles": [{
    "participant": "4b05ac22-abde-4f55-8ddc-0e057d7a45aa",
    "record": "sources/person-ai/record.json",
    "consent": {
      "confirmed_on": "2026-11-12",
      "evidence_ref": "private-consent-reference",
      "private_server_transfer": true,
      "recommendation_research": true
    }
  }]
}
```

AI 이관도 앞 절의 `status`와 새 경로 백업을 먼저 마칩니다.

```sh
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-ai-import --manifest /srv/study-private/legacy/ai-transfer.json --dry-run
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-ai-import --manifest /srv/study-private/legacy/ai-transfer.json
```

저장 후 같은 목록으로 `legacy-ai-import --dry-run`을 다시 실행해 추가 예정 건수가 0인지 확인하고 같은 DB의 `status`를 확인합니다.

원래 시각·소요 시간 값은 `original_at`·`original_secs`로 보존합니다. 과정·문항 버전·예측 시각이 없으면 미확인으로 남깁니다. 원본 해시와 로그 위치로 출처를 찾을 수 있으며, 같은 목록을 다시 실행해도 중복 저장하지 않습니다. 아래 철회 명령은 AI 이관 계정에도 적용됩니다.

정정 이력이나 중복 시도가 있는 원본은 자동 이관하지 않고 먼저 대조합니다. 재수입 차단은 고정한 가명과 원본 바이트 해시를 기준으로 합니다. 파일을 다시 저장하거나 새 가명을 붙이면 같은 사람인지 자동으로 판별할 수 없습니다. 운영자는 기존 비공개 대응 목록과 철회 기록을 확인하며, 이미 이관한 사람에게 새 가명을 발급해 다시 넣지 않습니다.

## 이관을 되돌리거나 철회를 처리합니다

비공개 목록에서 해당 사람의 `participant`를 확인하고 해당 사유의 명령 하나에 넣습니다. 이관 계정의 이벤트만 지우며 원본 `submissions`와 다른 수집 계정은 고치지 않습니다.

```sh
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-remove --participant fe6dbf8c-c020-42f6-b9cb-6369239455f9 --reason rollback
```

동의를 철회한 사람에게는 다음 명령을 사용합니다.

```sh
python3 -m learning_server --db /srv/study-private/server/learning.sqlite3 legacy-remove --participant fe6dbf8c-c020-42f6-b9cb-6369239455f9 --reason withdrawal
```

되돌리기는 `rolled_back`, 동의 철회는 `withdrawn`으로 남깁니다. 해당 계정을 폐기하고 동의 근거를 DB에서 지웁니다. 가명값·원본 해시·이관 식별자와 제거 상태는 재수입 방지와 사본 식별에 사용합니다. 반복 제거는 삭제 건수 0을 반환하며 철회 상태를 되돌리기 상태로 낮추지 않습니다. 이후 같은 원본이나 가명값으로 다시 이관하면 거절합니다.

이관 계정과 앱의 새 수집 계정은 별개입니다. 앱에서 새 수집 기록을 철회해도 과거 이관 계정까지 자동으로 연결해 지우지는 않습니다. 철회 요청을 받으면 운영자가 비공개 대응 목록에서 해당 이관 가명값을 찾아 위 명령도 실행합니다.

오래된 백업을 복구하면 백업 이후의 철회·되돌리기 요청을 먼저 적용합니다. 운영자가 전달한 연구 사본과 백업을 비공개 대응 목록·원본 해시·이관 식별자로 찾아 처리한 뒤 서비스를 재개합니다. 이 명령은 별도로 전달한 파일과 백업의 삭제까지 완료했다고 보고하지 않습니다.
