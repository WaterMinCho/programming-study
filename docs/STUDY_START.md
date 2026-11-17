# 스터디원 가이드 · 담당 모델과 다음 작업

<a id="스터디원-가이드--담당-모델과-첫-pr"></a>

<a id="내-담당을-확인하고-첫-pr을-보냅니다"></a>

[처음 화면으로](../README.md) · [문제 풀이 프로그램 사용법](LEARNER_START.md)

스터디원은 **자신이 맡은 모델을 구현하고 선택 이유와 실행 결과를 PR에 적습니다.** 프로그램·서버·공통 자료 준비와 통합은 WaterMinCho가 맡습니다.

<a id="담당과-이번-작업을-확인합니다"></a>

<a id="팀원별-담당-모델과-첫-작업"></a>

<a id="입력-실습-다음에-만들-코드"></a>

<a id="담당별-현재-제출과-다음-작업"></a>

## 팀원별 끝낸 작업과 다음 할 일

2026년 11월 16일 기준, 공통 저장소에 머지된 코드와 각 담당 이슈를 맞춘 내용입니다. 모델 학습·성능 비교는 아직 확인하지 않았습니다.

| 담당 | 끝낸 작업 | 다음에 할 일 |
|---|---|---|
| [michae18 · #119](https://github.com/WaterMinCho/programming-study/issues/119) | [#226](https://github.com/WaterMinCho/programming-study/pull/226)에서 학습 전 LSTM 예측과 빈 이력·빈 자리 테스트를 반영했습니다. | 기존 `train.py`에 손실 계산·역전파·가중치 갱신을 추가합니다. 검증 때는 가중치를 바꾸지 않는지 확인합니다. |
| [wamangdoo · #120](https://github.com/WaterMinCho/programming-study/issues/120) | [#189](https://github.com/WaterMinCho/programming-study/pull/189)에서 공통 입력과 빈 자리 구분을 설명한 README를 제출했습니다. | 작은 Transformer로 합성 예제 4개의 확률을 계산합니다. 빈 이력·빈 자리 처리를 테스트합니다. |
| [kimjs85529-a11y · #121](https://github.com/WaterMinCho/programming-study/issues/121) | [#235](https://github.com/WaterMinCho/programming-study/pull/235)에서 이번 문제의 개념에 맞는 시간값을 고르는 함수와 테스트를 반영했습니다. | 현재 #226의 LSTM에 고른 시간값과 시간 확인 여부를 연결합니다. 학습 비교는 michae18의 학습 코드가 공유된 뒤 진행합니다. |
| WaterMinCho · [#118](https://github.com/WaterMinCho/programming-study/issues/118) · [#122](https://github.com/WaterMinCho/programming-study/issues/122) | 공통 입력 도구와 비공개 공유 자료, 예측값 비교 도구를 준비했습니다. | 세 분의 실제 자료 수신·입력 검사를 확인하고 비교할 자료·입력 항목을 맞춥니다. 모델 학습·저장·불러오기가 준비되면 공통 평가와 앱 연결을 진행합니다. |

[담당별 구현·확인 방법](LEARNING_MISSIONS.md#이번-pr에-만들고-확인할-것)에서 이번에 고칠 코드와 확인할 결과를 이어서 읽으세요. 합성 자료로 예측값을 출력한 결과와 실제 자료를 읽어 본 결과는 따로 적습니다.

#226·#189·#235는 모두 머지됐습니다. 다음 작업은 fork의 `main`을 갱신한 뒤 새 브랜치에서 시작합니다. 이미 다음 작업용으로 만든 브랜치가 있다면 이어서 사용하세요. 리뷰를 받고 고칠 때는 PR을 올린 그 브랜치에 **Stage → Commit → Push**합니다. [상태별 SourceTree·터미널 안내](LEARNING_WORKFLOW.md#기존-작업에서-어디부터-이어가나요)

[작업 보드](https://github.com/users/WaterMinCho/projects/2/views/1)에서 카드 제목을 눌러 내 이슈를 여세요. 오른쪽 Projects의 Status에서 작업을 시작하면 **진행**, 검토받을 PR이 준비되면 **검토**를 선택합니다. [상태 바꾸는 방법](LEARNING_WORKFLOW.md#1-github-보드에서-내-담당-이슈-열기)을 따라 하세요.

[개발 로드맵](https://github.com/users/WaterMinCho/projects/2/views/4)의 **개발 단계**는 자료 준비·모델 구현 등 이슈의 목적을 나타냅니다. 작업의 진행 여부는 Status로 확인합니다.

[프로젝트 구조 그림](ARCHITECTURE.md)에서 모델이 받을 입력과 돌려줄 값을, [담당별 미션](LEARNING_MISSIONS.md)에서 코드와 실험 조건을 확인합니다. 보드에 404가 뜨면 초대받은 GitHub 계정으로 로그인했는지 확인하세요.

<a id="첫-pr까지-진행합니다"></a>

## 내 fork에서 개발하고 첫 PR 보내기

1. [fork·SourceTree 또는 터미널 안내](LEARNING_WORKFLOW.md)를 따라 본인 fork를 받고 작업 브랜치를 만듭니다.
2. 가상 자료로 시작하려면 Drive의 `3.학습추천모델` 폴더에서 `01_Colab에서_풀이_샘플_열기.ipynb`를 엽니다. 실제 파이썬 샘플과 ZIP은 `ROKEY 모델 스터디 · 공통 학습 자료` 폴더에서 받습니다. [파일별 사용 방법](LEARNING_DATA_ACCESS.md)을 따라 진행하세요.
3. `experiments/본인GitHubID/`에 모델 코드와 테스트를 작성합니다. 그 안의 기존 README에 실행 방법·선택 이유·실행 결과와 질문을 적습니다.
4. Stage → Commit → Push를 한 뒤 본인 fork의 브랜치에서 공통 `main`으로 PR을 만듭니다. [담당 이슈를 PR 본문에 연결](LEARNING_WORKFLOW.md#이슈와-pr-연결)하고 제목은 `feat(model): LSTM 입력과 예측 코드 추가`처럼 [PR 제목 규칙](PR_GUIDE.md)을 따릅니다.
5. 피드백을 읽고 같은 브랜치에서 고쳐 Push합니다. 새 커밋의 검사와 리뷰가 끝난 뒤 머지 준비 상태를 확인합니다.

입력 확인용 문서 PR을 따로 먼저 보낼 필요는 없습니다. 하나의 작업은 코드·테스트·설명을 같은 PR에서 검토받습니다. 구현 중에는 Draft로 공유하고, 자동 코드 리뷰를 받을 때 **Ready for review**로 바꾸세요. 입력 확인과 모델 학습 완료를 구분하고 학습·평가·저장·불러오기·오류 분석을 본인이 구현하며 [개발 로드맵](LEARNING_ROADMAP.md)의 산출물을 남깁니다. 실제 자료와 개별 예측·모델 가중치는 공개 PR에 올리지 않습니다.

모델 PR에서는 바뀐 Python의 구문과 [코드·실험 설명](LEARNING_REVIEW.md)을 확인합니다. 본인 모델 폴더만 바꾸면 프로그램·문제 은행·화면 전체 검사는 실행하지 않습니다. 공통 코드를 함께 바꾸면 그 부분의 검사도 필요합니다. [검사별 기준](PR_GUIDE.md)을 확인하세요.

<a id="사용할-문서를-고릅니다"></a>

## 자료 받기, 모델 실습, 코드 리뷰 안내

- [세 모델의 차이와 담당별 미션](LEARNING_MISSIONS.md)
- [실제 자료 받기·샘플 뽑기·입력 테스트](LEARNING_DATA_ACCESS.md)
- [공통 입력 버전·예제와 실제 자료의 한계](LEARNING_STARTER.md)
- [실험 기록 양식](LEARNING_EXPERIMENT_TEMPLATE.md)
- [코드 검토와 피드백 반영](LEARNING_REVIEW.md) · [Slack 알림](SLACK_NOTIFICATIONS.md)
- [프로그램 설치·화면 사용법](../gui/README.md) · [수집 동의·철회](LEARNING_PRIVACY.md)

일반 수강생의 풀이 파일은 비공개 서버로 받습니다. 모델 코드와 합성 자료의 실행 결과는 GitHub 개발 PR로 검토하며 실제 학습 기록은 운영자가 비공개 공유 폴더에 준비합니다.

<a id="기록을-연구에-사용할-때-확인합니다"></a>

## 실제 풀이 기록의 연구 동의와 공유 범위

새 풀이 기록은 동의 후 비공개 서버로 전송합니다. 팀원에게 서버 관리 권한이나 다른 사람의 원본 답안을 나누지 않습니다. WaterMinCho가 같은 입력 자료 묶음을 비공개로 전달하고 각 팀원은 그 자료로 모델을 비교합니다. 실제 자료와 가중치·개별 예측을 공개 PR에 넣지 않습니다.

과거 기록은 소유자의 동의를 별도로 확인한 뒤 [기존 기록 이관 안내](LEGACY_RECORDS.md)에 따라 보관합니다. AI 기록 원본 보관과 Python 프로필의 연구용 변환은 구분합니다.
