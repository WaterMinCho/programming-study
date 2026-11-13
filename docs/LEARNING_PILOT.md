# 네 명이 수집 서버를 먼저 사용합니다

일반 수강생 배포는 [첫 실행 동의·비공개 자동 전송](LEARNING_PRIVACY.md)과 [비공개 풀이 제출](API_SUBMISSIONS.md)을 사용합니다. 개인 초대 파일은 기본 배포에 필요하지 않습니다. 아래 초대 발급은 운영자가 이전 과목별 등록 API를 시험할 때 사용합니다.

프로그램 담당 WaterMinCho가 운영하는 비공개 수집 서버입니다. 일반 참가자는 프로그램을 실행해 [기기 본인 확인](DEVICE_IDENTITY.md)을 마치고 [학습 데이터 제공 안내]에서 참여 여부를 선택합니다. 동의하면 개인 초대 파일 없이 자동으로 연결하며, [내 정보·데이터]에서 전송 상태와 철회를 관리합니다. 현재 앱에는 개인 초대 코드를 입력하는 화면이 없습니다.

## 배포 후 확인한 내용입니다

Python 3.12 웹앱에서 데이터베이스 연결과 HTTPS 상태 응답을 확인했습니다. HTTP로 접속하면 같은 경로의 HTTPS 주소로 연결됩니다. 데이터·인증 키·초대·백업 폴더는 정적 파일로 공개하지 않았습니다.

파이썬과 AI 비전 개론의 합성 계정 두 개로 실제 HTTPS 전송을 확인했습니다. 같은 기록을 다시 보내도 서버 건수가 늘지 않았습니다. 저장 확인을 놓친 상황을 가정해 클라이언트의 전송 순서를 되돌린 재전송에서도 같은 결과를 확인했습니다. 기본 전송에서 입력 답안을 제외했으며, 삭제 후 인증 거절과 로컬 원본 보존도 확인했습니다. 이 초기 시험의 기록을 삭제했을 때 실제 참가자 계정과 과목별 기록은 0건이었고, 철회한 합성 계정 두 개는 인증 거절 상태였습니다.

개인 초대 없는 등록·저장·재전송·철회를 합성 계정으로 확인했습니다. 동의를 확인한 기존 풀이도 별도로 이관했고, 원본 보존과 재실행의 중복 방지를 대조했습니다. DB와 인증 키를 운영자 기기로 옮겨 SHA-256과 새 폴더 복구를 확인했습니다. 네 명의 실제 PC 동시 사용·장기 운영·전체 수강생 부하는 별도 확인이 필요합니다.

2026년 11월 12일 관리 화면에서 확인한 무료 웹앱 만료일은 **2026년 12월 11일**입니다. 운영자는 그 전에 Web 탭의 **Run until 1 month from today**로 연장합니다. 웹앱 연장은 운영자가 직접 합니다. 운영자 맥에서 실행하는 [외부 백업 절차](COLLECTOR_BACKUP.md)는 호스팅의 예약 작업과 별도로 관리합니다.

## 외부 무료 호스팅을 고릅니다

2026년 11월 10일에 확인한 조건입니다. 이번 네 명의 시범 운영은 PythonAnywhere Beginner로 선택했습니다. 기존 Python 서버와 로컬 SQLite 파일을 유지하며 월 0달러 플랜을 쓸 수 있는 점을 우선했습니다. 실제 계정에서도 무료 플랜을 확인했으며 결제 수단 등록이나 유료 전환 없이 배포했습니다.

