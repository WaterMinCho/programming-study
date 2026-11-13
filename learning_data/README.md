# 학습 기록·동의·전송 코드 위치

<a id="학습-기록동의전송-코드를-찾습니다"></a>

[전체 프로젝트 구조](../docs/ARCHITECTURE.md) · [모델 개발 시작](../docs/STUDY_START.md)

파이썬과 AI 개론·응용이 함께 쓰는 학습 데이터 코드를 모았습니다. 기록을 수집하고 동의 상태를 확인한 뒤 비공개 서버로 보냅니다.

| 고칠 기능 | 구현 파일 | 연결되는 곳 |
|---|---|---|
| 추가 학습 기록·문항 버전·내보내기 | [collection.py](collection.py) | 파이썬·AI 서비스 |
| 파이썬 입력 변경·채점 기록 | [python.py](python.py) | `session.py` |
| 수집 동의·철회 | [privacy.py](privacy.py) | `gui/privacy.py`, 서버의 동의 검증 |
| GitHub 기기 본인 확인·팀 통계 조회 | [identity.py](identity.py) | `gui/identity.py`, `learning_server/team.py` |
| 과목별 연구 기록 전송·인증 | [sharing.py](sharing.py) | 수집 서버 API |
| 비공개 풀이 파일 제출 | [submission.py](submission.py) | 제출 화면, `learning_server/submissions.py` |
| 희망 직무·로드맵 버전 | [goals.py](goals.py) | 직무 선택 화면과 공통 자료 준비 |
| 자동 전송 간격 | [sync_schedule.py](sync_schedule.py) | 화면의 전송 예약 |

화면 배치는 `gui/`, 서버 요청 처리와 자료 준비는 `learning_server/`, AI 문제·학습·연습은 `aiprep/`에서 고칩니다. 팀원의 모델 코드는 `experiments/본인GitHubID/`에 둡니다.

<a id="기존-경로로-불러와도-같은-구현을-사용합니다"></a>

## 기존 import 경로와 실제 구현 파일

`aiprep/collection.py`, `aiprep/privacy.py`, `aiprep/sharing.py`, `aiprep/goals.py`, `aiprep/sync_schedule.py`, 루트의 `python_collection.py`와 `submission_api.py`는 기존 import를 위한 연결 파일입니다. 구현을 고칠 때는 위 표의 파일을 수정합니다.

어느 경로로 import해도 같은 코드를 사용합니다. 기존 호출과 테스트도 같은 구현을 검사합니다. 연결 파일은 프로그램 업데이트 경로와 기존 개발 코드의 사용처를 확인한 뒤 정리합니다.

추가 기록은 기존 저장 위치와 SQLite 형식을 사용합니다. 문항 버전 계산에는 실제 구현 파일을 포함하며, 이미 저장한 문항·답안·이벤트는 바꾸지 않습니다. 구체적인 수집 항목은 [학습 데이터 안내](../docs/LEARNING_DATA.md), 전송·철회는 [동의 안내](../docs/LEARNING_PRIVACY.md)에서 확인합니다.
