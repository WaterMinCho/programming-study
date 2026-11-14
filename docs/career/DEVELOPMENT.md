# 커리어 화면의 코드와 연결 계약

[사용 안내](README.md)

## 페이지 콜백과 앱 통합

`gui.career_roadmap.CareerRoadmapPage`와 `gui.career_magazine.CareerMagazinePage`는 특정 창이나 학습 세션에 의존하지 않습니다. `catalog`를 생략하면 `career/data/`의 공개 JSON을 읽습니다. 별도 자료 폴더를 사용할 때는 `career.load_catalog(directory)`의 결과를 전달합니다. 목록을 읽는 `career.catalog`는 표준 라이브러리만 사용합니다. 두 화면은 PyQt6로 표시합니다.

| 연결 지점 | 전달하는 값과 동작 |
| --- | --- |
| 로드맵 `on_back()` | 목록에서 [학습 현황]을 누르면 호출합니다. 상세의 [직무 목록]은 같은 페이지 안에서 목록으로 돌아갑니다. |
| 로드맵 `on_select_goal(role_id, coarse_goal_id)` | 명시한 목표 선택 의도를 전달합니다. 저장과 동의·수집 정책은 연결한 쪽에서 처리합니다. |
| 로드맵 `on_magazine()` | 매거진 열기 버튼을 눌렀을 때 호출합니다. |
| 로드맵 `on_video(video_id)` | 관련 영상을 매거진에서 선택하도록 요청합니다. 이 콜백 자체를 자동 재생에 연결하지 않습니다. |
| 두 페이지 `on_source(url)` | 원문 열기 버튼을 눌렀을 때만 HTTPS 주소를 전달합니다. |
| 매거진 `on_video(Video)` | 영상 표지를 클릭하거나 키보드로 활성화하면 호출합니다. `Video.video_id`와 `Video.url`을 사용할 수 있습니다. |
| 매거진 `on_stop()` | 요청한 영상의 정지를 전달합니다. 재생·정지 콜백을 함께 제공해야 표지에서 재생을 요청할 수 있습니다. |
| 매거진 `on_paper(Paper)` | [논문 원문 열기]에서 논문 자료를 전달합니다. |
| 매거진 `on_figure(Paper)` | [그림 설명 보기]에서 `figure_description`과 검토 범위를 전달합니다. 실제 도식은 연결한 쪽에서 제공합니다. |

매거진의 `viewer_host`는 재생 위젯을 붙일 영역입니다. `set_viewer(widget)`로 붙이며 그 동작은 URL 설정·재생을 수행하지 않습니다. 뷰어의 배치와 구현은 이 영역을 사용하는 쪽에서 정합니다. `set_playback_state(video_id, state, message="")`에 `playing`, `paused`, `ended`, `error`를 전달하면 현재 요청과 같은 영상에만 반영합니다. 다른 영상의 늦은 응답은 무시합니다. `set_online(False)`는 재생을 막고 정지를 요청하며 `True`나 `None`은 재생 시도를 허용합니다.

`goal_requested`, `video_requested`, `stop_requested`, `paper_requested`, `figure_requested` 신호는 대응 콜백을 호출한 뒤의 관찰용입니다. 같은 동작을 콜백과 신호 양쪽에 연결하면 중복 실행할 수 있으므로 실제 처리에는 한 경로를 사용합니다. 선택·검색·탭과 읽던 위치는 페이지 객체에 유지합니다. 페이지를 다시 만들 때의 영구 저장은 포함하지 않습니다.

논문 자료 형식은 `career/data/papers.schema.json`을 참고합니다. JSON에는 원논문 본문·대본·외부 그림·개인 기록·내부 검토 경로를 넣지 않습니다. 표시용 독립 요약과 출처 URL, 확인일·검토 범위만 보관합니다.

## 직무 그림과 결과 예시

`gui/career_role_gallery.py`는 기존 직무의 업무 장면·이름·첫 산출물을 목록으로 표시합니다. 카드를 누르면 상세가 열리고 [직무 목록]으로 돌아갈 때 필터와 읽던 위치를 복원합니다. 탐색 중인 직무와 저장한 관심 직무는 별도로 표시합니다. 저장 콜백은 [관심 직무로 저장]을 눌렀을 때만 호출합니다.

상세의 [업무·결과]와 [학습 로드맵]은 같은 직무를 공유합니다. 탭을 바꾸면 해당 내용만 표시하며 직무 자료와 과거 학습 기록은 바꾸지 않습니다. 공개 자료가 비어 있는 상태와 필터 결과가 없는 상태는 구분합니다.