| 서비스 | 기존 서버를 배포할 때 확인한 내용 | 시범 운영 판단 |
|---|---|---|
| PythonAnywhere Beginner | 월 0달러, 웹앱 1개·작업자 1개, 개인 파일 공간 512MiB, HTTPS 지원, 무료 웹앱 만료 기간 1개월 | 네 명의 시범 운영에 선택합니다. 월별 연장과 파일 백업이 필요합니다. |
| Render Free | 로컬 파일을 재배포·재시작·유휴 종료 때 잃으며 무료 영구 디스크를 제공하지 않습니다. 무료 Postgres도 생성 후 30일에 만료됩니다. | 현재 SQLite 서버의 풀이 보관 장소로 사용하지 않습니다. |
| Koyeb Free | 무료 인스턴스에는 영구 저장 볼륨을 붙일 수 없습니다. | 현재 SQLite 파일을 보관할 대상으로 선택하지 않습니다. |
| Railway Free | 최초 체험 후 월 1달러 크레딧과 볼륨 최대 0.5GB를 제공합니다. 체험 중 만든 볼륨에는 크레딧 만료 후 삭제 조건도 있습니다. | 계속 무료로 유지할 수 있는지는 실제 사용량과 볼륨 보존 조건을 더 확인해야 하므로 이번에는 선택하지 않습니다. |
| Oracle Always Free | 무료 VM과 블록 저장소를 제공하지만 가입 시 카드 인증이 필요합니다. 유휴 인스턴스 회수와 무료 VM 용량 부족 조건이 있습니다. | 서버·HTTPS를 직접 관리하는 부담까지 고려해 이번 시범 운영에서는 제외합니다. |
| Cloudflare Workers·D1 Free | D1은 전체 5GB, 하루 읽기 500만 행·쓰기 10만 행 한도가 있으며 초과하면 쿼리를 거절합니다. | 현재 파일 DB 코드를 D1 연결로 바꿔야 합니다. 이번에는 기존 서버로 시작하며 별도 이전 작업은 추가하지 않습니다. |

