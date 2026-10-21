# 비동기와 Promise: 늦게 온 응답과 요청 묶기

화면이 서버에 요청을 보내고 응답을 기다리는 동안 사용자는 다른 글자를 치고 다른 탭을 누릅니다. 그사이 요청은 보낸 순서와 다르게 돌아오기도 하고, 여럿을 한꺼번에 보내면 그 가운데 하나만 실패하기도 합니다. 이 페이지의 앞 절은 늦게 돌아온 응답이 화면을 덮는 버그를 검색창 코드로 재현하고, React가 effect를 다시 실행하기 전에 부르는 함수와 AbortController로 고치며, 뒤 절은 요청 여러 개를 `Promise.all`과 `Promise.allSettled`로 묶을 때 실패를 어떻게 다루는지, 요청 수가 많을 때 동시에 보내는 수를 어떻게 제한하고 언제 다시 보내는지를 다룹니다. 끝까지 읽으면 꼬리 질문 사슬 3-A와 3-B의 질문, 그리고 이 페이지의 출력 순서 문제 네 개에 답할 수 있습니다.

## 늦게 온 응답은 어떻게 화면을 덮나요

사용자가 검색창에 글자를 칠 때마다 `query`가 바뀌고, 아래 effect가 검색 API를 불러 결과를 `results` state에 넣습니다. 사슬 3-A에서 면접관이 보여 주는 코드와 같습니다.

```tsx
useEffect(() => {
  fetch(`/api/search?q=${query}`)
    .then((res) => res.json())
    .then((data) => setResults(data));
}, [query]);
```

이 코드에서 두 요청이 엇갈리는 모습과 React가 effect를 다시 실행하기 전에 부르는 함수를 차례로 보고, 이어서 고친 코드 두 벌을 봅니다.

### 두 요청은 어떻게 엇갈리나요

검색창에 'r', 're', 'rea', 'reac', 'react'가 차례로 들어가면 effect가 다섯 번 실행되어 요청도 다섯 번 나갑니다. 아래 그림은 그 가운데 're'와 'react' 요청만 시간축에 그린 것입니다. 're' 요청은 먼저 나갔지만 서버가 더 오래 걸려 'react' 요청보다 늦게 끝납니다.

```figure
파일: assets/3a-1.gif
캡션: 그림 3A-1. 're' 요청이 'react' 요청보다 늦게 끝나 화면이 옛 결과로 돌아갑니다.
프레임:
1. 가로 시간축 아래에 're' 요청 막대가 0ms 에서 시작함. 오른쪽 화면 칸은 비어 있음. (1400ms)
2. 'react' 요청 막대가 200ms 에서 시작함. 're' 막대는 계속 늘어남. (1400ms)
3. 'react' 막대가 500ms 에서 끝나고 화면 칸에 'react 결과'가 들어감. (1600ms)
4. 're' 막대가 900ms 에서 끝나고 화면 칸이 're 결과'로 바뀜. 바뀐 칸에 빨간 테두리와 "마지막 setResults" 표시. (2200ms)
```

`.then((data) => setResults(data))`는 응답이 도착한 순서대로 실행됩니다. 코드에는 "이 응답이 지금 검색어의 응답인가"를 확인하는 곳이 없어서, 가장 늦게 도착한 응답이 화면에 남습니다. 앞서 보낸 요청의 응답이 늦게 도착해 나중 요청의 결과를 덮는 문제를 경쟁 상태(race condition)라고 합니다.

브라우저 없이도 이 순서를 볼 수 있습니다. 아래 코드는 서버 대신 `setTimeout`으로 're' 응답을 900ms 뒤에, 'react' 응답을 300ms 뒤에 돌려줍니다. 실행하기 전에 무엇이 먼저 찍힐지 적어 보세요.

```js
function search(q, ms) {
  return new Promise((resolve) => setTimeout(() => resolve(`${q} 결과`), ms));
}
search('re', 900).then((data) => console.log(data));
search('react', 300).then((data) => console.log(data));
```

