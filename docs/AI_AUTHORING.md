# AI 비전 개론 출제 안내

AI 비전 개론 트랙에 학습 노트, 연습 문항, 생성기, 그림을 넣는 사람이 보는 문서입니다. 파일 규격, 봉인·검증·서명 명령, 출제·재풀이·대조·검토를 나눠 맡는 교차 검증 순서, 쓰는 사람과 검토하는 사람이 같이 쓰는 체크 목록을 적었습니다. 학습 노트의 기본 꼴과 서명은 웹 면접 준비의 학습 페이지와 같아서 [WEB_AUTHORING.md](WEB_AUTHORING.md) 의 학습 페이지 절도 함께 읽습니다.

이 트랙은 코드를 실행하지 않습니다. 앱, 도구, 테스트, 생성기 어느 것도 `torch` 와 `numpy` 를 import 하지 않고, 코드 지식은 코드 빈칸과 코드 고르기로만 묻습니다. 강의 자료가 맞다고 가정하지 않습니다. 문항은 사실 확인을 마친 사실(`facts.json`)로만 만들고, 강의 자료 오류는 학습 노트의 「정정」 상자와 해설에서 바로잡습니다.

## 1. 폴더와 파일

```
ai/
  index.json                차시(lessons), 상황별 코드(patterns), 모의고사(mocks), 시험 날짜(exam), 학습 노트 목록(pages, order)
  terms.json                낱말 사전. term·also·page 는 웹과 같고 accept(빈칸에서 더 받는 말)·intro(먼저 소개한 노트)를 더함
  retired.json              지운 카드·문장 id 목록. 한 번 쓴 id 는 다른 문항에 다시 쓰지 않습니다
  learn/l05/
    meta.json               공개. 웹 키(title, defines, needs, sections, outputs, sources) + lesson, credits, units
    page.md                 공개. 봉인하지 않습니다
    assets/l05-3.gif …      그림. 이름은 노트 그림 l05-3, 단원 그림 5c-1
    review.json             학습 노트 서명(verify_web.py 가 씀)
  items/i05/
    meta.json               공개. 단원별 카드 수
    gens.py, oracle.py      공개. 생성기와 그 정답(생성기를 보지 않고 쓴 판)
    sealed.json             work/ 를 묶은 봉인 파일. 이것만 커밋합니다
    work/                   평문 작업본. 커밋하지 않습니다
      items.json            빈칸·고르기 문항
      statements.json       참거짓을 정한 문장 묶음
      facts.json            확인된 사실과 강의 자료 오류
      review.json           문항 묶음 서명(verify_ai.py --sign 이 씀)
  items/common/gens.py      공용 생성기(@base). 차시마다 register 로 붙입니다
  mocks/m1/                 모의고사(뒤 PR)
tools/ai_art/
  lNN.py                    그 노트의 그림 스크립트(출제자 컴퓨터에서만)
  manifest.json             스크립트로 그린 그림의 sha256
```

차시는 학습 노트 `meta.json`, 문항 `meta.json`, 봉인(또는 평문 작업본)이 모두 있으면 화면에 나옵니다. 학습 노트 `meta.json` 의 `units` 에 적은 단원만 보이므로 다 된 단원부터 낼 수 있습니다.

## 2. 학습 노트(page.md)

`#` 은 노트 제목, `##` 는 단원, `###` 는 단계입니다. 단원 제목은 `meta.json` 의 `sections` 값과 같아야 하고, 단원 키는 `<차시 번호><a~i>`(5c), 상황별 코드는 `18a`~`18h` 입니다. `sections` 에 없는 `##`(그림 출처 등)는 단원으로 세지 않습니다. `##` 바로 밑에는 글을 두지 않고 첫 `###` 안에 씁니다.

단계 제목 바로 밑 줄에 그 단계가 설명하는 사실 id 를 적습니다. 이 줄은 화면에 넘기기 전에 지워지고 verify_ai 가 카드의 `step` 과 맞춰 봅니다.

```
### 시그모이드를 여러 번 지나면 기울기가 줄어듭니다
<!-- facts: F05-12 F05-13 -->
```

단계의 종류는 제목 앞머리로 정합니다. 「심화」로 시작하면 대학원 강의안 단계, 「보충 설명」은 시험 범위 안의 보충, 「더 알아보기」는 시험 범위 밖, 「외울 것」은 단원 마지막 단계입니다. 그 밖은 강의 단계입니다. 단원 단계는 먼저 풀어 보기와 외울 것을 넣어 4~7개이고, 마지막은 꼭 「외울 것」입니다.