근거는 [PythonAnywhere 요금](https://www.pythonanywhere.com/pricing/), [무료 계정 기능](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [Render 무료 제한](https://render.com/docs/free)입니다. PythonAnywhere의 100 CPU초는 콘솔·작업에 적용하며 웹앱 요청의 실행 한도와 구분합니다. 당시 확인한 새 무료 계정에는 예약 작업이 없었습니다.

추가 비교는 [Koyeb 무료 인스턴스][koyeb-free], [Railway 무료 플랜](https://docs.railway.com/pricing/plans)과 [체험 자료 보존 조건](https://docs.railway.com/pricing/free-trial), [Oracle 무료 자원][oracle-free]과 [가입 조건](https://www.oracle.com/cloud/free/faq/), [D1 무료 한도](https://developers.cloudflare.com/d1/platform/pricing/)를 대조했습니다. D1 연결 변경과 서버 관리 부담은 현재 코드·운영 절차를 대조한 선택 판단입니다. 각 서비스에서 실제 수강생 전송을 시험했다는 뜻은 아닙니다.

PythonAnywhere는 파일을 보존하지만 네트워크 파일 시스템을 사용합니다. 운영사는 [SQLite의 간헐적 잠금과 운영 서비스 사용 제한](https://www.pythonanywhere.com/forums/topic/35474/)을 안내했습니다. 이 후보에서는 네 명의 전송·재전송·복구를 먼저 확인하고, 문제가 반복되면 영구 저장소가 있는 다른 서버나 별도 DB를 검토합니다. 앱은 전송에 실패해도 로컬 기록을 보존합니다. 11월 13일에는 운영 서버에서 합성 클라이언트 30개가 1MiB 파일을 동시에 제출했고, 별도 시험에서 4MiB 파일 한 개를 제출했습니다. 수강생 PC에서 한 달간 사용할 때의 보관량은 [전체 배포 조건](LEARNING_READINESS.md#무료-서버의-운영-한계를-확인합니다)에서 따로 다룹니다.

## 서버 계정에 코드를 준비합니다

계정 생성과 로그인은 운영자가 완료합니다. Beginner 무료 플랜을 선택하며 유료 전환이나 결제 수단 등록을 이 절차에 포함하지 않습니다. 기존 계정에 웹앱이 있다면 덮어쓰지 않습니다.

PythonAnywhere의 Bash 콘솔에서 공개 코드를 받습니다.

```sh
git clone --depth 1 https://github.com/WaterMinCho/programming-study.git
cd programming-study
```

Web 탭에서 새 웹앱의 **Manual configuration**을 고르고 Python 3.12 이상을 선택합니다. 이 서버는 Python 표준 라이브러리로 WSGI 앱을 제공하므로 PythonAnywhere에서는 Waitress나 PyQt를 설치하지 않습니다. [공식 웹앱 설정 안내](https://help.pythonanywhere.com/pages/WebAppBasics)를 따릅니다.

Web 탭의 WSGI 설정 파일에 아래 코드를 넣습니다. 계정 홈은 실행 계정에서 읽으며 서버가 저장소 밖의 DB 상위 폴더를 만듭니다.

```python
import os
import sys
from pathlib import Path

project = Path.home() / "programming-study"
sys.path.insert(0, str(project))
os.environ["STUDY_DATA_DB"] = str(Path.home() / ".rokey-collector/data/learning.sqlite3")

from learning_server.wsgi import application
```

이 예시는 초대 코드로만 새 연구 계정을 등록할 수 있습니다. 일반 수강생의 첫 실행 자동 연결을 열 때는 WSGI 파일의 application import 앞에 `os.environ["STUDY_OPEN_REGISTRATION"] = "1"`을 추가합니다. 현재 학습 앱을 연결할 때는 [기기 본인 확인용 서버 설정](../learning_server/README.md#기기-본인-확인과-팀-통계)도 준비합니다.

저장 후 Web 탭에서 Reload를 누릅니다. Static files에는 데이터·키·초대·백업 폴더를 연결하지 않습니다. 접근 로그와 오류 로그에 답안 본문·인증 헤더를 추가하지 않습니다.

Web 탭에서 실제 HTTPS 주소를 복사합니다. Bash 콘솔에서는 웹앱에서 선택한 Python 버전을 지정합니다. 다음 명령은 Python 3.12를 사용합니다. 주소를 묻는 줄에 Web 탭의 HTTPS 주소를 붙여넣으세요.

```sh
read -r -p 'Web 탭의 HTTPS 주소: ' COLLECTOR_URL
python3.12 -m learning_server check --url "$COLLECTOR_URL"
python3.12 -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" status
```

`check`는 원격 서버 응답과 수집 형식 버전을 확인합니다. `/health`는 실제 데이터베이스를 열 수 없으면 503을 반환합니다. `status`는 기존 DB를 읽기 전용으로 검사하며 파일이 없을 때 새 DB나 키를 만들지 않습니다. 가명 구분값·답안·인증 토큰은 상태 결과에 포함하지 않습니다.

<a id="운영자용-개인-초대를-발급합니다"></a>

## 이전 시범 API의 과목별 초대 발급

이전 시범 클라이언트는 파이썬과 AI의 가명 계정을 따로 등록합니다. 운영자가 이 연결을 시험할 때만 `pilot`으로 과목별 코드를 발급합니다. `class-invites`는 예전 파일 제출 API용으로 사람마다 코드 하나를 만드는 별도 명령입니다. 현재 앱의 비공개 파일 제출은 동의 후 자동 등록하며 이 코드를 쓰지 않습니다.

```sh
python3.12 -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" pilot --url "$COLLECTOR_URL" --out "$HOME/.rokey-collector/invites/first-pilot"
```

`member-01.txt`부터 `member-04.txt`까지 개인 파일 네 개와 목록을 만듭니다. 각 개인 파일에는 서버 주소와 두 과목의 코드가 있습니다. 코드를 화면이나 명령 로그에 출력하지 않으며 파일을 다시 읽어 확인합니다. 초대는 기본 7일 동안 유효합니다. 기존 출력 폴더를 덮어쓰지 않습니다. 초대 발급과 실제 참가자 등록은 구분합니다. 수집 동의는 프로그램 첫 실행에서 별도로 선택합니다. 초대 발급이 동의를 대신하지 않습니다.

이전 시범 클라이언트로 시험할 때 운영자는 해당 참가자에게만 파일을 전달합니다. 클라이언트는 파일의 서버 주소로 `POST /v1/enroll`을 호출할 때 해당 과목의 코드를 `invite`로 보냅니다. 운영자는 수집 목적·서버 보관 장소·보관 기간·삭제 요청 연락 경로를 함께 안내합니다. 코드와 파일을 공개 저장소·공용 채널·공유 화면에 올리지 않습니다. 참가자는 [수집 항목과 삭제 범위](LEARNING_DATA.md)를 읽고 참여를 선택합니다.

네 명이 이 초대로 두 과목을 모두 연결하면 연구용 가명 계정이 8개 생깁니다. `active_accounts`에는 비공개 파일 제출·기존 기록 이관 등 다른 활성 계정도 포함됩니다.

## 참가자가 저장과 재전송을 확인합니다

아래 순서는 자동 등록을 연 서버에 현재 앱으로 연결할 때 사용합니다.

1. 프로그램을 최신 버전으로 실행하고 처음 쓰는 기기에서는 GitHub 계정으로 본인 확인을 마칩니다.
2. [학습 데이터 제공 안내]에서 [학습 데이터 제공 동의 (선택)]와 [비공개 서버 보관 동의 (선택)]를 선택한 뒤 [동의하고 시작]을 누릅니다. 비공개 서버에 보관할 항목과 기간도 확인합니다. 동의하지 않아도 학습과 로컬 채점을 사용할 수 있습니다.
3. 파이썬 또는 AI 개론·응용에서 문제에 답하고 채점합니다. 동의 후의 새 기록만 자동 전송합니다.
4. [내 정보·데이터]에서 전송 결과를 확인합니다. 연결이 끊겨도 로컬 기록을 유지하며 다음 전송 때 다시 시도합니다.
5. 다른 과목에서도 기록과 전송 결과를 확인합니다. 과목마다 가명이 달라 사람 수와 계정 수를 구분합니다.

철회는 참가자가 [내 정보·데이터]의 [동의 철회·비공개 기록 삭제]에서 직접 선택합니다. 모든 수집 과목과 비공개 제출의 삭제 확인을 기다리며 기존 풀이·진도는 유지합니다. 운영자는 과목별 서버 건수와 참가자 화면을 대조하고, 합성 검사와 실제 참가자의 사용 결과를 구분합니다.

## 데이터베이스와 인증 키를 함께 백업합니다

```sh
python3.12 -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" backup --out "$HOME/.rokey-collector/backups/before-pilot"
```

SQLite의 [연결 백업 기능](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)으로 일관된 DB 사본을 만듭니다. DB와 `.key` 파일을 함께 저장하고 무결성·건수·SHA-256을 다시 확인합니다. 기존 폴더를 덮어쓰지 않으며 원본 데이터 폴더 안에는 만들지 않습니다. POSIX에서는 새 출력 폴더를 700, 파일을 600 권한으로 만듭니다.

최신 비공개 제출 파일은 SQLite 안에 압축해 보관하므로 DB 백업에도 들어갑니다. 연구용 내보내기 파일과 이미 전달한 사본은 따로 관리합니다. 호스팅 계정의 비공개 Files에서 운영자 기기로 내려받아 보호합니다. 별도 기기의 사본을 확인하기 전까지 같은 서버 안의 백업만으로 장애에 대비했다고 기록하지 않습니다. 전송·삭제 확인 뒤와 코드 갱신 전에 새 이름으로 백업하고, 사용을 시작할 때 Web 탭의 만료일도 확인해 연장합니다.

## 복구한 사본을 확인한 뒤 다시 엽니다

```sh
python3.12 -m learning_server restore --from "$HOME/.rokey-collector/backups/before-pilot" --out "$HOME/.rokey-collector/restored/first-check"
python3.12 -m learning_server --db "$HOME/.rokey-collector/restored/first-check/learning.sqlite3" status
```

복구는 해시가 맞는 DB·키를 새 폴더에 복사합니다. 운영 DB를 덮어쓰거나 서버를 자동으로 재시작하지 않습니다. 백업을 만든 뒤 접수한 삭제·철회 요청이 있으면 운영자는 서버를 다시 열기 전에 그 요청을 복구 사본에도 적용합니다. 과거 이관 계정은 [이관 철회 명령](LEGACY_RECORDS.md#이관을-되돌리거나-철회를-처리합니다)으로 처리합니다. 앱 수집·파일 제출 계정에는 별도의 운영자용 철회 명령이 없습니다. 백업 이후 요청이 해당 사본에 반영됐는지 확인할 수 없으면 사본을 서비스에 연결하지 않습니다.

복구 사본의 확인을 마치면 Web 탭에서 앱을 중지합니다. 서버에 복구한 DB와 짝이 맞는 키를 함께 두고 WSGI의 `STUDY_DATA_DB`를 그 DB 경로로 바꿉니다. 운영자 맥의 경로는 웹앱에서 읽을 수 없습니다. 다시 연 뒤 `check`와 `status`를 확인합니다. 기존 초대 재시도와 철회한 인증 거절도 확인한 뒤 참가자에게 사용을 재개하도록 안내합니다.

## 직접 실행하는 장비에서 운영 서버를 확인합니다

PythonAnywhere 외의 장비에서는 운영 패키지를 설치하고 Waitress로 실행할 수 있습니다.

```sh
python3.12 -m pip install -r learning_server/requirements.txt
python3.12 -m learning_server --db "$HOME/.rokey-collector/data/learning.sqlite3" serve --production
```

기본은 이 기기의 `127.0.0.1:8765`에서만 받습니다. 외부 참가자가 쓰려면 별도의 HTTPS 연결이 필요합니다. 개발용 `serve`와 운영용 `serve --production`을 구분하며 두 실행만으로 외부 접속 주소가 생기지 않습니다.

[koyeb-free]: https://www.koyeb.com/docs/reference/instances#free-instances

[oracle-free]: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
