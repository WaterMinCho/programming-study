# 커리어 화면의 코드와 연결 계약

[사용 안내](README.md)

## 페이지 콜백과 앱 통합

`gui.career_roadmap.CareerRoadmapPage`와 `gui.career_magazine.CareerMagazinePage`는 특정 창이나 학습 세션에 의존하지 않습니다. `catalog`를 생략하면 `career/data/`의 공개 JSON을 읽습니다. 별도 자료 폴더를 사용할 때는 `career.load_catalog(directory)`의 결과를 전달합니다. 이 모듈은 표준 라이브러리만 사용합니다.

| 연결 지점 | 전달하는 값과 동작 |
| --- | --- |
| 로드맵 `on_back()` | 돌아가기 버튼을 눌렀을 때 호출합니다. |
| 로드맵 `on_select_goal(role_id, coarse_goal_id)` | 명시한 목표 선택 의도를 전달합니다. 저장과 동의·수집 정책은 연결한 쪽에서 처리합니다. |
| 로드맵 `on_magazine()` | 매거진 열기 버튼을 눌렀을 때 호출합니다. |
| 로드맵 `on_video(video_id)` | 관련 영상을 매거진에서 선택하도록 요청합니다. 이 콜백 자체를 자동 재생에 연결하지 않습니다. |
| 두 페이지 `on_source(url)` | 원문 열기 버튼을 눌렀을 때만 HTTPS 주소를 전달합니다. |
| 매거진 `on_video(Video)` | [영상 보기]을 눌렀을 때 호출합니다. `Video.video_id`와 `Video.url`을 사용할 수 있습니다. |
| 매거진 `on_stop()` | 요청한 영상의 정지를 전달합니다. 재생·정지 콜백을 함께 제공해야 재생 버튼을 사용할 수 있습니다. |
| 매거진 `on_paper(Paper)` | [논문 원문 열기]에서 논문 자료를 전달합니다. |
| 매거진 `on_figure(Paper)` | [그림 설명 보기]에서 `figure_description`과 검토 범위를 전달합니다. 실제 도식은 연결한 쪽에서 제공합니다. |

매거진의 `viewer_host`는 재생 위젯을 붙일 영역입니다. `set_viewer(widget)`로 붙이며 그 동작은 URL 설정·재생을 수행하지 않습니다. 뷰어의 배치와 구현은 이 영역을 사용하는 쪽에서 정합니다. `set_playback_state(video_id, state, message="")`에 `playing`, `paused`, `ended`, `error`를 전달하면 현재 요청과 같은 영상에만 반영합니다. 다른 영상의 늦은 응답은 무시합니다. `set_online(False)`는 재생을 막고 정지를 요청하며 `True`나 `None`은 재생 시도를 허용합니다.

`goal_requested`, `video_requested`, `stop_requested`, `paper_requested`, `figure_requested` 신호는 대응 콜백을 호출한 뒤의 관찰용입니다. 같은 동작을 콜백과 신호 양쪽에 연결하면 중복 실행할 수 있으므로 실제 처리에는 한 경로를 사용합니다. 선택·검색·탭과 읽던 위치는 페이지 객체에 유지합니다. 페이지를 다시 만들 때의 영구 저장은 포함하지 않습니다.

논문 자료 형식은 `career/data/papers.schema.json`을 참고합니다. JSON에는 원논문 본문·대본·외부 그림·개인 기록·내부 검토 경로를 넣지 않습니다. 표시용 독립 요약과 출처 URL, 확인일·검토 범위만 보관합니다.

## 기존 기능에 미치는 영향

이 변경은 공개 자료 읽기에서 두 페이지의 탐색·표시·명시한 콜백으로 이어집니다. 기존 학습 기록·과거 목표·수집 API·동의·DB·인증·서버·시작 파일은 변경하지 않습니다. 연결을 되돌릴 때는 페이지 진입을 해제하면 되며 데이터 변환이나 복원이 필요하지 않습니다. 앱 메뉴 연결과 영상 엔진은 `CareerController`와 `VideoDialog`에서 처리합니다. 실제 외부 영상의 재생은 네트워크와 제공자의 재생 허용 조건에도 영향을 받습니다.

관련 검사는 저장소에서 다음 명령으로 실행합니다.

```sh
python -m unittest tests.test_career
QT_QPA_PLATFORM=offscreen python -m unittest tests.test_gui_career
```

화면 검사는 임시 자료와 PyQt6 기본 위젯을 사용합니다. 작은 창·최대 글자·두 테마에서 흐름도의 경계, 목표 선택 요청, 영상 재생·정지 콜백, 탭 왕복과 읽던 위치를 확인합니다. 이 결과는 Windows의 실제 글꼴·창 배율이나 YouTube의 실제 재생을 검증한 결과와 구분합니다.


앱 통합은 `gui/career_controller.py`가 맡습니다. 화면은 처음 열 때 만들며 자료 목록 진입으로 외부 연결·재생 부품 설치를 시작하지 않습니다. 관심 직무는 선택한 자료 버전·시각과 함께 기기 설정에 저장합니다. 기존 여섯 연구 목표와 수집 기록은 바꾸지 않습니다. 세부 직무의 연구 수집은 별도 계약을 정하기 전까지 포함하지 않습니다.

현재 앱은 `VideoDialog`를 별도 창으로 열므로 목록의 인라인 뷰어 자리와 정지 버튼을 숨깁니다. 닫기·다른 화면 이동·오류·종료에서 재생 자원을 해제합니다. 설치는 기존 Qt 패키지를 변경하지 않는 계획만 적용하고 기존 종료·답안 저장 흐름으로 재시작합니다.

Qt WebEngine은 [Qt 공식 배포 안내](https://www.qt.io/blog/qt-webengine-will-release-separate)에 따라 버전 규칙이 달라집니다. 설치 도구는 Qt 6.11까지 같은 minor의 바인딩과 같은 patch의 Qt 엔진을 확인합니다. Qt 6.12.0은 확인한 WebEngine 6.140.0 조합만 허용하며 그 밖의 조합은 자동 설치하지 않습니다. 설치 계획과 설치 후 import를 확인하고 기존 Qt 패키지를 바꾸는 계획은 거절합니다.
