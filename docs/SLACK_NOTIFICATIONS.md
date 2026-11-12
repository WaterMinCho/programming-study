# PR 검사와 검토 결과를 Slack에서 확인합니다

개발 PR의 검사와 코드 검토가 끝나면 스터디 채널에 결과 카드를 보냅니다. **상태·PR 제목·짧은 결과·PR 보기 링크**를 표시합니다. 검사와 피드백의 자세한 내용은 PR에서 확인합니다. 개별 검사 종료·댓글·리뷰마다 메시지를 보내지 않습니다. 풀이 제출 PR과 `submissions/`만 바꾼 PR은 제외합니다.

팀원 모델 PR은 필수 검사와 현재 코드 판의 검토를 함께 확인합니다. 모두 통과하고 충돌이 없으면 **머지 준비 완료**, 실패나 수정 요청이 남으면 **확인 필요**로 알립니다. 머지는 운영자가 직접 합니다. 코드 검토는 [검토 안내](LEARNING_REVIEW.md)를 따릅니다.

새 커밋의 검사가 진행 중이거나 결과가 아직 등록되지 않았으면 기다립니다. 이전 커밋의 뒤늦은 결과로 알리지 않습니다. 같은 코드 판의 같은 결과는 다시 보내지 않으며 실패를 고쳐 통과한 경우처럼 결과가 달라지면 새 카드를 보냅니다. 제목 수정으로 머지 조건이 바뀐 때도 다시 확인합니다.

## 운영자가 알림 연결을 확인합니다

Slack Incoming Webhooks와 GitHub Actions를 사용합니다. 채널 전용 웹훅은 저장소의 `SLACK_STUDY_WEBHOOK_URL` 비밀 값에 보관합니다. 코드·문서·PR·로그에 주소를 붙이지 않습니다. [웹훅 공식 안내](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)

**Actions → Slack 스터디 알림 → Run workflow**의 기본 실행은 전송 없이 카드만 확인합니다. 실제 전송은 운영자가 dry run을 끄고 실행합니다. 웹훅이 없으면 전송을 보류하고 CI 판정은 유지합니다.

전송 시작을 GitHub 상태에 먼저 기록합니다. Slack 응답을 잃으면 중복 메시지를 피하도록 자동 재전송을 멈춥니다. 운영자는 실행 로그와 채널의 실제 카드를 대조한 뒤 재전송 여부를 정합니다. 웹훅 방식으로 네트워크 장애 중에도 정확히 한 번의 전달을 보장하지는 않습니다.

## 포크 코드와 비밀 값을 분리합니다

알림 작업은 main의 도구로 GitHub에 저장된 PR·검사·리뷰를 다시 조회합니다. 포크 코드를 실행하거나 전달 파일의 명령을 실행하지 않습니다. 제목 검사는 main의 규칙으로 제목 문자열만 확인하고 PR의 head에 결과를 남깁니다. [GitHub 이벤트 안내][events]

포크 실행에 GitHub 승인이 필요하거나 Mac 검토기가 꺼져 있으면 최종 알림도 늦어집니다. 알림을 멈추려면 **Actions → Slack 스터디 알림 → Disable workflow**를 선택합니다.

[events]: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