울타리 블록은 JSON 한 덩이로 씁니다.

| 블록 | 필드 | 화면 |
|---|---|---|
| `ai-guess` | `id`, `q`, `options`(2~4), `answer`(0부터), `reveal_step`(답을 보일 뒤 단계 번호), `cards` | 먼저 풀어 보기. 채점하지 않음 |
| `ai-reveal` | `guess`(먼저 풀어 보기 id) | 처음 고른 답과 정답 한 줄 |
| `ai-recall` | `id`, `q`(`____` 하나), `answer`, `mode`, 선택 `why` | 떠올리기. 바로 채점, 상자는 움직이지 않음 |
| `ai-why` | `q`, `a` | 왜일까요. 답은 접어 둠 |
| `ai-memo` | `[{"q", "a", "cards"}]` | 외울 것. 질문을 누르면 답이 펴짐 |
| `ai-trend` | `title`, `text` | 2026 흐름. 단계 수에 넣지 않음 |

외울 것의 `cards` 는 그 단원의 핵심 카드를 모두 덮어야 합니다. 정정과 보충 설명은 인용 블록 머리로 씁니다: `> **[정정]** …`, `> **[보충 설명]** …`.

`terms.json` 의 낱말은 정의한 노트를 `page` 로 둡니다. 앞 차시가 그 낱말을 먼저 쓰면 그 차시를 `intro` 로 두고, 그 차시 `meta.json` 의 `defines` 에 넣고, 처음 쓰는 문장 앞에 "…을 오차라고 부릅니다" 꼴 정의 한 문장을 둡니다. 1차시가 어림값의 오차를 먼저 쓰고 4차시가 예측의 오차를 정의하는 경우처럼 쓰임이 조금 달라도 이렇게 소개합니다. `also` 에 적은 꼴은 한 낱말에만 두고, 다른 낱말에서도 받을 꼴은 `accept` 에 둡니다. 4차시의 오차와 손실처럼 서로 다른 낱말로 가르치는 두 말은 서로의 `accept` 에 넣지 않습니다.

그림 블록은 웹과 같은 꼴이고 GIF 의 `프레임:` 줄 수는 GIF 장 수와 같아야 합니다. 프레임 줄은 그림 아래 장 설명으로 보이는 글이라 말투 검사를 받습니다.

````
```figure
파일: assets/5c-1.gif
캡션: 그림 4. 층을 지날 때마다 곱해지는 미분값
프레임:
1. 가로는 층 번호, 세로는 곱한 값입니다. (2000ms)
2. 세 층을 지나면 0.25 를 세 번 곱합니다. (2000ms)
```
````

## 3. 문항

카드 id 는 `i05-b07`(빈칸), `i05-c03`(고르기), `i05-s21`(문장), `i05-g02`(생성기), 주제는 `i05-t03` 입니다. 모든 카드에 `unit`, `step`(`5c/3`), `facts`, `core`, `prio`(1~3), `level`(1~3), `tags`(1~3개), `ref` 를 둡니다. 선택 필드는 `family`(같은 계산·같은 사실 묶음), `confuse`(헷갈리는 짝 태그, `confuse:axis-0-1` 꼴), `deep`(대학원 근거), `errata`(걸린 강의 자료 오류 id), `alt`(같은 사실을 바꿔 쓴 판)입니다. `step` 단계의 `<!-- facts -->` 줄과 카드 `facts` 가 하나 이상 겹쳐야 합니다. 단원마다 핵심 카드(`core`)는 3~4개입니다.

빈칸 문항은 지문의 `____` 수와 `blanks` 수가 같아야 합니다. 칸마다 `answer`(첫째가 화면 정답), `mode`, 선택 `hint`·`places`·`unit`·`term` 을 둡니다.

| mode | 쓰는 곳 | 받는 차이 |
|---|---|---|
| `word` | 개념 낱말 | 공백·붙임표·가운뎃점·밑줄, 끝 조사 하나나 "입니다", terms.json 의 also·accept |
| `code` | 코드 토큰 | 공백, 따옴표 모양, 빈칸 좌우 문맥을 같이 쓴 답, 정답에 없는 끝 `()` 와 앞 `.` |
| `number` | 계산 값 | 천 단위 쉼표, 빼기표(U+2212), 분수, `unit` 꼬리, `places` 반올림 |
| `shape` | 텐서 모양 | 대괄호·소괄호·x·×, `torch.Size(...)` |
| `values` | 배열 값 | `tensor(...)`·`array(...)` 껍데기, `dtype=`, 원소 반올림. True·False 는 1·0 과 다르게 봄 |
| `exact` | 서식 문자열 | 앞뒤 공백만 |

