<a id="운영자-맥으로-수집-서버를-백업합니다"></a>

# 운영자 맥으로 수집 서버 백업하기

일반 수강생과 모델 개발 팀원은 이 설정이 필요하지 않습니다. 운영자가 DB와 인증 키를 함께 보관하고 복구할 때 사용합니다.

PythonAnywhere 무료 계정에는 예약 작업이 없습니다. 이 도구는 운영자 맥에서 공식 API로 전용 Bash 콘솔에 온라인 SQLite 백업 명령을 보냅니다. 백업 DB·인증 키·목록을 내려받고 SHA-256·DB 무결성·등록 및 기록 수를 다시 확인합니다. 콘솔이 꺼져 있을 때만 운영 DB 파일을 파일 API로 직접 받습니다. 이때는 저널 파일이 없는지 앞뒤로 확인하고, DB를 두 번 받아 SHA-256이 같을 때만 그 파일을 사용합니다. 인증 키도 앞뒤로 받아 비교합니다. 받은 파일은 맥에서 SQLite 백업 API로 다시 복사한 뒤 같은 방법으로 검사합니다. 쓰는 중인 파일을 받는 방법이라 콘솔 백업보다 위험이 큽니다. 받는 동안 진행되다 취소된 쓰기가 DB 파일에 남아 있으면 커밋된 적 없는 상태가 검사를 통과한 사본으로 남을 수 있습니다. 파일 API가 옛 내용을 두 번 똑같이 돌려주면 그것도 알아채지 못합니다. 콘솔을 다시 열면 콘솔 백업으로 돌아갑니다.

<a id="연결-전에-권한을-확인합니다"></a>

## 연결 전에 권한 확인하기

