# 프로젝트 폴더와 차시별 복습 자료

<a id="프로그램-안내-문서를-찾습니다"></a>

[수강생 학습 시작](LEARNER_START.md) · [스터디원 모델 개발 시작](STUDY_START.md) · [전체 안내 목록](GUIDE_INDEX.md)

[처음 안내로 돌아갑니다](../README.md)

처음 설치할 때는 [프로그램 준비](../gui/README.md#처음-설치할-때)를 읽습니다. 모델 스터디에 참여하는 팀원은 [각자 fork에서 첫 PR까지](LEARNING_WORKFLOW.md)를 먼저 따라 합니다.

## 폴더와 차시별 복습 자료

파이썬 회차에는 여러 차시의 문제가 섞여 나옵니다. 한 차시만 복습하려면 [3차시 조건문](../problems/s03/README.md)처럼 해당 차시 폴더의 README를 여세요. 개념 정리와 시험에서 헷갈리는 부분이 적혀 있습니다.

| 폴더 | 내용 |
| --- | --- |
| `problems/s01` ~ `s21` | 1~21차시. 파이썬 소개, 프로그래밍 기초, 조건문, 리스트와 딕셔너리, 반복문, 함수 1·2, 자료구조와 알고리즘, 클래스 1·2, GUI, 파일 처리, 예외·문자열·람다·map, 정규표현식, 고급 함수, 알고리즘 1·2, Pandas·NumPy·Matplotlib, statsmodels·scikit-learn·SciPy, Seaborn·OpenCV, 파이썬 활용 심화. 18~20차시는 패키지를 다루는 차시라 객관식과 단답만 있습니다. 20차시의 캐스케이드 분류기 이후와 21차시는 시험 범위가 아니라서 회차에 나오지 않습니다 |
| `problems/m1`, `m2`, `m3` | 모의고사 1회, 2회, 3회. 각각 120분, 100점 |
| `problems/c1`, `c2` | 코딩테스트 연습 Lv.1, Lv.2 (선택) |
| `dungeons/` | 알고리즘 여행에서 공개한 던전은 `d01`, `d02`, `d03`입니다. 각 폴더에 지문과 소개가 있고, 숨은 테스트·힌트·해설·기준 풀이는 `sealed.json`에 묶여 있습니다. |
| `journey/` | 알고리즘 여행의 코드 실행기와 채점기 |
| `gui/` | 과목 선택, 학습·풀이 화면, 화면 설정과 수집 동의 창 |
| `ai/`, `aiprep/` | AI 개론·응용의 학습 자료와 문항, 학습·연습·채점 기능 |
| `career/` | 커리어 메뉴의 세부 직무와 영상·논문 목록입니다. 화면에서 찾는 방법은 [커리어 안내](career/README.md)에 있습니다. |
| `learning_data/` | 파이썬·AI의 공통 기록, 수집 동의·철회, 전송과 비공개 파일 제출 |
| `learning_server/` | 비공개 수집 API, 파일 보관, 공통 학습 자료 준비와 운영 명령 |
| `experiments/본인GitHubID/` | 스터디원이 직접 만드는 모델 코드·테스트·실험 설명 |
| `web/missions`, `web/drills`, `web/learn` | 웹 면접 준비의 미션, 꼬리 질문 주제, 학습 노트. 읽기 안내(`brief.md`), 템플릿 코드(`app/`), 학습 노트(`page.md`)는 공개 파일이고, 단계 요구, 검사, 해설, 사슬 본문은 미션과 주제마다 `sealed.json` 하나에 묶여 있습니다. 목록과 권장 순서는 `web/index.json` 에 있고, 아직 출제되지 않은 것은 폴더가 없습니다 |
| `webprep/` | 웹 면접 준비의 서비스, 검사 실행, 기록, 복습 일정, 터미널 명령 |
| `package.json`, `package-lock.json` | 웹 미션 검사 도구의 버전과 의존성입니다. 현재 배포본에서는 웹 면접 준비 메뉴와 터미널 명령을 제공하지 않습니다. |
| `submissions/<내 ID>` | 내 회차, 풀이, 기록(`profile.json`) |
| `submissions/<내 ID>/journey` | 알고리즘 여행의 내 코드(`d01/p1.py`, `d01/p1.js`), 내가 추가한 테스트 케이스(`d01/p1.cases.json`), 기록(`progress.json`) |
| `submissions/<내 ID>/web` | 웹 면접 준비의 내 미션 코드(`missions/w03/`)와 기록(`record.json`) |
| `docs` | [GIT_GUIDE](GIT_GUIDE.md)(프로그램 업데이트와 개발 PR), [CRITERIA](CRITERIA.md)(판정 규칙), [AUTHORING](AUTHORING.md)(스터디장용 운영 메모와 출제 규격), [JOURNEY_AUTHORING](JOURNEY_AUTHORING.md)(알고리즘 여행 출제 규격과 교차 검증), [WEB_AUTHORING](WEB_AUTHORING.md)(웹 면접 준비 출제 규격과 교차 검증) |