빈칸 바로 뒤에 받침에 따라 갈리는 조사를 두지 않고 "____ 입니다" 꼴로 씁니다. 칸이 둘 이상이면 칸끼리 정답이 겹치지 않게 지문에 칸마다 무엇인지 적습니다. `register_full_backward_hook` 처럼 긴 API 이름은 고르기로만 냅니다.

고르기 문항은 보기 4개이고 `options[].ok` 는 그 보기 글이 참인지입니다. `pick: "right"` 면 참인 보기가, `"wrong"` 이면 거짓인 보기가 답입니다. 모두 고르기(`multi: true`)는 답 2~3개이고 지문에 "모두" 를 씁니다. 답이 아닌 보기의 `why` 는 바른 문장 한 줄이고, 옳은 것 고르기의 거짓 보기에는 노리는 착각을 짧게 적은 `aim` 을 둡니다(화면에 나오지 않음). "모두 옳다" 처럼 다른 보기를 가리키는 보기는 쓰지 않습니다.

문장 묶음(`statements.json`)은 주제마다 참 4·거짓 4 이상입니다. 참 문장에는 상자 2 부터 나오는 빈칸판 `cloze`(`____` 하나와 `answer`)를 둡니다. 상자는 문장마다 따로 셉니다.

생성기는 `gens.py` 에 씁니다. 표준 라이브러리만 쓰고 `basis` 는 `lecture-example` 이나 `lecture-formula` 입니다.

```python
from aiprep.gen import blank, gen, num

@gen("i05-g02", unit="5b", level=2, tags=["Linear 파라미터 수"], ref=["5차시 과제 5번"], facts=["F05-20"],
     basis="lecture-formula", step="5b/3")
def linear_params(r):
    """입력 a, 출력 c 인 Linear 층의 학습 파라미터 수."""
    a, c = r.pick([8, 16, 32]), r.int(1, 10)
    return blank(stem="`nn.Linear(%d, %d)` 의 학습 파라미터는 ____ 개입니다." % (a, c),
                 blanks=[{"answer": [str(a * c + c)], "mode": "number", "unit": "개"}],
                 explain="입력 × 출력 + 출력(편향)입니다. %d×%d+%d = %s 입니다." % (a, c, c, num(a * c + c)),
                 params={"a": a, "c": c})
```

`oracle.py` 에는 생성기 id 의 붙임표를 밑줄로 바꾼 함수(`def i05_g02(params)`)를 둡니다. 빈칸이면 칸마다 정답 글의 목록, 고르기면 답 보기의 글을 돌려줍니다. 300 시드에서 생성기와 oracle 이 같아야 하고 서로 다른 지문이 20개 이상이어야 합니다. 반올림 경계는 `fixed(x, k)` 가 `Retry` 로 피합니다.

`ref` 는 이 꼴만 받습니다: `5차시 슬 p21`, `5차시 노트북 02 [7]`, `5차시 과제 4번`, `10차시 강의노트 [3]`, `요약 1주차 p14`, `대학원 05 p15`, `공식 13차시`, `PyTorch 문서 CrossEntropyLoss`. 첫 ref 는 그 차시의 슬라이드·노트북·과제·강의노트·요약본이고, 대학원·공식만 근거인 카드는 `deep` 입니다.

## 4. 사실 확인(facts.json)

`facts` 의 사실마다 `id`, `from`(factcheck 의 위치), `text`(확인 기록을 바꿔 쓴 한 문장), `verdict`, `where`, `checked` 를 둡니다. `verdict` 가 틀림·확인 못 함인 사실은 문항에 쓰지 않습니다. 단순화·부분적으로 맞음이면 `ask_as` 의 표현으로만 묻습니다. `concept_only` 사실은 number·exact·values 빈칸으로 묻지 않습니다. `errata` 의 강의 자료 오류를 건드리는 카드는 해설에 "정정" 문구를 두고 모의고사에 넣지 않습니다. `sources` 에는 강의 폴더 기준 경로와 sha256 을 적습니다. 경로는 실제 폴더 이름을 그대로 써서 `강의_11기_AI개론_2차시_…/강의_11기_AI개론_2차시_01_numpy.ipynb` 꼴이고, 요약본은 맨 위 파일 이름만 씁니다. `verify_ai.py --sources` 가 이 경로로 파일을 찾습니다.

## 5. 그림