'react 결과'가 먼저 찍히고 're 결과'가 뒤에 찍힙니다. `then`에 넘긴 콜백은 Promise가 이행된 순서대로 실행되므로, `search`를 부른 순서는 출력 순서와 관계가 없습니다. 화면 코드였다면 마지막에 찍힌 're 결과'가 `setResults`로 들어가 화면에 남습니다.

### 정리 함수는 언제 실행되나요

`useEffect`에 넘긴 함수가 함수 하나를 돌려주면 React는 그 함수를 기억해 두었다가 나중에 부릅니다. 이렇게 돌려준 함수를 정리 함수라고 합니다. `query`가 're'에서 'rea'로 바뀌면 React는 화면을 새 값으로 그린 뒤, 're' 때 실행된 effect의 정리 함수를 먼저 부르고 나서 'rea' effect를 실행합니다. 컴포넌트가 화면에서 사라질 때도 마지막 effect의 정리 함수를 부릅니다. 're' 요청을 버리거나 끊는 코드를 정리 함수에 넣으면 'rea' effect가 실행되기 전에 're' 요청을 정리할 수 있습니다.

```figure
파일: assets/3a-2.png
캡션: 그림 3A-2. query가 바뀌면 React는 화면을 그린 뒤 앞 effect의 정리 함수를 부르고, 그다음에 새 effect를 실행합니다.
내용: 왼쪽에서 오른쪽으로 칸 다섯 개. "query='re' 로 그림" → "effect('re') 실행, 요청 1" → "query='rea' 로 그림" → "정리('re')" → "effect('rea') 실행, 요청 2". 정리 칸만 주황색으로 칠하고 요청 1 쪽으로 점선 화살표.
```

### 플래그로 늦은 응답 버리기

참이나 거짓으로 상태를 표시하는 변수를 플래그라고 부릅니다. effect마다 플래그 `ignore`를 하나 두고, 정리 함수에서 그 값을 `true`로 바꿉니다.

```tsx
useEffect(() => {
  let ignore = false;
  fetch(`/api/search?q=${encodeURIComponent(query)}`)
    .then((res) => res.json())
    .then((data) => {
      if (!ignore) setResults(data);
    });
  return () => {
    ignore = true;
  };
}, [query]);
```

effect 함수가 실행될 때마다 `ignore` 변수가 새로 생기고, 같은 실행에서 만들어진 정리 함수와 `then` 콜백은 그 `ignore`를 함께 봅니다. 그래서 're' effect의 정리 함수가 실행되면 're' effect의 `ignore`만 `true`가 되고, 're' 응답이 늦게 와도 `setResults`를 부르지 않아 'react' 결과가 화면에 남습니다. 이 방법은 요청 자체를 멈추지는 않아서 're' 응답은 끝까지 내려받습니다.

### AbortController로 요청 끊기

AbortController는 요청을 중간에 끊게 해 주는 브라우저 내장 객체입니다. effect마다 AbortController를 만들어 그 `signal`을 `fetch`에 넘겨 두면, 나중에 `abort()`를 불러 그 요청을 끊을 수 있습니다. 아래 코드는 실패를 화면에 보여 주려고 `error` state를 하나 더 둡니다.

```tsx
useEffect(() => {
  const controller = new AbortController();
  fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal: controller.signal })
    .then((res) => {
      if (!res.ok) throw new Error(`검색 실패: ${res.status}`);
      return res.json();
    })
    .then((data) => setResults(data))
    .catch((error) => {
      if (error.name === 'AbortError') return;
      setError(error);
    });
  return () => controller.abort();
}, [query]);
```

정리 함수에서 `controller.abort()`를 부르면 're' 요청이 끊기고, 're' `fetch`의 Promise는 이름이 `AbortError`인 에러로 거부됩니다. 이 거부는 사용자가 볼 실패가 아니라서 `catch`에서 이름을 확인하고 넘어갑니다. 같은 코드에 `res.ok` 확인도 넣었습니다. `fetch`의 Promise는 서버가 404나 500을 돌려줘도 거부되지 않기 때문에, 상태 코드를 직접 보고 에러를 던져야 `catch`로 갑니다.