업무 장면은 `career/scenes/<role_id>.webp`에서 읽습니다. `gui/career_scene.py`에서 해당 직무의 질문과 장면을 연결하고, `gui/career_artifact.py`에서 결과 예시를 그립니다. 새 자료를 넣을 때는 같은 직무를 선택한 상태에서 두 보기를 왕복해 질문과 결과가 맞는지 확인하세요. 직무 원문과 수업 범위의 기준은 `career/data/roles.json`입니다.

`gui/career_learning_path.py`는 직무의 `roadmap_nodes` 순서와 수업 범위를 받아 입력·변화의 예시를 그립니다. 주제를 추가하면 예시 설명과 그림이 같은 동작을 가리키는지 확인하세요. 곡선에는 축과 선의 의미를 붙이고, 로봇의 링크·관절과 실행 노드 연결을 구분합니다. 학습 기록이나 진도를 이 그림의 상태로 사용하지 않습니다.

`gui/career_paper_preview.py`는 기존 `PaperDiagram`에서 대표 연산을 보여주는 단계를 재사용합니다. 미리보기 단계와 질문·입력 모양·계산 조건을 함께 선택하세요. 설명 자료를 읽지 못하면 기존 대체 설명을 표시합니다. 미리보기와 [그림 설명 보기]는 같은 논문을 같은 `on_figure`로 전달합니다.

확대 지도는 `tools/roadmap/draw.py`로 생성합니다. 가운데 번호는 단계 순서이며 양쪽 선은 해당 단계의 세부 주제를 연결합니다. 표현만 바꿀 때는 원본 JSON과 목표 식별자를 유지합니다. 각 상자의 글자 폭·높이와 다른 상자와의 겹침은 생성할 때 검사합니다.

## 기존 기능에 미치는 영향

이 변경은 공개 자료 읽기에서 두 페이지의 탐색·표시·명시한 콜백으로 이어집니다. 기존 학습 기록·과거 목표·수집 API·동의·DB·인증·서버·시작 파일은 변경하지 않습니다. 연결을 되돌릴 때는 페이지 진입을 해제하면 되며 데이터 변환이나 복원이 필요하지 않습니다. 앱 메뉴 연결과 영상 엔진은 `CareerController`와 `VideoDialog`에서 처리합니다. 실제 외부 영상의 재생은 네트워크와 제공자의 재생 허용 조건에도 영향을 받습니다.

관련 검사는 저장소에서 다음 명령으로 실행합니다.

```sh
python -m unittest tests.test_career
python -m unittest tests.test_gui_career tests.test_gui_career_navigation tests.test_gui_career_role_gallery
```

화면 검사는 임시 자료와 PyQt6 기본 위젯을 사용합니다. 별도로 Qt 플랫폼을 지정하지 않으면 테스트가 `offscreen`을 선택합니다. 작은 창·최대 글자·두 테마에서 흐름도의 경계, 목표 선택 요청, 영상 재생·정지 콜백, 탭 왕복과 읽던 위치를 확인합니다. 이 결과는 Windows의 실제 글꼴·창 배율이나 YouTube의 실제 재생을 검증한 결과와 구분합니다.


앱 메뉴는 `gui/career_controller.py`에서 연결합니다. 관심 직무는 선택 시각과 자료 버전과 함께 기기에 저장합니다. 영상 표지는 `career/covers/<video_id>.webp`에서 읽습니다. 파일이 없거나 손상되면 같은 크기의 대체 표지를 그립니다. 새 영상을 추가할 때는 16:9 표지와 출처·검토 범위를 함께 확인하세요.

표지를 누르면 `VideoDialog`가 재생을 요청합니다. Qt WebEngine을 사용할 수 없으면 해당 영상의 원본을 기본 브라우저에서 엽니다. 첫 재생을 시도한 뒤 25초 안에 YouTube가 외부 재생을 제한해도 같은 원본을 한 번 엽니다. 앱 내 재생기가 없고 브라우저까지 열리지 않을 때는 재생창에서 [앱 내 재생기 설치]를 선택할 수 있습니다. 앱의 재생창을 닫으면 내장 플레이어를 정리합니다. 브라우저로 연 영상은 브라우저에서 제어합니다. 앱에서 자동 재생을 요청해도 브라우저 정책에 따라 사용자가 플레이어의 재생 버튼을 눌러야 할 수 있습니다. [YouTube 플레이어 이벤트](https://developers.google.com/youtube/iframe_api_reference#onAutoplayBlocked)