학습 노트 그림은 `tools/ai_art/lNN.py` 를 출제자 파이썬(numpy·matplotlib·Pillow)으로 돌려 직접 그리고, matplotlib 는 Agg 로만 씁니다. 파일은 폭 1120px·높이 600px 이하, GIF 는 10장 이하·장마다 1,600~2,500ms·250KB 이하, PNG 는 150KB 이하입니다. 그림에 찍는 숫자는 스크립트 안에서 assert 로 확인합니다.

```
python3 -m tools.ai_art l05                                    @figure 함수를 그려 assets/ 에 쓰고 manifest 를 고칩니다
python3 tools/ai_art/l05.py                                    자기 명령줄로 그리는 스크립트
python3 -m tools.ai_art l05 --record                           그린 뒤 manifest 만 고칩니다(표준 라이브러리)
```

manifest 에 없는 그림은 verify_ai 가 실패로 봅니다. 가져온 그림은 이번 단계에서 쓰지 않습니다.

## 6. 명령

```
python3 tools/ai_seal.py seal [i05 ...] [--keep]          work/ → sealed.json
python3 tools/ai_seal.py unseal i05                       sealed.json → work/
python3 tools/ai_seal.py check                            평문이 남았거나 봉인이 깨졌으면 실패
python3 tools/ai_seal.py brief i05 --out DIR              재풀이용 문제지(sheet.md)와 빈 답안(answers.json), 저장소 밖에만
python3 tools/verify_ai.py [i05 common ...]               문항 꼴, 빈칸 규칙, 고르기, 문장, 생성기 300 시드, 사실 확인, 노트 블록, 근거, 말투, 그림
python3 tools/verify_ai.py i05 --answers DIR/answers.json 재풀이 답안을 채점
python3 tools/verify_ai.py i05 --sign --writer "출제 1" --resolver "재풀이 2" --checker "대조 3" --reviewer "검토 4" \
        --first-pass DIR/answers.json --minutes 95 --finding "i05-b09 지문이 두 가지로 읽혀 고침"
python3 tools/verify_ai.py --require-review               문항 묶음·common·모의고사 서명 확인(CI)
python3 tools/verify_web.py --bank ai --total-mb 32 l05   학습 노트 꼴·그림·서명(--sign --writer --resolver --reviewer)
python3 tools/web_lint.py --bank ai --no-external         학습 노트 말투와 맥락(낱말을 쓰기 전에 소개)
python3 tools/ai_overlap.py --lecture "$AI_LECTURE_DIR" l05 i05   강의 글 겹침(출제자 컴퓨터에서만, PDF 는 pypdf)
python3 tools/verify_ai.py --sources "$AI_LECTURE_DIR"    강의 폴더 sha256 을 facts.json 과 견줌
python3 tools/verify_ai.py --overrides                    [내 답도 맞음] 답 모아 보기
python3 tools/verify_ai.py --leeches                      자주 틀리는 문항 모아 보기
```

이 컴퓨터에서는 `python3` 를 `/opt/homebrew/bin/python3` 로 씁니다. 서명은 글 파일(.py, .json, .md)을 줄 끝 LF 로 읽어 해시를 세므로 Windows 에서 받아도 맞습니다. 봉인은 내용을 바꾸지 않아 봉인 앞뒤로 서명이 맞습니다. 서명 뒤에 한 글자라도 고치면 `--require-review` 가 떨어지고, 바뀐 카드를 다시 재풀이·대조·검토한 뒤 다시 서명합니다.

## 7. 교차 검증 순서

| 꼬리표 | 하는 일 | 겸할 수 없는 것 |
|---|---|---|
| 출제 | facts.json, 학습 노트, 그림 스크립트, 문항, 문장, 생성기를 씀 | 나머지 셋 |
| 재풀이 | 공개본과 학습 노트만 보고 모든 카드를 풂. 생성기는 견본 10개를 손으로 풀고 oracle.py 를 씀 | 출제, 대조 |
| 대조 | 카드의 사실마다 factcheck 줄과 원문 위치를 열어 확인, 정정 상자, 그림 숫자, 겹침 검사, 강의 폴더 sha256 | 출제, 재풀이 |
| 검토 | 학습자에게 보이는 문장을 하나씩 읽고 체크 목록과 말투를 보고 서명 | 출제 |