```figure
파일: assets/3a-3.gif
캡션: 그림 3A-3. 정리 함수가 're' 요청을 끊으면 'react' 결과가 화면에 남습니다.
프레임:
1. 그림 3A-1 의 1번 프레임과 같은 시간축. 're' 막대가 시작됨. (1400ms)
2. 100ms 자리에 작은 'rea' 입력 눈금. 그 순간 're' 막대 끝에 "abort()" 표시가 붙고 're' 막대가 회색으로 멈춤. 200ms 에 'react' 막대가 시작됨. 본문대로 're' 는 query 가 'rea' 로 바뀔 때 끊기므로 표시를 'react' 시작 자리에 두지 않음. (1800ms)
3. 'react' 막대가 500ms 에서 끝나고 화면 칸에 'react 결과'가 들어감. (1600ms)
4. 900ms 자리에 회색 점선과 "AbortError, 화면에 쓰지 않음" 글자. 화면 칸은 'react 결과'로 남고 초록 테두리. (2200ms)
```

### 직접 재현해 보기

가짜 검색 함수를 만들어 짧은 검색어일수록 늦게 응답하게 하면 경쟁 상태를 눈으로 볼 수 있습니다.

```ts
function fakeSearch(q: string): Promise<string[]> {
  const delay = q.length < 3 ? 1500 : 300;
  return new Promise((resolve) => setTimeout(() => resolve([`${q} 결과`]), delay));
}
```

React 프로젝트에 검색창 컴포넌트를 하나 만들고, 이 절 처음에 본 검색 effect에서 `fetch` 대신 `fakeSearch(query).then(setResults)`를 부른 뒤 'react'를 빠르게 쳐 보세요. 'r'과 're' 요청이 1.5초 뒤에 도착해 화면에 're 결과'가 남습니다. 그다음 플래그나 AbortController로 고치세요. `fakeSearch`는 `signal`을 받지 않으므로, AbortController로 고칠 때는 `then` 안에서 `controller.signal.aborted`를 확인해 끊긴 요청의 결과를 버립니다. 고친 뒤 같은 입력을 다시 해서 'react 결과'가 남는지 확인하세요.

## 여러 요청을 묶을 때 하나가 실패하면 어떻게 되나요

광고 캠페인 목록에서 사용자가 캠페인 여러 개를 골라 [중지]를 누르면 아래 함수가 실행됩니다. `pauseCampaign(id)`는 캠페인 하나를 중지하라고 서버에 요청하고, 서버가 처리를 마치면 이행되는 Promise를 돌려줍니다. 사슬 3-B에서 면접관이 보여 주는 코드와 같습니다.

```ts
async function pauseSelected(ids: string[]) {
  await Promise.all(ids.map((id) => pauseCampaign(id)));
  showToast('고른 캠페인을 모두 중지했습니다');
}
```

캠페인 20개를 골랐는데 요청 하나가 실패하면 "모두 중지했습니다" 대신 에러 화면이 뜨고, 목록을 새로 고치면 19개는 중지되어 있습니다. 이 절에서는 그 이유를 `Promise.all`의 동작에서 찾고, `Promise.allSettled`로 고친 뒤, 요청이 500개일 때와 실패한 요청을 다시 보낼 때까지 이어서 봅니다.

### Promise.all은 하나가 거부되면 그 순간 거부됩니다

`Promise.all`은 Promise 배열을 받아 Promise 하나를 돌려줍니다. 넘긴 Promise가 모두 이행되면 그 값들을 넘긴 순서대로 담은 배열로 이행되고, 하나라도 거부되면 나머지를 기다리지 않고 그 순간 같은 이유로 거부됩니다. 거부된 뒤에도 나머지 Promise는 취소되지 않습니다. 요청은 서버에서 그대로 처리되고 응답도 돌아오지만, 그 결과를 받아 볼 곳이 없습니다.

