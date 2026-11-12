# 내 담당을 확인하고 첫 PR을 보냅니다

[처음 화면으로](../README.md) · [문제 풀이 프로그램 사용법](LEARNER_START.md)

스터디원은 **자신이 맡은 모델을 구현하고, 선택 이유와 실행 결과를 PR로 설명합니다.** 프로그램·서버·공통 자료 준비와 통합은 WaterMinCho가 맡습니다. 문제를 풀기 위한 사용법은 위의 공통 학습 안내를 이용합니다.

## 담당과 이번 작업을 확인합니다

| 담당 | 만드는 모델 | 첫 작업 |
|---|---|---|
| michae18 | 풀이 순서를 읽는 LSTM | 공통 입력을 읽고 입력·정답의 모양을 본인 말로 설명합니다. |
| wamangdoo | 과거 풀이 관계를 비교하는 Transformer | 같은 입력에서 과거와 빈 자리를 구분하는 방법을 설명합니다. |
| kimjs85529-a11y | 같은 LSTM에 풀이 간격 추가 | 간격을 아는 자리와 모르는 자리의 차이를 설명합니다. |

[담당 이슈와 현재 작업은 GitHub 보드](https://github.com/users/WaterMinCho/projects/2)에서 확인합니다. [프로젝트 구조 그림](ARCHITECTURE.md)으로 내 모델의 입력·출력과 사용할 위치를 보고, [담당별 미션](LEARNING_MISSIONS.md)에서 구체적인 조건을 확인하세요.

## 첫 PR까지 진행합니다

1. [fork·SourceTree 또는 터미널 안내](LEARNING_WORKFLOW.md)를 따라 본인 fork를 받고 작업 브랜치를 만듭니다.
2. [공통 입력 예제](LEARNING_STARTER.md)를 실행합니다. 처음에는 합성 자료를 사용하며 추가 라이브러리나 모델 학습 없이 입력 모양을 확인합니다.
3. `experiments/본인GitHubID/README.md`에 실행한 명령·확인한 모양·자신이 이해한 내용과 질문을 적습니다. 최상위 README를 실습 기록으로 바꾸지 않습니다.
4. Stage → Commit → Push를 한 뒤 본인 fork의 브랜치에서 공통 `main`으로 PR을 만듭니다. 제목은 `docs(model): 공통 입력 확인`처럼 [PR 제목 규칙](PR_GUIDE.md)을 따릅니다.
5. 피드백을 읽고 같은 브랜치에서 고쳐 Push합니다. 새 커밋의 검사와 리뷰가 끝난 뒤 머지 준비 상태를 확인합니다.

첫 입력 확인 PR과 모델 완성은 구분합니다. 이후 학습·평가·저장·불러오기·오류 분석을 본인이 구현하며 [개발 로드맵](LEARNING_ROADMAP.md)의 산출물을 남깁니다. 실제 자료와 개별 예측·모델 가중치는 공개 PR에 올리지 않습니다.

## 사용할 문서를 고릅니다

- [세 모델의 차이와 담당별 미션](LEARNING_MISSIONS.md)
- [공통 입력 판·예제와 실제 자료의 한계](LEARNING_STARTER.md)
- [실험 기록 양식](LEARNING_EXPERIMENT_TEMPLATE.md)
- [코드 검토와 피드백 반영](LEARNING_REVIEW.md) · [Slack 알림](SLACK_NOTIFICATIONS.md)
- [프로그램 설치·화면 사용법](../gui/README.md) · [수집 동의·철회](LEARNING_PRIVACY.md)

일반 수강생의 풀이 파일은 비공개 서버로 받습니다. 모델 코드와 합성 자료의 실행 결과는 GitHub 개발 PR로 검토하며 실제 학습 기록은 운영자가 같은 판으로 준비해 비공개로 전달합니다.