1. 출제가 factcheck·차시 분석·요약본·코드 보충을 읽고 쓸 사실을 facts.json 에 옮깁니다. 새 사실은 대조가 판정한 뒤에만 넣습니다.
2. 출제가 work/ 평문으로 노트·문항·생성기·그림을 쓰고 verify_web, web_lint, verify_ai, ai_overlap 을 통과시킵니다.
3. `ai_seal.py brief` 로 만든 공개본을 재풀이에게 넘깁니다. 재풀이는 answers.json 과 oracle.py, 걸린 시간, 막힌 곳을 돌려줍니다.
4. 대조가 `verify_ai.py --answers` 로 채점하고 틀린 카드마다 원인을 하나로 정합니다(정답 틀림, 두 가지로 읽힘, 받는 답 빠짐, 공정한 함정, oracle 불일치).
5. 검토가 아래 체크 목록을 보고, 새로 걸린 말투 문장은 `tools/check_style.py` 패턴에 더합니다.
6. 학습 노트와 문항 묶음에 서명하고 `ai_seal.py seal`, `ai_seal.py check` 로 봉인합니다.

꼬리표는 "출제 1" 꼴로 쓰고 만든 도구 이름은 저장소 어디에도 적지 않습니다.

## 8. 체크 목록

쓰는 사람(출제)이 PR 전에, 검토하는 사람(재풀이·대조·검토)이 서명 전에 같은 목록을 씁니다. PR 본문에는 체크한 줄 수만 적습니다.

짜임
- [ ] 단계 4~6개, 읽기 5분 안팎, 첫 단계 먼저 풀어 보기 1~2개, 마지막 외울 것
- [ ] 예제 하나를 단원 끝까지 이어 씀, 연습은 숫자만 바꿈
- [ ] 개념 단계마다 그림 하나(과정이면 GIF), 단원 첫 그림에 낱말 이름표
- [ ] 단계마다 떠올리기 하나, 핵심 단계에 왜일까요 하나

정확성
- [ ] 단원의 모든 사실·숫자가 facts.json 에 있고 판정이 맞음(또는 ask_as 표현)
- [ ] 그림·장 설명·본문·연습의 숫자가 같고, 그림 스크립트 assert 가 통과
- [ ] 일반화 문장에 반례가 없음, 우연히 같은 값은 밝힘
- [ ] 강의 자료 오류는 그 단계 안 정정 상자에, 정정 주제는 모의고사에 없음
- [ ] 출력 주석은 노트북 출력이거나 다시 계산한 값

처음 배우는 사람
- [ ] 낱말을 쓰기 전에 정의, 한 낱말 한 뜻, 영어 이름은 처음 한 번
- [ ] 축·색·기호의 뜻을 처음 나올 때 적음, 색은 단원 안에서 한 뜻
- [ ] 코드의 새 API 를 코드 바로 아래에서 설명, 준비 줄을 지우지 않음
- [ ] 재풀이자가 처음부터 읽고 막힌 곳을 모두 고침

문항
- [ ] 빈칸 정답이 3.3 의 넷 가운데 하나, 조사 함정 없음, 답이 하나로 정해짐
- [ ] 고르기 보기 4개, 오답마다 노리는 착각과 바른 문장
- [ ] 과제와 같은 계산은 숫자·이름을 바꿈

저작물과 말투
- [ ] 강의 문장을 옮기지 않음(겹침 검사 통과), 강의 비유 장면을 옮기지 않음
- [ ] 슬라이드 그림을 따라 그리지 않음, 가져온 그림은 허용 라이선스와 출처
- [ ] 말투 검사 셋 통과, 정리문·은유·em-dash 없음

빈칸 정답 넷: (가) 학습 노트가 정의한 낱말, (나) 지문이 쓰임을 밝힌 강의 코드의 API·인자·토큰, (다) 지문의 숫자로 계산되는 값, (라) 지문에서 따라갈 수 있는 shape.

## 9. 엔진이 카드를 내는 규칙

학습자 쪽 규칙(상자, 학습일, 묶음, 오답 노트)은 [CRITERIA.md](CRITERIA.md) 와 엔진 코드(`aiprep/`)에 있습니다. 출제에 걸리는 것만 적습니다.

- 핵심 카드는 단원을 읽으면 열리고, 비핵심 카드는 그 단원 핵심 카드가 모두 상자 2 이상일 때 열립니다. 차시 풀기로 연 차시는 모든 카드가 열립니다.
- 같은 `family` 는 한 묶음에 하나만 나오고, 외운 문항 수도 family 로 셉니다.
- 같은 `confuse` 태그 카드는 한 문항을 사이에 두고 가까이 나옵니다.
- 문장 카드는 상자 1 까지 고르기, 상자 2 부터 빈칸판으로 나옵니다.
- 하루 새 카드 상한과 오늘 목표 단원은 기본으로 꺼 두었습니다(학습자가 문제집을 원하는 만큼 풂). 켜려면 `aiprep/service.py` 의 `NEW_PER_DAY`, `DAILY_GOAL` 을 바꿉니다.