아래 코드는 서버 대신 `setTimeout`으로 응답 셋을 흉내 냅니다. 'A'는 300ms 뒤에 성공하고, 'B'는 100ms 뒤에 실패하고, 'C'는 200ms 뒤에 성공합니다. 같은 Promise 셋을 `Promise.all`과 `Promise.allSettled`에 각각 넘겼을 때 무엇이 어떤 순서로 찍힐지 먼저 적어 보세요.

```js
const ok = (ms, v) => new Promise((resolve) => setTimeout(resolve, ms, v));
const fail = (ms, msg) => new Promise((_, reject) => setTimeout(reject, ms, new Error(msg)));

Promise.all([ok(300, 'A'), fail(100, 'B 실패'), ok(200, 'C')])
  .then((values) => console.log('all 성공', values))
  .catch((error) => console.log('all 실패', error.message));

Promise.allSettled([ok(300, 'A'), fail(100, 'B 실패'), ok(200, 'C')])
  .then((results) => console.log(results.map((r) => r.status).join(', ')));
```

100ms에 'B'가 거부되는 순간 `Promise.all`이 거부되어 'all 실패 B 실패'가 먼저 찍힙니다. `Promise.allSettled`는 300ms에 'A'까지 끝난 뒤에야 이행되어 'fulfilled, rejected, fulfilled'가 그다음에 찍힙니다. `Promise.all` 쪽의 'C'와 'A'는 200ms와 300ms에 이행되지만 아무 곳에도 찍히지 않습니다.

```figure
파일: assets/3b-1.gif
캡션: 그림 3B-1. 요청 B가 100ms에 실패하는 순간 Promise.all이 거부되고, 뒤늦게 끝난 A와 C의 결과는 받는 곳이 없습니다.
프레임:
1. 가로 시간축 0~300ms 아래에 요청 A, B, C 막대가 0ms 에서 함께 시작함. 오른쪽에 "Promise.all" 상자, 상태 "대기 중". (1400ms)
2. 100ms 에서 B 막대가 끝나고 빨간 "거부" 표시. Promise.all 상자가 빨갛게 "거부됨"으로 바뀌고 아래 "catch 실행, 에러 화면" 칸으로 화살표. A, C 막대는 계속 늘어남. (2000ms)
3. 200ms 에서 C 막대가 끝남. 끝에 회색 "이행, 받는 곳 없음" 글자. (1600ms)
4. 300ms 에서 A 막대가 끝남. 같은 회색 글자. Promise.all 상자는 그대로 "거부됨". (2000ms)
```

### Promise.allSettled는 모두 끝난 뒤 결과를 하나씩 돌려줍니다

`Promise.allSettled`도 Promise 배열을 받아 Promise 하나를 돌려주지만, 넘긴 Promise가 모두 이행되거나 거부될 때까지 기다린 뒤에 이행되고, 중간에 거부되는 일이 없습니다. 이행된 값은 결과 객체의 배열이고, 결과 객체는 이행된 자리에서 `{ status: 'fulfilled', value }`, 거부된 자리에서 `{ status: 'rejected', reason }` 모양입니다. 배열의 자리는 넘긴 순서를 지키므로 `ids[i]`의 결과가 `results[i]`에 있습니다.

```figure
파일: assets/3b-2.png
캡션: 그림 3B-2. allSettled의 결과 배열은 넘긴 순서대로 자리마다 status가 적혀 있어, 성공한 자리와 실패한 자리를 나눌 수 있습니다.
내용: 위에 "Promise.allSettled([A, B, C])" 글자. 가운데 카드 셋: 0번 "fulfilled / value: 'A'"(초록 테두리), 1번 "rejected / reason: Error"(빨간 테두리), 2번 "fulfilled / value: 'C'"(초록 테두리). 아래 왼쪽 상자 "성공 2개: 중지했습니다 안내", 아래 오른쪽 상자 "실패 1개: 다시 시도 단추". 0번·2번 카드에서 왼쪽 상자로, 1번 카드에서 오른쪽 상자로 화살표.
```

