# Slack의 PR 검사·리뷰 알림

<a id="pr-검사와-검토-결과를-slack에서-확인합니다"></a>

개발 PR의 검사와 코드 검토가 끝나면 스터디 채널에 결과 카드를 보냅니다. **상태·PR 제목·짧은 결과·PR 보기 링크**를 표시합니다. 검사와 피드백의 자세한 내용은 PR에서 확인합니다. 개별 검사 종료·댓글·리뷰마다 메시지를 보내지 않습니다. 닫힌 PR·Draft·풀이 제출 PR과 `submissions/`만 바꾼 PR은 제외합니다.

팀원 모델 PR은 필수 검사와 현재 커밋의 검토를 함께 확인합니다. 모두 통과하고 충돌이 없으면 **머지 준비 완료**, 실패나 수정 요청이 남으면 **확인 필요**로 알립니다. 머지는 운영자가 직접 합니다. 코드 검토는 [검토 안내](LEARNING_REVIEW.md)를 따릅니다.

새 커밋의 검사가 진행 중이거나 결과가 아직 등록되지 않았으면 기다립니다. 이전 커밋의 뒤늦은 결과로 알리지 않습니다. 같은 커밋의 같은 결과는 다시 보내지 않으며 실패를 고쳐 통과한 경우처럼 결과가 달라지면 새 카드를 보냅니다. 제목 수정으로 머지 조건이 바뀐 때도 다시 확인합니다.

<a id="하루의-pr-결과를-스레드에-모읍니다"></a>

## 오늘의 PR 스레드와 상태 알림

일별 스레드 모드를 켜면 한국 시간으로 그날 첫 알림이 있을 때 `2026-11-12 오늘의 PR`처럼 상위 글을 만듭니다. 이후 결과는 같은 글의 답글로 모읍니다. 날짜가 바뀐 뒤 첫 알림이 오면 새 글을 만들고 알림이 없는 날에는 글을 만들지 않습니다. 답글은 채널 본문에 다시 게시하지 않습니다.

상위 글 번호는 고정한 Git 커밋의 상태 기록에 저장해 실행이 끝나도 재사용합니다. 토큰과 메시지 본문은 상태 기록에 넣지 않습니다. 상위 글을 만드는 중 응답을 잃으면 새 글을 반복 생성하지 않고 전송을 보류합니다. 이때는 운영자가 Slack에 실제 글이 올라왔는지 확인하고 저장한 글 번호를 복구합니다.

<a id="운영자가-알림-연결을-확인합니다"></a>

## 운영자용 Slack 알림 설정

GitHub Actions에서 Slack 알림을 보냅니다. 기본 모드의 채널 전용 웹훅은 저장소의 `SLACK_STUDY_WEBHOOK_URL` 비밀 값에 보관합니다. 코드·문서·PR·로그에 주소를 붙이지 않습니다. [웹훅 공식 안내](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)

