# <img src="docs/img/icon.png" width="36" alt=""> 프로그래밍 스터디

파이썬·알고리즘·AI 문제를 풀고, 풀이 기록으로 추천 모델을 만드는 프로젝트입니다. ROKEY 11기 수강생의 자율 학습용이며 아래에서 사용할 안내를 고릅니다.

---

## [문제를 풀고 싶어요 → 학습 시작](docs/LEARNER_START.md)

**처음 코딩을 배우는 분도 여기서 시작하세요.** 설치부터 첫 문제를 푸는 순서까지 안내합니다.

프로그램 받기 → start 파일 실행 → 과목 선택 → 풀이·채점

[**설치하고 첫 문제 풀기**](docs/LEARNER_START.md) · [이미 설치했다면 바로 실행하기](gui/README.md#프로그램을-켜고-id를-입력합니다)

---

## [스터디원이에요 → 모델 개발 시작](docs/STUDY_START.md)

**michae18 · wamangdoo · kimjs85529-a11y는 여기서 시작하세요.** 담당 모델과 이번 할 일, 본인 fork에서 첫 PR을 보내는 순서를 안내합니다.

담당 미션 확인 → fork·작업 브랜치 → 비공개 자료·샘플 확인 → 코드·테스트·PR

[**내 담당과 첫 작업 확인하기**](docs/STUDY_START.md) · [실제 자료 받기·샘플링](docs/LEARNING_DATA_ACCESS.md) · [프로젝트 구조와 팀원 역할](docs/ARCHITECTURE.md)

코드를 고칠 때는 [기능별 폴더 안내](docs/ARCHITECTURE.md#기능별-코드-위치)에서 시작합니다. 공통 기록·동의·전송은 `learning_data/`, 서버는 `learning_server/`, 팀원 모델은 `experiments/본인GitHubID/`에 있습니다.

---

## 설정과 자료를 찾습니다

- [글자 크기·밝고 어두운 테마](gui/README.md#글자-크기와-테마를-바꿉니다) · [새 자료 받기](gui/README.md#새-자료를-받습니다)
- [비공개 풀이 제출](docs/API_SUBMISSIONS.md) · [수집 동의·철회](docs/LEARNING_PRIVACY.md)
- [직무별 학습 로드맵 펼쳐보기](docs/roadmap/README.md#직무별-로드맵)
- [실행·제출 오류 해결](gui/README.md#안-될-때) · [전체 안내 목록](docs/GUIDE_INDEX.md)

## 라이선스

프로그램 코드(`study.py`, `adaptive.py`, `session.py`, `gitflow.py`, `bootstrap.py`, `mdlite.py`, `gui/`, `aiprep/`, `learning_data/`, `learning_server/`, `journey/`, `webprep/`, `tools/`, `tests/`)는 [GPL-3.0](LICENSE)입니다. 화면에 쓰는 PyQt6 가 GPL-3.0 이라 같은 조건을 따릅니다.

`gui/fonts/` 의 글꼴은 SIL OFL 1.1 을 따릅니다. 화면 글꼴은 [나눔고딕](gui/fonts/OFL.txt), 코드 글꼴은 [D2Coding](gui/fonts/OFL-D2Coding.md)입니다.

`problems/`, `dungeons/`, `web/` 의 문제, 해설, 개념 정리, 그림, 미션 템플릿 코드는 이 스터디의 학습 자료이고 GPL 적용 대상이 아닙니다. 다른 곳에 옮겨 쓰려면 스터디장에게 문의해 주세요.

<details>
<summary>기존 안내 주소에서 이어 보기</summary>

<a id="-프로그래밍-스터디"></a>
<a id="프로젝트-전체-구조와-내-담당-보기"></a>
<a id="학습-로드맵"></a>
<a id="시험-정보"></a>
<a id="최초-한번-준비해야할-것"></a>
<a id="켜기와-첫-화면"></a>
<a id="파이썬-스터디-풀기"></a>
<a id="답-적는-법과-채점-기준을-확인합니다"></a>
<a id="알고리즘-여행"></a>
<a id="웹-면접-준비"></a>
<a id="ai-개론응용"></a>
<a id="풀이-기록으로-추천-모델을-만듭니다"></a>
<a id="nodejs-설치"></a>
<a id="풀이-올리기pr와-리뷰"></a>
<a id="문제를-고르는-방식"></a>
<a id="모의고사-보기"></a>
<a id="폴더와-차시별-복습-자료"></a>
<a id="안-될-때"></a>
<a id="터미널-명령"></a>
<a id="라이선스"></a>
<a id="그림-읽는-법"></a>
<a id="여섯-길"></a>
<a id="직무별-로드맵"></a>
<a id="이-프로그램에서-연습할-수-있는-부분"></a>
<a id="그림의-근거"></a>
<a id="답-적는-법과-채점"></a>
<a id="던전-지도"></a>
<a id="언어-고르기"></a>
<a id="문제-화면"></a>
<a id="코드-실행과-채점"></a>
<a id="힌트와-해설"></a>
<a id="생성-입력-캐시"></a>
<a id="기록"></a>
<a id="준비하기"></a>
<a id="라이브-코딩-미션"></a>
<a id="꼬리-질문-사슬"></a>
<a id="학습-노트"></a>
<a id="기록-1"></a>
<a id="ai-비전-개론"></a>
<a id="응용은-입력-준비부터-이어갑니다"></a>
<a id="ai-개론-모의고사"></a>
<a id="학습-단원"></a>
<a id="연습"></a>
<a id="복습-확인"></a>
<a id="오답-노트"></a>
<a id="기록-2"></a>
<a id="창이-열리지-않을-때"></a>
<a id="예전-버전을-받아-뒀거나-문제-받기가-계속-오류로-끝날-때"></a>
<a id="id-를-잘못-넣었을-때"></a>
<a id="제출이-안-될-때"></a>
<a id="알고리즘-여행-줄에-기록을-읽을-수-없다고-나올-때"></a>
<a id="그-밖에-불편하거나-이상할-때"></a>

[전체 안내 목록](docs/GUIDE_INDEX.md)에서 이전 항목을 찾습니다.

</details>