일괄 중지 함수를 `Promise.allSettled`로 바꾸면 성공과 실패를 나눠 안내할 수 있습니다.

```ts
async function pauseSelected(ids: string[]) {
  const results = await Promise.allSettled(ids.map((id) => pauseCampaign(id)));
  const failed = ids.filter((_, i) => results[i].status === 'rejected');
  if (failed.length === 0) {
    showToast(`캠페인 ${ids.length}개를 중지했습니다`);
    return;
  }
  showToast(`${ids.length - failed.length}개를 중지했고 ${failed.length}개는 실패했습니다`);
  setRetryTargets(failed);
}
```

`failed`에는 실패한 캠페인 id만 남으므로, [다시 시도]를 누르면 그 id만 다시 `pauseSelected`에 넘기면 됩니다. 결과를 모두 합쳐야만 다음 일을 할 수 있을 때는 `Promise.all`이 맞습니다. 캠페인 상세 화면을 그리는 데 캠페인 정보, 광고 소재 목록, 예산 잔액 세 응답이 모두 필요하다면, 하나라도 실패한 순간 화면을 그릴 수 없으니 바로 실패 처리로 넘어가는 편이 사용자를 덜 기다리게 합니다.

### 결과 배열은 끝난 순서가 아니라 넘긴 순서를 지킵니다

`Promise.all`이 이행될 때 값 배열의 자리는 Promise가 끝난 순서가 아니라 넘긴 순서를 따릅니다. 아래 코드에서 'B'는 100ms, 'A'는 300ms 뒤에 끝납니다. 끝나는 순서와 결과 배열의 순서를 각각 적어 보세요.

```js
const wait = (ms, v) => new Promise((resolve) => setTimeout(() => { console.log(v, '끝'); resolve(v); }, ms));
Promise.all([wait(300, 'A'), wait(100, 'B')]).then((values) => console.log(values.join(', ')));
```

'B 끝', 'A 끝' 순서로 찍힌 뒤 결과 배열은 'A, B'로 찍힙니다. 그래서 `const [campaign, creatives, budget] = await Promise.all([...])`처럼 자리로 꺼내 써도 어느 응답이 먼저 왔는지와 관계없이 각 변수에 맞는 값이 들어갑니다.

### 동시에 보내는 요청 수를 제한합니다

캠페인이 500개라면 `ids.map`으로 요청 500개가 한꺼번에 나갑니다. 브라우저는 HTTP/1.1로 한 서버에 동시에 여는 연결을 6개 안팎으로 제한하므로 그 뒤 요청은 브라우저 안에서 줄을 서고, 서버도 한꺼번에 들어온 요청에 429(요청이 너무 많음)로 답하거나 느려집니다. 그래서 동시에 진행 중인 요청 수를 정해 둔 개수로 제한하고, 하나가 끝나면 다음 것을 보냅니다.

가장 단순한 방법은 500개를 5개씩 잘라 묶음마다 `Promise.allSettled`를 기다리는 것인데, 묶음에서 가장 느린 하나가 끝날 때까지 다음 묶음이 나가지 못합니다. 아래 코드는 작업자 함수 여러 개가 같은 줄에서 다음 작업을 꺼내 가게 해서 빈자리가 바로 채워지게 합니다. `tasks`는 부르면 Promise를 돌려주는 함수의 배열이고, `limit`은 동시에 진행할 개수입니다. 코드 아래쪽은 100ms에서 300ms가 걸리는 작업 여섯 개를 작업자 둘로 돌려 끝난 순서와 결과 순서를 찍습니다.

```js
async function runPool(tasks, limit) {
  const results = new Array(tasks.length);
  let next = 0;
  async function worker() {
    while (next < tasks.length) {
      const i = next++;
      results[i] = await tasks[i]().then(
        (value) => ({ status: 'fulfilled', value }),
        (reason) => ({ status: 'rejected', reason }),
      );
    }
  }
  await Promise.all(Array.from({ length: limit }, worker));
  return results;
}

const finished = [];
const durations = [300, 100, 150, 100, 300, 100];
const tasks = durations.map((ms, i) => () => new Promise((resolve) => {
  setTimeout(() => { finished.push(i); resolve(i); }, ms);
}));
runPool(tasks, 2).then((results) => {
  console.log('끝난 순서', finished.join(' '));
  console.log('결과 순서', results.map((r) => r.value).join(' '));
});
```

