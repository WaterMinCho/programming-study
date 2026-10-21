# w03. 거래내역 불러오기

이 미션은 화면이 서버에서 데이터를 받아 오는 동안 생기는 일을 다룹니다. 미리 받은 작은 React 저장소를 20분 동안 읽고, 이어지는 45분 동안 면접관이 하나씩 건네는 요구에 맞게 코드를 고칩니다.

토스증권의 2026년 공개 채용 공고에는 1차 면접이 미리 받은 코드베이스를 면접관과 함께 읽고 고치는 라이브 코딩이라고 적혀 있습니다. 이 미션은 그 형식을 따라 새로 지은 연습 문제이고 실제 출제 문제와는 관계가 없습니다.

## 어떤 앱인가요

은행 앱의 거래내역 화면입니다. 위쪽에 생활비 통장, 저축 통장, 새 통장 탭이 있고, 탭을 누르면 아래 목록이 그 통장의 거래내역으로 바뀝니다. 서버는 없고 `src/api.ts`의 가짜 함수가 서버 대신 응답합니다.

## 어떻게 실행하나요

[폴더 열기]를 누르거나 `submissions/<내 ID>/web/missions/w03/` 폴더를 에디터에서 여세요. 에디터의 터미널에서 아래 명령을 실행하세요. 패키지는 프로그램이 스터디 저장소 맨 위 `node_modules` 폴더에 설치해 두었으니 미션 폴더에서 `npm install`을 하지 마세요. 미션 폴더 안에 따로 설치하면 React가 두 벌 읽혀 훅 에러가 날 수 있습니다.

```
npm run dev      # http://localhost:5173 에서 앱이 열립니다
npm test         # 저장소에 들어 있는 테스트를 실행합니다
```

프로그램 아래쪽의 [화면 띄우기]를 눌러도 `npm run dev`와 같은 서버가 뜨고 브라우저에 앱이 열립니다. 서버는 같은 자리의 [화면 끄기]를 누르거나 미션 화면을 떠나면 꺼집니다. [테스트 돌리기]는 `npm test`와 같은 테스트를 돌려 통과한 개수와 첫 실패를 보여 줍니다.

Windows의 PowerShell 터미널에서는 `npm run dev`가 "npm.ps1 파일을 로드할 수 없습니다"라는 오류로 막힐 수 있습니다. 그럴 때는 `npm.cmd run dev`와 `npm.cmd test`로 실행하거나 [화면 띄우기]와 [테스트 돌리기]를 쓰세요. PowerShell의 실행 정책은 바꾸지 않아도 됩니다.

## 파일은 어떻게 나뉘어 있나요

```
src/
  main.tsx                        앱 시작 파일 (StrictMode 사용)
  App.tsx                         고른 통장 id state 와 탭, 목록을 가진 최상위 컴포넌트
  accounts.ts                     통장 세 개의 id 와 이름
  api.ts                          가짜 서버 getTransactions(accountId, options)
  types.ts                        Account, Transaction 타입
  format.ts                       금액과 날짜를 화면용 글자로 바꾸는 함수
  components/AccountTabs.tsx      통장 탭 버튼
  components/TransactionList.tsx  거래내역을 불러와 목록을 그리는 컴포넌트
  components/TransactionRow.tsx   거래 한 줄
  App.test.tsx                    지금 통과하는 기존 테스트
  format.test.ts                  format.ts 의 기존 테스트
```

## 가짜 서버는 어떻게 응답하나요

`getTransactions(accountId, options)`는 정해 둔 시간을 기다린 뒤 거래 배열을 돌려주는 Promise를 돌려줍니다. `npm run dev`로 띄운 화면에서는 생활비 통장이 1.5초, 저축 통장이 0.3초 뒤에 응답하고, 새 통장은 빈 배열을 돌려줍니다. 주소 끝에 `?fail=1`을 붙이면 첫 요청이 실패합니다. 테스트에서는 기다리지 않고 바로 응답합니다.

`options.signal`에는 요청을 그만두라는 신호를 넘길 수 있습니다. AbortController는 요청을 중간에 끊게 해 주는 브라우저 내장 객체입니다. `new AbortController()`로 만든 객체의 `signal`을 요청에 넘겨 두고 나중에 그 객체의 `abort()`를 부르면, 가짜 서버는 응답을 멈추고 이름이 `AbortError`인 에러로 Promise를 거부합니다. 브라우저의 `fetch`도 같은 방식으로 요청을 끊습니다.

## 읽으면서 답해 볼 질문

실전을 시작하면 면접관이 코드를 설명해 달라고 합니다. 아래 질문에 답할 수 있게 읽어 두세요.

- 통장 탭을 누르면 어떤 state가 바뀌고, 그 값이 어떤 경로로 `TransactionList`까지 내려가나요?
- `TransactionList`의 `useEffect`는 언제 다시 실행되나요?
- 응답을 기다리는 동안 화면에는 무엇이 보이나요? 요청이 실패하면 화면은 어떻게 되나요?
- 기존 테스트는 무엇을 확인하나요?
