# 네 명이 수집 서버를 먼저 사용합니다

프로그램 담당 WaterMinCho가 서버와 개인 초대 파일을 준비합니다. 참가자는 파이썬과 AI 비전 개론에서 각각 수집·전송 여부를 선택합니다. 현재는 운영 준비 단계이며 외부 서버 주소와 실제 참가 결과를 아직 등록하지 않았습니다.

## 외부 무료 호스팅을 고릅니다

2026년 11월 10일에 확인한 조건입니다.

| 서비스 | 기존 서버를 배포할 때 확인한 내용 | 시범 운영 판단 |
|---|---|---|
| PythonAnywhere Beginner | 월 0달러, 웹앱 1개·작업자 1개, 개인 파일 공간 512MiB, HTTPS 지원, 무료 웹앱 만료 기간 1개월 | 기존 WSGI 서버와 SQLite를 연결할 후보입니다. 월별 연장과 파일 백업이 필요합니다. |
| Render Free | 로컬 파일을 재배포·재시작·유휴 종료 때 잃으며 무료 영구 디스크를 제공하지 않습니다. 무료 Postgres도 생성 후 30일에 만료됩니다. | 현재 SQLite 서버의 풀이 보관 장소로 사용하지 않습니다. |

근거는 [PythonAnywhere 요금](https://www.pythonanywhere.com/pricing/), [무료 계정 기능](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [Render 무료 제한](https://render.com/docs/free)입니다. PythonAnywhere의 100 CPU초는 콘솔·작업에 적용하며 웹앱 요청의 실행 한도와 구분합니다. 새 무료 계정에는 예약 작업이 없으므로 자동 백업을 등록했다고 안내하지 않습니다.

PythonAnywhere는 파일을 보존하지만 네트워크 파일 시스템을 사용합니다. 운영사는 [SQLite의 간헐적 잠금과 운영 서비스 사용 제한](https://www.pythonanywhere.com/forums/topic/35474/)을 안내했습니다. 이 후보에서는 네 명의 전송·재전송·복구를 먼저 확인하고, 문제가 반복되면 영구 저장소가 있는 다른 서버나 별도 DB를 검토합니다. 앱은 전송에 실패해도 로컬 기록을 보존합니다. 아직 다른 수강생에게 배포하거나 수집 성능을 측정한 결과는 없습니다.

## 서버 계정에 코드를 준비합니다

계정 생성과 로그인은 운영자가 완료합니다. Beginner 무료 플랜을 선택하며 유료 전환이나 결제 수단 등록을 이 절차에 포함하지 않습니다. 기존 계정에 웹앱이 있다면 덮어쓰지 않습니다.

PythonAnywhere의 Bash 콘솔에서 공개 코드를 받습니다.

```sh
git clone --depth 1 https://github.com/WaterMinCho/programming-study.git
cd programming-study
```

Web 탭에서 새 웹앱의 **Manual configuration**을 고르고 Python 3.12 이상을 선택합니다. 이 서버는 Python 표준 라이브러리로 WSGI 앱을 제공하므로 PythonAnywhere에서는 Waitress나 PyQt를 설치하지 않습니다. [공식 웹앱 설정 안내](https://help.pythonanywhere.com/pages/WebAppBasics)를 따릅니다.

Web 탭의 WSGI 설정 파일에 아래 코드를 넣습니다. 계정 홈은 실행 계정에서 읽으며 데이터는 코드 저장소 밖에 보관합니다.

```python
import os
import sys
from pathlib import Path

project = Path.home() / "programming-study"
sys.path.insert(0, str(project))
os.environ["STUDY_DATA_DB"] = str(Path.home() / ".rokey-collector/data/learning.sqlite3")

from learning_server.wsgi import application
```

저장 후 Web 탭에서 Reload를 누릅니다. Static files에는 데이터·키·초대·백업 폴더를 연결하지 않습니다. 접근 로그와 오류 로그에 답안 본문·인증 헤더를 추가하지 않습니다.

Web 탭에서 실제 HTTPS 주소를 복사합니다. Bash 콘솔에서 아래 명령을 실행하고 주소를 붙여넣습니다.

```sh
read -r -p 'Web 탭의 HTTPS 주소: ' COLLECTOR_URL
python -m learning_server check --url "$COLLECTOR_URL"
python -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" status
```

`check`는 원격 서버 응답과 수집 형식 판을 확인합니다. `/health`는 실제 데이터베이스를 열 수 없으면 503을 반환합니다. `status`는 기존 DB를 읽기 전용으로 검사하며 파일이 없을 때 새 DB나 키를 만들지 않습니다. 가명 구분값·답안·인증 토큰은 상태 결과에 포함하지 않습니다.

## 네 명의 개인 초대를 발급합니다

파이썬과 AI 비전 개론은 서로 다른 가명 구분값을 만듭니다. 한 초대 코드는 한 가명 계정에만 연결하므로 한 사람에게 과목별로 두 개를 전달합니다.

```sh
python -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" pilot --url "$COLLECTOR_URL" --out "$HOME/.rokey-collector/invites/first-pilot"
```

`member-01.txt`부터 `member-04.txt`까지 개인 파일 네 개와 목록을 만듭니다. 각 개인 파일에는 서버 주소와 두 과목의 코드가 있습니다. 코드를 화면이나 명령 로그에 출력하지 않으며 파일을 다시 읽어 확인합니다. 초대는 기본 7일 동안 유효합니다. 기존 출력 폴더를 덮어쓰지 않습니다. 발급만으로 참가자 등록이나 수집 동의가 이루어지지 않습니다.

운영자는 파일마다 수집 목적·서버 보관 장소·보관 기간·삭제 요청 연락 경로를 설명하고 한 사람에게 한 파일만 비공개로 전달합니다. 코드와 파일을 공개 저장소·공용 채널·공유 화면에 올리지 않습니다. 참가자는 [수집 항목과 삭제 범위](LEARNING_DATA.md)를 읽고 참여를 선택합니다.

서버의 `active_accounts`는 사람 수가 아닌 가명 계정 수입니다. 네 명이 두 과목을 모두 연결하면 계정은 8개이며 이를 참가자 8명으로 세지 않습니다.

## 참가자가 저장과 재전송을 확인합니다

1. 프로그램을 최신 버전으로 업데이트하고 과목 홈의 [학습 데이터]를 엽니다.
2. 수집 항목을 읽고 참여한다면 [동의하고 수집 시작]을 누릅니다. 희망 직무는 선택하지 않아도 됩니다.
3. 문제에 답하고 채점합니다. 서버 주소와 해당 과목 초대 코드를 입력한 뒤 [동의하고 서버에 보내기]를 누릅니다. 입력 답안 포함은 기본으로 꺼져 있습니다.
4. 같은 기록을 다시 전송해 새로 보낸 수가 0건인지 확인합니다. 접속이 끊겼다면 기록이 로컬에 남는지 확인하고 연결 후 다시 전송합니다.
5. 다른 과목에서도 해당 과목의 별도 초대 코드로 같은 절차를 확인합니다.

삭제를 시험할 때는 [서버의 내 풀이 삭제]를 누릅니다. 해당 과목의 서버 기록과 업로드 인증을 없애며 로컬 진도·풀이 제출은 유지합니다. 재참여하려면 로컬 추가 데이터도 삭제한 뒤 새 초대를 받습니다. 삭제와 재참여는 참가자가 직접 선택합니다.

운영자는 `status`의 과목별 건수와 참가자 화면의 저장 확인을 대조합니다. 마지막으로 입력 답안을 제외한 내보내기 파일을 만들어 행 수와 해시를 확인합니다. 이 과정을 합성 계정으로 검사한 결과와 실제 네 명이 사용한 결과는 따로 기록합니다.

## 데이터베이스와 인증 키를 함께 백업합니다

```sh
python -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" backup --out "$HOME/.rokey-collector/backups/before-pilot"
```

SQLite의 [연결 백업 기능](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)으로 일관된 DB 사본을 만듭니다. DB와 `.key` 파일을 함께 저장하고 무결성·건수·SHA-256을 다시 확인합니다. 기존 폴더를 덮어쓰지 않으며 원본 데이터 폴더 안에는 만들지 않습니다. POSIX에서는 새 출력 폴더를 700, 파일을 600 권한으로 만듭니다.

백업에는 입력 답안과 인증 키가 포함될 수 있습니다. 호스팅 계정의 비공개 Files에서 운영자 기기로 내려받아 보호합니다. 별도 기기의 사본을 확인하기 전까지 같은 서버 안의 백업만으로 장애에 대비했다고 기록하지 않습니다. 전송·삭제 확인 뒤와 코드 갱신 전에 새 이름으로 백업하고, 사용을 시작할 때 Web 탭의 만료일도 확인해 연장합니다.

## 복구한 사본을 확인한 뒤 다시 엽니다

```sh
python -m learning_server restore --from "$HOME/.rokey-collector/backups/before-pilot" --out "$HOME/.rokey-collector/restored/first-check"
python -m learning_server --db "$HOME/.rokey-collector/restored/first-check/learning.sqlite3" status
```

복구는 해시가 맞는 DB·키를 새 폴더에 복사합니다. 운영 DB를 덮어쓰거나 서버를 자동으로 재시작하지 않습니다. 백업을 만든 뒤 접수한 삭제·철회 요청이 있으면 운영자는 서버를 다시 열기 전에 그 요청을 복구 사본에도 적용합니다. 백업에 없던 철회 사실을 프로그램이 추정하지 않습니다.

복구 사본의 확인을 마치면 Web 탭에서 앱을 중지하고 WSGI 설정의 DB 경로를 복구한 파일로 바꿉니다. 다시 연 뒤 `check`와 `status`를 확인합니다. 기존 초대 재시도와 철회한 인증 거절도 확인한 뒤 참가자에게 사용을 재개하도록 안내합니다.

## 직접 실행하는 장비에서 운영 서버를 확인합니다

PythonAnywhere 외의 장비에서는 운영 패키지를 설치하고 Waitress로 실행할 수 있습니다.

```sh
python -m pip install -r learning_server/requirements.txt
python -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" serve --production
```

기본은 이 기기의 `127.0.0.1:8765`에서만 받습니다. 외부 참가자가 쓰려면 별도의 HTTPS 연결이 필요합니다. 개발용 `serve`와 운영용 `serve --production`을 구분하며 두 실행만으로 외부 접속 주소가 생기지 않습니다.