작업자 둘이 0번과 1번을 먼저 집고, 1번이 100ms에 끝나면 그 작업자가 2번을 집습니다. 그래서 끝난 순서는 '1 2 0 3 5 4'이고, 결과 배열은 `results[i]`에 넣었으므로 '0 1 2 3 4 5' 순서를 지킵니다. `worker`가 `await`에서 멈춰 있는 동안 다른 작업자가 `next`를 읽고 늘리므로 같은 작업을 두 작업자가 집는 일은 없습니다. 자바스크립트는 한 번에 한 함수만 실행하고 `next++`는 그 사이에 끼어들 틈이 없기 때문입니다.

```figure
파일: assets/3b-3.gif
캡션: 그림 3B-3. 작업자 둘이 같은 줄에서 다음 작업을 꺼내 가면, 하나가 끝나는 순간 빈자리가 바로 채워집니다.
프레임:
1. 가로 시간축 0~600ms. 줄 두 개 "작업자 1", "작업자 2". 0ms 에 작업자 1 이 0번(300ms), 작업자 2 가 1번(100ms)을 집음. 왼쪽 "남은 작업" 칸에 2 3 4 5. (1400ms)
2. 100ms. 1번이 끝나고 작업자 2 가 2번(150ms)을 집음. 남은 작업 3 4 5. (1400ms)
3. 250ms. 2번이 끝나고 작업자 2 가 3번(100ms)을 집음. 남은 작업 4 5. (1400ms)
4. 300ms. 0번이 끝나고 작업자 1 이 4번(300ms)을 집음. 남은 작업 5. (1400ms)
5. 350ms. 3번이 끝나고 작업자 2 가 5번(100ms)을 집음. 남은 작업 비어 있음. (1400ms)
6. 450ms. 5번이 끝남. 작업자 2 는 빈 채로 기다림. (1400ms)
7. 600ms. 4번이 끝남. 아래에 결과 배열 0 1 2 3 4 5 가 순서대로 채워져 보임. (2200ms)
```

서버가 id 배열을 한 번에 받는 일괄 API를 둘 수 있다면 요청 하나로 끝나므로, 화면에서 500번 보내기 전에 서버 쪽과 먼저 상의합니다.

### 실패한 요청은 조건을 보고 다시 보냅니다

실패한 요청을 자동으로 다시 보낼 때는 어떤 실패인지부터 봅니다. 네트워크가 끊겼거나 서버가 500번대로 답한 요청은 잠시 뒤 다시 보내면 성공할 수 있습니다. 400이나 404처럼 요청 자체가 잘못됐다는 400번대 응답은 다시 보내도 결과가 같아서 바로 실패로 안내합니다. 400번대 가운데 408은 서버가 요청을 기다리다 시간이 지나 끊었다는 뜻이고 429는 서버가 잠시 뒤 다시 보내라는 뜻이라 예외로 다시 보냅니다. 429는 서버가 `Retry-After` 헤더에 적어 준 시간이 지난 뒤에 보냅니다.

간격은 1초, 2초, 4초처럼 두 배씩 늘리고 횟수에 상한을 둡니다. 이렇게 간격을 두 배씩 늘리는 방식을 지수 백오프라고 합니다. 실패한 요청 여럿이 같은 순간에 다시 몰리지 않게 간격마다 무작위 시간을 조금 더합니다.