일별 스레드는 기존 Slack 앱의 메시지 전송 권한 `chat:write`와 해당 채널 참여가 필요합니다. 채널 기록을 읽는 권한은 요청하지 않습니다. [메시지 전송 API](https://docs.slack.dev/reference/methods/chat.postMessage/)로 받은 글 번호를 저장하고 답글의 `thread_ts`로 사용합니다.

연결을 준비할 때 GitHub 저장소의 **Settings → Secrets and variables → Actions**에서 다음 값을 설정합니다. 봇 연결을 마치고 활성화하기 전까지 기존 웹훅 알림을 유지합니다.

| 위치 | 이름 | 값 |
|---|---|---|
| Secrets | `SLACK_STUDY_BOT_TOKEN` | 해당 Slack 앱의 Bot User OAuth Token |
| Variables | `SLACK_STUDY_CHANNEL_ID` | 스터디 채널 ID |
| Variables | `SLACK_STUDY_THREAD_ANCHOR` | 스레드 번호를 보관할 고정 커밋의 전체 SHA |
| Variables | `SLACK_STUDY_DAILY_THREADS` | 일별 스레드를 켤 때 `1`, 기존 웹훅 모드는 `0` |

고정 커밋은 `git rev-list --max-parents=0 origin/main`으로 확인한 첫 커밋을 사용합니다. 날짜마다 상태 이름을 나눠 같은 커밋에 저장합니다. 봇 토큰과 전송 채널 설정이 맞지 않으면 전송을 멈추며 채널 본문으로 대신 게시하지 않습니다.

<details>
<summary>상위 글 생성 중 응답을 잃었을 때 복구합니다</summary>

스터디 채널에서 해당 날짜의 상위 글이 있는지 확인합니다. 글이 있으면 [메시지 링크 복사]로 주소를 확인합니다. 주소 끝의 `p1794490000000001`은 마지막 여섯 자리 앞에 점을 넣어 `1794490000.000001`로 바꿉니다. 이 값이 상위 글의 `ts`입니다.

아래 명령의 `고정커밋SHA`와 날짜를 실제 설정으로 바꿉니다. `context`는 `스터디 PR 스레드/날짜/채널 ID의 SHA-256 앞 12자리` 형식이며 조회 결과의 값을 복사합니다.

```bash
gh api repos/WaterMinCho/programming-study/commits/고정커밋SHA/statuses --jq '.[] | select(.context | startswith("스터디 PR 스레드/2026-11-12/")) | {context, description}'
gh api --method POST repos/WaterMinCho/programming-study/statuses/고정커밋SHA -f state=success -f context='조회한 context 값' -f description='ready:1794490000.000001'
```

상위 글이 없다는 것을 확인했다면 두 번째 명령의 description을 `failed`로 바꿔 재생성을 허용합니다. 실제 글과 날짜·채널을 대조하기 전에는 기록을 바꾸지 않습니다.

보류된 PR의 알림은 별도로 확인합니다. 해당 head의 `스터디 알림 기록`에 `sending:KEY`가 남아 있으면 Slack 답글과 실행 로그를 대조합니다. 답글을 보내기 전에 멈췄다는 것이 확인된 경우에만 아래처럼 `failed:KEY`를 추가하고 알림 워크플로를 다시 실행합니다. `PR_HEAD_SHA`와 `KEY`는 실제 조회 값으로 바꿉니다.

```bash
gh api repos/WaterMinCho/programming-study/commits/PR_HEAD_SHA/statuses --jq '.[] | select(.context == "스터디 알림 기록") | {context, description}'
gh api --method POST repos/WaterMinCho/programming-study/statuses/PR_HEAD_SHA -f state=success -f context='스터디 알림 기록' -f description='failed:KEY'
```

답글이 이미 도착한 것을 확인했다면 같은 명령의 description을 `sent:KEY`로 바꿔 완료를 기록합니다. 이 경우에는 다시 전송하지 않습니다.

</details>

**Actions → Slack 스터디 알림 → Run workflow**의 기본 실행은 전송 없이 카드만 확인합니다. 실제 전송은 운영자가 dry run을 끄고 실행합니다. 웹훅 모드에서 웹훅이 없으면 전송을 보류하고 CI 판정은 유지합니다. 일별 스레드 모드에서는 봇 토큰과 채널 설정을 사용합니다.

전송 시작을 GitHub 상태에 먼저 기록합니다. Slack 응답을 잃으면 중복 메시지를 피하도록 자동 재전송을 멈춥니다. 운영자는 실행 로그와 채널의 실제 카드를 대조한 뒤 재전송 여부를 정합니다. 웹훅 방식으로 네트워크 장애 중에도 정확히 한 번의 전달을 보장하지는 않습니다.

## 포크 코드와 비밀 값을 분리합니다

알림 작업은 main의 도구로 GitHub에 저장된 PR·검사·리뷰를 다시 조회합니다. 포크 코드를 실행하거나 전달 파일의 명령을 실행하지 않습니다. 제목 검사는 main의 규칙으로 제목 문자열만 확인하고 PR의 head에 결과를 남깁니다. [GitHub 이벤트 안내][events]

포크 실행에 GitHub 승인이 필요하거나 Mac 검토기가 꺼져 있으면 최종 알림도 늦어집니다. 알림을 멈추려면 **Actions → Slack 스터디 알림 → Disable workflow**를 선택합니다.

[events]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

## 수집 서버 장애와 복구

스터디 채널에 한국 날짜로 ‘금일 서버 상태 모니터링’ 글이 하루에 하나 올라옵니다. 장애가 생기면 복구를 먼저 시도하고, 그날의 글에 장애 번호와 처리 결과를 답글 한 개로 남깁니다. 자정을 넘겨 결과가 나오면 결과를 보낸 날짜의 글에서 확인할 수 있습니다.

복구되지 않았으면 답글에서 어떤 조치를 시도했는지, 어디서 멈췄는지 확인하세요. 이후의 접속 상태는 [수집 서버 상태 페이지](https://rokey-study.betteruptime.com)에서 확인할 수 있습니다. Better Stack은 3분마다 서버 접속을 확인하고, GitHub Actions는 5분 간격으로 장애 목록을 조회합니다. Actions 실행이 밀리면 답글도 늦어질 수 있습니다.

운영자는 저장소 변수 `ROKEY_INCIDENT_RESOURCES`에 운영 모니터 ID를 `{"health":"monitor:123"}` 형식으로 등록합니다. Actions는 팀 전용 읽기 토큰으로 장애를 조회하고 기존 Slack 봇으로 답글을 보냅니다. Slack의 수신 확인이 끊기면 해당 장애 번호의 답글과 전송 기록을 대조한 뒤 재시도 여부를 결정합니다.