PythonAnywhere API 토큰은 백업 전용으로 권한을 좁힐 수 없습니다. 계정 파일과 콘솔에 접근할 수 있으므로 운영자만 사용하고 공개 저장소·GitHub Actions·채팅·로그에 넣지 않습니다. 새 토큰 발급과 보관을 승인한 뒤 연결합니다. [공식 API 안내](https://help.pythonanywhere.com/pages/API/)를 기준으로 2026년 11월 12일 확인했습니다.

API로 콘솔 번호를 만들기만 해서는 프로세스가 시작되지 않습니다. 운영자가 웹 화면에서 별도 Bash 콘솔을 열고, 그 번호를 백업 전용으로 지정합니다. 다른 작업을 입력하는 콘솔과 함께 쓰지 않습니다. 콘솔이 종료되면 API가 HTTP 412를 돌려주고, 도구는 위의 직접 받기로 백업합니다. 이 동안에는 서버 용량을 재지 않고 서버의 이전 자동 사본도 지우지 않으므로 운영자가 콘솔을 다시 열어야 합니다. 인증 실패(401), 요청 제한(429), 서버 오류(5xx), 연결 실패, 응답이 중간에 끊긴 경우는 직접 받기로 넘어가지 않고 실패로 남습니다.

<a id="비공개-설정을-준비합니다"></a>

## 비공개 설정 준비하기

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

`status=ok`, `verified=true`와 `backup_created_at`을 확인합니다. `path`는 콘솔로 만든 사본이면 `console`, 직접 받은 사본이면 `files`입니다. `state.json`은 마지막 작업과 용량 결과, 마지막 시도 시각(`last_attempt_at`), 마지막 실패(`last_error`), 연속 실패 횟수(`consecutive_failures`)를 보관합니다. 응답이 끊기면 같은 작업 번호로 다시 확인하고, 불완전한 로컬 사본은 지웁니다. 용량은 계정 폴더의 할당량 추정값이며, 호스팅 사업자의 집계와 다를 수 있습니다.

`problems`에는 아래 경고가 들어갑니다. 백업이 성공했는데 경고가 있으면 `status=warning`과 종료 코드 2를 돌려줍니다. 실패하면 종료 코드 1이고, 실패 줄의 `problems`에는 `stale`, `failed`, `capacity`만 들어갑니다.

- `stale`: 마지막 사본이 만들어진 지 12시간이 넘었습니다. 맥이 밤에 잠들어 정기 실행을 몇 번 건너뛰어도 경고하지 않게 잡은 값입니다.
- `failed`: 두 번 이상 연속으로 실패했습니다. 맥이 잠에서 깬 직후처럼 네트워크가 아직 붙지 않았을 때 한 번 실패할 수 있어 경고하지 않습니다.
- `console_unavailable`: 콘솔이 꺼져 있어 직접 받기로 백업했습니다.
- `capacity`: 마지막으로 잰 서버 용량에 경고가 있습니다.

실패 줄은 `{"status": "error", "code": "offsite_backup_failed", "stage": …, "http": …, "at": …, "problems": […]}` 꼴입니다. `stage`는 실패한 단계(`send_input`, `poll`, `download`, `verify`, `direct_busy`, `direct_unstable`, `direct_wal`, `direct_key`, `config`, `lock`, 그 밖의 오류는 `unknown`), `http`는 호스팅 API가 돌려준 HTTP 코드, `at`은 UTC 시각입니다. 토큰, 응답 본문, 파일 경로는 찍지 않습니다. `direct_busy`는 서버에 `-journal` 파일이 있어 DB에 쓰는 중인 경우이고, `direct_unstable`은 두 번 받은 DB의 SHA-256이 다른 경우입니다. 도구는 한 실행 안에서 5초 간격으로 모두 세 번까지 받아 보고, 세 번 모두 바뀌면 실패로 남깁니다. 다음 정기 실행에서 다시 시도합니다. `direct_wal`은 서버에 `-wal` 파일이 있을 때만 나옵니다. 운영 DB의 저널 방식이 바뀐 것이니 직접 받기를 쓰지 말고 콘솔을 여세요. 파일 확인 요청 자체가 실패하면 `download`와 그 HTTP 코드가 찍힙니다. 받은 파일이 SQLite로 읽히지 않으면 `verify`로 남습니다.

서버에서는 운영자 기기에 보관을 확인한 이전 자동 사본만 다음 실행 때 정리합니다. 수동 백업과 다른 폴더는 건드리지 않습니다. 맥의 사본은 자동으로 지우지 않으므로 운영자가 보관 기간과 공간을 관리합니다. 서버 정리는 콘솔로 만든 마지막 사본(`remote_latest`)을 기준으로 해서, 직접 받은 사본이 끼어도 서버의 이전 자동 사본을 정리합니다. 콘솔에 명령을 보냈지만 완료를 확인하지 못한 작업 번호(`pending`)는 직접 받기에 쓰지 않습니다. 직접 받기는 새 번호로 사본을 만들고, 남겨 둔 번호는 다음 콘솔 백업이 이어받아 서버 정리 기준으로 씁니다.

경고 목록이 바뀌면 맥 알림센터에 한 번 알립니다. 같은 경고가 이어지면 24시간마다 다시 알리고, 백업이 성공하고 경고가 모두 사라지면 "수집 서버 백업이 다시 정상입니다."를 한 번 띄웁니다. 실패한 실행에서는 이 문구를 띄우지 않습니다. 설정·토큰 파일을 읽지 못하는 등 `state.json`을 쓰기 전에 멈추면 실행마다 "수집 서버 백업을 시작하지 못했습니다."를 띄웁니다. 다른 실행이 잠금을 쥐고 있어 멈춘 경우는 알리지 않습니다. `osascript`가 실패로 끝나면 다음 실행에서 다시 띄웁니다. 알림 권한이 꺼져 있으면 실패로 잡히지 않을 수 있습니다. 맥이 꺼져 있거나 알림을 꺼 두었으면 알림이 뜨지 않습니다. Slack·메일로는 보내지 않습니다. 알림을 받으면 정기 실행 로그의 마지막 줄과 `state.json`의 `last_error`를 보고, `http`가 412면 웹 화면에서 전용 콘솔을 다시 엽니다.

정기 실행은 `WorkingDirectory`에 둔 코드 사본을 돌리므로 저장소에 머지해도 바로 바뀌지 않습니다. 이 도구를 고친 뒤에는 아래 순서로 실행 폴더를 바꿉니다.

1. 머지한 main에서 새 실행 폴더를 만들고 `tools/`, `learning_server/`, `learning_data/`를 함께 넣습니다. `learning_server/operations.py`가 `learning_data`와 `learning_server.app`을 불러오므로 `tools/`만 복사하면 실행되지 않습니다.
2. 새 폴더에서 `python3 -c "import tools.collector_backup"`이 오류 없이 끝나는지 확인합니다.
3. 새 폴더에서 앞에 나온 `python3 -m tools.collector_backup` 명령을 한 번 실행해 `path`가 `console`이고 `verified`가 `true`인지 봅니다.
4. plist의 `WorkingDirectory`를 새 폴더로 바꾸고 `launchctl bootout gui/$(id -u) plist파일경로`, `launchctl bootstrap gui/$(id -u) plist파일경로`를 차례로 실행합니다.
5. 다음 정기 실행 로그의 마지막 줄을 확인합니다. 경고가 처음 생겼을 때 맥 화면에 알림이 실제로 뜨는지도 사람이 확인합니다.

되돌릴 때는 `WorkingDirectory`를 옛 폴더로 바꾸고 4번처럼 bootout과 bootstrap을 실행합니다. 옛 코드는 `state.json`에 새로 생긴 키를 읽지 않고 `latest`를 서버 정리 기준으로 씁니다. 그래서 마지막 사본을 직접 받았다면 서버의 `remote_latest` 사본 하나가 지워지지 않고 남을 수 있습니다.

<a id="복구와-철회-요청을-함께-처리합니다"></a>

## 복구와 철회 요청 함께 처리하기

맥에서 받은 사본은 설정의 `destination` 아래에 작업 번호별로 저장합니다. `state.json`의 `latest`가 가리키는 폴더에 `manifest.json`, `learning.sqlite3`, `learning.sqlite3.key`가 있는지 확인합니다. 시범 운영 안내의 `restore --from`에 이 폴더를 지정하고 `--out`에는 아직 없는 새 폴더를 지정합니다. DB와 키는 그 새 폴더 바로 아래에 복구됩니다. [새 폴더에 복구하고 서버를 다시 여는 절차](LEARNING_PILOT.md#복구한-사본을-확인한-뒤-다시-엽니다)를 따릅니다. 동의 철회가 있으면 서버뿐 아니라 자동 사본·수동 백업·전달한 연구 자료도 대조합니다. 오래된 사본을 복구한 뒤에는 백업 이후의 철회 요청을 먼저 적용합니다. 백업 성공은 실제 네 명의 PC 사용이나 장시간 서버 안정성 검사를 대신하지 않습니다.