```ts
const RETRY_STATUS = new Set([408, 429, 500, 502, 503, 504]);

async function fetchWithRetry(input: RequestInfo, init?: RequestInit, retries = 3): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    let res: Response | undefined;
    try {
      res = await fetch(input, init);
      if (res.ok || !RETRY_STATUS.has(res.status)) return res;
    } catch (error) {
      if (attempt >= retries) throw error;
    }
    if (attempt >= retries) return res!;
    const retryAfter = Number(res?.headers.get('Retry-After'));
    const base = retryAfter > 0 ? retryAfter * 1000 : 1000 * 2 ** attempt;
    await new Promise((resolve) => setTimeout(resolve, base + Math.random() * 300));
  }
}
```

`try` 안에서 `fetch`가 던지는 에러는 네트워크가 끊긴 경우이고, `res.ok`가 거짓인데 `RETRY_STATUS`에 없는 상태 코드는 다시 보내지 않고 그대로 돌려줍니다. `Retry-After`가 있으면 그 초를, 없으면 1초에 `2 ** attempt`를 곱한 시간을 기다립니다.

```figure
파일: assets/3b-4.png
캡션: 그림 3B-4. 다시 보내는 간격은 두 배씩 늘리고 무작위 시간을 더하며, 429는 Retry-After가 적어 준 시간을 따릅니다.
내용: 가로 시간축 0~8초. 1차 0초 "503, 1초 뒤", 2차 1초 "네트워크 오류, 2초 뒤", 3차 3초 "429, Retry-After: 4", 4차 7초 "200 성공". 시도마다 세로 표시와 응답 글자, 간격마다 "+무작위 0~0.3초" 꼬리표. 아래 띠에 "다시 보내지 않음: 400, 403, 404" 상자.
```

다시 보내도 되는 요청인지도 확인합니다. 여러 번 보내도 한 번 보낸 것과 결과가 같은 성질을 멱등이라고 합니다. 캠페인 중지 요청은 이미 중지된 캠페인에 한 번 더 가도 결과가 같아 멱등하지만, "예산 1만 원 추가" 같은 요청은 두 번 가면 2만 원이 더해집니다. 멱등하지 않은 요청은 서버가 요청마다 붙인 고유 키로 중복을 거를 수 있을 때만 다시 보냅니다.

### 직접 해 보기

이 페이지의 `js` 코드 블록 네 개는 브라우저 없이 Node로 실행됩니다. 각 블록을 파일로 저장하고 터미널에서 `node` 뒤에 파일 이름을 적어 실행하거나, 브라우저 개발자 도구의 Console 탭에 붙여 넣어 실행해 보세요.

- `Promise.all` 블록에서 `fail(100, 'B 실패')`를 `ok(100, 'B')`로 바꾸고, 'all 성공'이 몇 ms에 찍힐지 적은 뒤 실행해 보세요. 셋이 모두 끝나는 300ms에 찍힙니다.
- `runPool` 블록에서 `limit`을 1과 6으로 바꿔 끝난 순서가 어떻게 달라지는지 보세요. 1이면 넘긴 순서대로 끝나고, 6이면 걸리는 시간이 짧은 것부터 끝납니다.
- `fetchWithRetry`를 실제로 써 보려면 `https://httpstat.us/503` 같은 상태 코드 시험용 주소를 넘기고, Network 탭에서 요청 사이의 간격이 1초, 2초, 4초로 늘어나는지 확인하세요.

## 면접에서는 이렇게 이어집니다

꼬리 질문 사슬 3-A는 앞 절의 검색 코드를 보여 주고 "왜 옛 결과가 남나요", "어떻게 고치나요", "그 밖에 빠진 처리는요", "React Query를 쓰면요" 순서로 묻습니다. 사슬 3-B는 뒤 절의 일괄 중지 코드를 보여 주고 "19개는 중지됐는데 왜 에러인가요"에서 시작해 `Promise.all`을 쓸 때, 500개를 보낼 때, 다시 보낼 조건으로 이어집니다. 사슬 7-B는 React Query의 `staleTime`과 캐시 무효화를 묻고, 라이브 코딩 미션 w03에서는 앞 절의 코드를 통장 탭 화면에 직접 넣어 보며, w13에서는 뒤 절의 일괄 처리를 캠페인 관리 화면에서 고칩니다.
