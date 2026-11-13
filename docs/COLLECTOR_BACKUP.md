# 운영자 맥으로 수집 서버를 백업합니다

일반 수강생과 모델 개발 팀원은 이 설정이 필요하지 않습니다. 운영자가 DB와 인증 키를 함께 보관하고 복구할 때 사용합니다.

PythonAnywhere 무료 계정에는 예약 작업이 없습니다. 이 도구는 운영자 맥에서 공식 API로 전용 Bash 콘솔에 온라인 SQLite 백업 명령을 보냅니다. 백업 DB·인증 키·목록을 내려받고 SHA-256·DB 무결성·등록 및 기록 수를 다시 확인합니다. 실제 운영 DB를 파일 전송 도중 그대로 복사하지 않습니다.

## 연결 전에 권한을 확인합니다

PythonAnywhere API 토큰은 백업 전용으로 권한을 좁힐 수 없습니다. 계정 파일과 콘솔에 접근할 수 있으므로 운영자만 사용하고 공개 저장소·GitHub Actions·채팅·로그에 넣지 않습니다. 새 토큰 발급과 보관을 승인한 뒤 연결합니다. [공식 API 안내](https://help.pythonanywhere.com/pages/API/)를 기준으로 2026년 11월 12일 확인했습니다.

API로 콘솔 번호를 만들기만 해서는 프로세스가 시작되지 않습니다. 운영자가 웹 화면에서 별도 Bash 콘솔을 열고, 그 번호를 백업 전용으로 지정합니다. 다른 작업을 입력하는 콘솔과 함께 쓰지 않습니다. 콘솔이 종료되면 백업은 실패로 남으며 운영자가 다시 열어야 합니다.

## 비공개 설정을 준비합니다

아래는 가상 계정의 설정 예입니다. 실제 설정과 토큰 파일은 저장소 밖에 두고 본인만 읽을 수 있게 권한을 `600`으로 지정합니다. 토큰 파일에는 API 토큰만 넣습니다. 설정 예시의 두 파일을 만든 뒤 `chmod 600 /Users/operator/.rokey-collector/backup/{config.json,api-token}`을 실행하세요. 도구는 두 파일에 그룹·다른 사용자 권한이 남아 있으면 중단합니다.

```json
{
  "host": "www.pythonanywhere.com",
  "username": "example",
  "console": 123,
  "repo": "/home/example/programming-study",
  "db": "/home/example/.rokey-collector/data/learning.sqlite3",
  "remote_root": "/home/example/.rokey-collector/automatic-backup",
  "token_file": "/Users/operator/.rokey-collector/backup/api-token",
  "destination": "/Users/operator/.rokey-collector/backup/snapshots"
}
```

맥에서 아래 명령으로 한 번 실행합니다. 정기 백업에는 운영자가 별도로 준비한 macOS 사용자 LaunchAgent를 사용합니다. 설정 파일의 `ProgramArguments`에는 Python 절대 경로, `-m`, `tools.collector_backup`, `--config`, 설정 파일 절대 경로를 순서대로 넣습니다. `WorkingDirectory`는 해당 모듈을 읽을 수 있는 코드 폴더, `StartInterval`은 14400초입니다. 처음 등록할 때는 준비한 plist 경로로 `launchctl bootstrap gui/$(id -u) plist파일경로`를 실행합니다. 맥이 꺼져 있거나 로그인하지 않은 시간에는 실행되지 않습니다. 코드를 준비한 상태와 자동 실행을 실제 등록한 상태를 구분합니다.

```sh
python3 -m tools.collector_backup --config /Users/operator/.rokey-collector/backup/config.json
```

`status=ok`, `verified=true`와 `backup_created_at`을 확인합니다. `state.json`은 마지막 작업과 용량 결과를 보관합니다. 응답이 끊기면 같은 작업 번호로 다시 확인하고, 불완전한 로컬 사본은 지웁니다. 8시간보다 오래된 백업은 경고로 반환합니다. 용량은 계정 폴더의 할당량 추정값이며, 호스팅 사업자의 집계와 다를 수 있습니다.

서버에서는 운영자 기기에 보관을 확인한 이전 자동 사본만 다음 실행 때 정리합니다. 수동 백업과 다른 폴더는 건드리지 않습니다. 맥의 사본은 자동으로 지우지 않으므로 운영자가 보관 기간과 공간을 관리합니다. 이 도구의 경고 종료 코드와 로그만으로 Slack·메일 알림까지 연결됐다고 안내하지 않습니다.

## 복구와 철회 요청을 함께 처리합니다

맥에서 받은 사본은 설정의 `destination` 아래에 작업 번호별로 저장합니다. `state.json`의 `latest`가 가리키는 폴더에 `manifest.json`, `learning.sqlite3`, `learning.sqlite3.key`가 있는지 확인합니다. 시범 운영 안내의 `restore --from`에 이 폴더를 지정하고 `--out`에는 아직 없는 새 폴더를 지정합니다. DB와 키는 그 새 폴더 바로 아래에 복구됩니다. [새 폴더에 복구하고 서버를 다시 여는 절차](LEARNING_PILOT.md#복구한-사본을-확인한-뒤-다시-엽니다)를 따릅니다. 동의 철회가 있으면 서버뿐 아니라 자동 사본·수동 백업·전달한 연구 자료도 대조합니다. 오래된 사본을 복구한 뒤에는 백업 이후의 철회 요청을 먼저 적용합니다. 백업 성공은 실제 네 명의 PC 사용이나 장시간 서버 안정성 검사를 대신하지 않습니다.
