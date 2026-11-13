# Node.js 설치와 과목별 터미널 명령

<a id="실행-도구와-터미널-명령을-확인합니다"></a>

[처음 안내로 돌아갑니다](../README.md)

이 문서의 터미널 명령은 `study.py`가 있는 `programming-study` 폴더에서 입력합니다. 문서가 있는 하위 폴더에서 실행하지 않습니다.

웹 면접 준비의 화면과 명령은 현재 진입을 중지했습니다. 아래 `web` 명령은 기능을 다시 연 뒤 사용하는 기존 안내입니다. [기능 상태](../web/README.md)를 먼저 확인합니다.

## Node.js 설치

알고리즘 여행에서 JavaScript를 선택하면 Node.js 20 이상을 사용합니다. 웹 면접 준비의 라이브 코딩 미션을 다시 열면 그 미션에는 22.12 이상이 필요합니다.

1. 터미널에서 `node --version`을 입력합니다. 이미 20 이상이 설치돼 있다면 알고리즘 여행에서 사용할 수 있습니다.
2. 새로 설치한다면 [Node.js 공식 다운로드](https://nodejs.org/en/download)에서 **LTS**로 표시된 지원 버전을 고릅니다. Windows는 `.msi`, macOS는 `.pkg` 설치 파일로 설치합니다.
3. 알고리즘 여행에서 [JavaScript]를 누릅니다. 프로그램을 켜 둔 채로 설치했다면 'Node.js 찾기' 창의 [다시 찾기]를 누르거나 프로그램을 껐다 켭니다.

설치 뒤에도 Node.js를 찾지 못하면 같은 창의 [직접 고르기]로 실행 파일을 지정합니다. 위치는 터미널에서 `where node`(macOS는 `which node`)로 확인합니다. 선택한 위치는 이 컴퓨터에 저장됩니다.

## 터미널 명령

평소에는 프로그램 창에서 학습하고 채점하면 됩니다. 아래 명령은 터미널에서 파이썬 스터디를 사용할 때의 참고입니다. Windows에서 `python`이 없으면 `py`, macOS는 `python3`로 바꿉니다.

창 없이 풀려면 `go` 를 씁니다. 답은 `submissions/<내 ID>/<회차>/` 의 `quiz.py` 와 `.py` 파일에 직접 적습니다. 알고리즘 여행은 창에서 풉니다. `go`, `me`, `start`, `grade`에서 다른 풀이 ID를 지정하려면 `--user <ID>`를 붙입니다.

`go` 는 채점 여부를 묻습니다. 동의하면 적어 둔 답을 이 컴퓨터에서 채점하고 문항별 첫 시도를 기록합니다. 화면에서 풀던 회차에 쓰면 쓰다 만 답까지 기록되므로, 화면으로 풀 때는 화면의 [회차 제출]만 씁니다. 터미널 모드는 빈 문항을 오답으로 넘기지 않아서, 모든 문항에 답을 적어야 회차가 끝나고 다음 회차가 나옵니다.

| 명령                             | 하는 일                                                                            |
| -------------------------------- | ---------------------------------------------------------------------------------- |
| `python study.py`                | 창 열기. 진행 상황과 오류가 이 터미널에 나옵니다                                   |
| `python study.py update`         | 새 버전 확인과 업데이트 적용 (창이 열리지 않을 때)                                       |
| `python study.py go`             | 다음 할 일 이어 가기 (진단, 풀기, 채점, 다음 회차)                                 |
| `python study.py me`             | 단원별 숙달도와 약한 개념                                                          |
| `python study.py explain s03_Q4` | 정답과 해설                                                                        |
| `python study.py grade r02`      | 2회차(`r02`)의 작성한 답 채점                                                             |
| `python study.py start m1`       | 실전 모의고사(120분). 채점은 `grade m1`. 2회는 `m2`, 3회는 `m3`                    |
| `python study.py start c1`       | 코딩테스트 연습 Lv.1. 채점은 `grade c1`. Lv.2 는 `c2`                              |

<details>
<summary>현재 진입을 중지한 웹 면접 준비의 명령 펼쳐보기</summary>

기능을 다시 연 뒤 사용하는 참고입니다. 현재 배포본에서는 실행되지 않습니다.

| 명령 | 하는 일 |
|---|---|
| `python study.py web status`     | 웹 면접 준비 현황: Node.js 와 검사 도구, 미션·사슬·학습 노트, 오늘 복습, 다음 추천 |
| `python study.py web install`    | 미션 검사 도구 설치 (처음 한 번, 인터넷 필요). 지우기는 `web uninstall`            |
| `python study.py web get w03`    | 미션 코드를 내 폴더로 복사하고 읽기 시간 시작. 처음부터 다시 하려면 `--again`      |
| `python study.py web start w03`  | 실전 시작. 0단계(코드 설명)가 열립니다                                             |
| `python study.py web check w03`  | 0단계면 점검 항목 표시, 그 뒤는 단계 검사                                          |
| `python study.py web answer w03` | 통과 뒤 질문에 답하지 못하고 넘어갔으면 그 질문에 다시 답하기                      |
| `python study.py web hint w03`   | 면접관 힌트 듣기                                                                   |
| `python study.py web skip w03`   | 목표 시간이 지난 단계 넘어가기                                                     |
| `python study.py web finish w03` | 미션 끝내기: 해설, 모범 답안 비교, 스스로 점검                                     |
| `python study.py web dev w03`    | 미션 폴더에서 `npm run dev` 와 같은 화면 서버 띄우기, Ctrl+C 로 끄기               |
| `python study.py web test w03`   | 미션 폴더에서 `npm test` 와 같은 테스트 돌리기                                     |
| `python study.py web drill 3-A`  | 꼬리 질문 사슬 풀기. 사슬을 비우면 오늘 복습의 첫 사슬                             |
| `python study.py web show l20`   | 학습 노트 읽기                                                                     |

</details>
