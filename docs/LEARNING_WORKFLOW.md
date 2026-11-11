# 개인 모델을 만들고 함께 검토합니다

작업 상태는 [GitHub 스터디 보드](https://github.com/users/WaterMinCho/projects/2)에서 관리합니다. [Notion 스터디 홈](https://app.notion.com/p/41581d88a7c181ad9ed9e0b5dc4b5a1f)에는 사용법과 배운 점을 모읍니다. 두 곳에 같은 진행 상황을 반복해서 적을 필요는 없습니다. 두 공간은 초대받은 팀원이 함께 사용합니다.

## 자기 미션부터 엽니다

| 담당 | 시작할 이슈 |
|---|---|
| WaterMinCho | [공통 입력과 전달 자료](https://github.com/WaterMinCho/programming-study/issues/118), [제출물 확인과 앱 연결](https://github.com/WaterMinCho/programming-study/issues/122) |
| michae18 | [기본 LSTM](https://github.com/WaterMinCho/programming-study/issues/119) |
| wamangdoo | [Transformer](https://github.com/WaterMinCho/programming-study/issues/120) |
| kimjs85529-a11y | [같은 LSTM에 풀이 간격 추가](https://github.com/WaterMinCho/programming-study/issues/121) |

처음에는 `할 일`에 둡니다. 필요한 입력과 선행 코드가 준비되면 `시작 가능`, 직접 작업하면 `진행`, 실행 방법과 설명을 올리면 `검토`로 옮깁니다. 완료 조건과 확인 결과를 대조한 뒤 `완료`로 바꿉니다. 기한과 추정 점수는 필수가 아닙니다.

큰 미션의 체크 항목을 하나씩 진행합니다. 별도 오류를 발견하면 재현 입력·현재 결과·기대 결과를 이슈에 적고 원래 미션을 연결합니다. 리뷰 질문과 수정 결과는 같은 이슈나 PR에서 이어갑니다.

## 각자의 저장소를 만듭니다

GitHub에서 본인 계정을 소유자로 새 저장소를 만듭니다. 이름은 `learning-lstm`, `learning-transformer`, `learning-gap-lstm`처럼 맡은 모델을 알아볼 수 있게 정합니다. 이 이름은 예시입니다. 공통 프로그램 전체를 복사할 필요는 없습니다.

저장소에는 직접 만든 모델 코드·설정·실험 기록·실행 방법을 둡니다. [실험 기록 양식](LEARNING_EXPERIMENT_TEMPLATE.md)을 복사해 첫 README나 실험 노트로 사용합니다. 학습·예측 코드는 팀원이 직접 구현합니다. 공통 코드를 가져왔다면 원본 주소·고정 커밋·가져온 범위를 밝히고 원본의 LICENSE와 저작권 표시를 보존합니다.

공통 프로그램은 옆 폴더에 따로 받아 [기존 입력 예제](LEARNING_STARTER.md)를 사용합니다. 합성 자료를 새 폴더에 준비하는 명령과 입력 확인 방법도 그 문서에 있습니다. 같은 입력 처리를 별도로 복사해 고치지 않습니다. 공통 코드 커밋과 `features_version: 3`을 기록하고 자료 판을 맞춥니다.

```text
작업 폴더/
  programming-study/    공통 자료 준비와 입력 도구
  learning-lstm/        본인이 만든 모델과 실험 기록
  learning-demo-v3/     공통 도구가 만든 합성 자료
```

실제 풀이·가명 식별자·개별 예측·학습 가중치는 공개 저장소와 Notion에 올리지 않습니다. 자료와 출력 폴더, 모델 파일은 개인 저장소의 `.gitignore`에서 제외합니다. 공개 실행 예시는 합성 자료로 준비합니다.

## 작은 실행과 자기 설명을 남깁니다

입력 하나를 읽고 모양을 설명하는 것부터 시작합니다. 이어서 첫 예측, 작은 학습, 저장한 모델을 새 프로세스에서 불러오는 순서로 진행합니다. 실행 명령·코드 커밋·자료 판·관측 결과를 남기고 아직 실행하지 않은 부분은 구분합니다.

LSTM과 Transformer는 같은 비시간 입력으로 비교합니다. 간격 담당은 공유한 기본 LSTM의 전체 커밋 SHA를 고정하고 직접 더한 시간 입력을 구분합니다. 기본 코드가 준비되기 전에는 간격 값과 시간 미확인 표시를 확인할 수 있습니다. 비교 조건과 세 모델의 그림은 [담당별 미션](LEARNING_MISSIONS.md)에 있습니다.

## 공통 프로젝트에 PR을 연결합니다

개인 저장소에서 구현한 코드를 고정한 뒤 공통 프로젝트의 개발 브랜치나 fork에서 PR을 엽니다. 프로그램이 풀이를 제출하는 `study/<ID>` 브랜치와 구분합니다. PR에는 담당 이슈, 개인 저장소 주소와 전체 커밋 SHA, 직접 구현한 범위, 실행 명령과 확인 결과를 적습니다.

첫 기여는 입력 처리 설명이나 합성 실행 예시여도 됩니다. 앱 연결 단계에서는 개인 모델을 호출하는 연결 코드와 확인 결과를 함께 제출합니다. 저장소 링크만 추가한 일을 모델 통합 완료로 기록하지 않습니다. 기존 예측 출력인 `event_id`·`probability`·`model_version` 형식을 사용합니다.

받은 질문에 반영 여부와 이유를 답하고 다시 확인한 결과를 남깁니다. 팀원 모델 PR은 검토를 거쳐 직접 머지를 판단합니다. 자세한 기준은 [코드 검토 방법](LEARNING_REVIEW.md)을 따릅니다.

## 운영 구성을 고른 근거입니다

[GitHub 공식 Projects 안내](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)의 보드·담당자·이슈 연결을 사용합니다. [Notion 공식 Projects & Tasks 템플릿](https://www.notion.com/templates/notion-projects-and-tasks)은 확인했지만, 작업 상태를 두 번 관리하지 않도록 Notion은 안내와 기록에 사용합니다. [GitHub 동기화 DB](https://www.notion.com/help/github)는 유료 조건이 있어 사용하지 않습니다.

[ML Zoomcamp 프로젝트 안내](https://github.com/DataTalksClub/machine-learning-zoomcamp/blob/9bb19da5777191f0dc0a038f93ef1b429db5a2bb/projects/README.md)의 실행법·재현 코드·문서 기준을 참고했습니다. 각자 코드와 판단, 오류 분석, 피드백 반영을 남깁니다. 합성 실행 점수를 실제 학습자 성능이나 취업 성과로 설명하지 않습니다. 공식 자료는 2026년 11월 11일에 확인했습니다.
