# state로 둘 값, effect, 서버 상태

React 화면을 짤 때는 값마다 state에 둘지 렌더링할 때 계산할지 정하고, 화면 바깥의 무엇인가와 맞추는 코드는 effect에 넣고, 서버에서 받은 데이터는 언제 다시 받을지 정합니다. 이 페이지는 상품 목록 위에 검색창이 붙은 화면 하나로 세 결정을 차례로 따라갑니다. 첫 절은 걸러 낸 목록을 state에 따로 두었을 때 생기는 버그와 렌더링 중에 계산하는 코드를, 둘째 절은 effect가 돌려주는 함수가 언제 불리는지와 개발 모드에서 effect가 한 번 더 실행되는 이유를, 셋째 절은 서버에서 받은 상품 목록을 불러오는 중, 실패, 성공으로 나눠 다루는 법과 React Query 같은 라이브러리가 맡는 일, 여러 화면이 함께 쓰는 값을 Context와 store 가운데 어디에 둘지를 다룹니다. 끝까지 읽으면 꼬리 질문 사슬 7-A와 7-B의 질문, 그리고 이 페이지에서 실행 결과를 예상해 보는 문제 세 개에 답할 수 있습니다.

## state로 둘 값과 계산할 값

상품 목록 화면 위쪽에 검색창이 있고, 검색어를 치면 이름에 그 검색어가 든 상품만 아래 목록에 남습니다. 부모 컴포넌트는 서버에서 상품 배열을 받아 `products` props로 넘기는데, 응답이 오기 전에는 빈 배열을 넘기고 응답이 오면 상품 셋이 든 배열을 넘깁니다. 이 절의 코드는 모두 아래 타입과 상품 셋을 씁니다. `ProductList`는 `products` props로 받은 상품을 한 줄씩 그리는 컴포넌트입니다.

```ts
type Product = { id: string; name: string; price: number };

const PRODUCTS: Product[] = [
  { id: 'p1', name: 'USB-C 케이블', price: 9900 },
  { id: 'p2', name: 'usb 허브', price: 25000 },
  { id: 'p3', name: '무선 충전기', price: 32000 },
];
```

### 걸러 낸 목록을 state에 따로 두면 어긋납니다

처음 떠올리기 쉬운 코드는 검색어와 걸러 낸 목록을 둘 다 state에 두고, 검색어가 바뀔 때 두 값을 함께 바꾸는 코드입니다.

```tsx
function ProductSearch({ products }: { products: Product[] }) {
  const [query, setQuery] = useState('');
  const [filtered, setFiltered] = useState(products);

  function handleChange(value: string) {
    setQuery(value);
    setFiltered(products.filter((p) => p.name.includes(value)));
  }

  return (
    <>
      <input value={query} onChange={(e) => handleChange(e.target.value)} placeholder="상품 검색" />
      {filtered.length === 0 ? <p>검색 결과가 없습니다</p> : <ProductList products={filtered} />}
    </>
  );
}
```

이 화면은 상품 응답이 도착한 뒤에도 "검색 결과가 없습니다"만 보여 줍니다. `useState`에 넘긴 값은 첫 렌더링에서만 초기값으로 쓰이고, 그 뒤에 `products`가 바뀌어도 `filtered`에는 들어가지 않습니다. 첫 렌더링 때 `products`는 응답이 오기 전의 빈 배열이었으므로 `filtered`도 빈 배열로 시작하고, 상품 셋이 도착해도 사용자가 검색창에 글자를 치기 전까지 빈 배열로 남습니다.

```figure
파일: assets/7a-1.gif
캡션: 그림 7A-1. 상품 셋이 도착해도 filtered는 첫 렌더링의 빈 배열로 남아 화면에 상품이 보이지 않습니다.
프레임:
1. 위에 "첫 렌더링, 응답 전" 글자. 왼쪽 props 칸 products: [], 가운데 state 칸 query: '', filtered: []. 오른쪽 화면 칸에 "검색 결과가 없습니다". (1400ms)
2. 위 글자가 "응답 도착, 다시 렌더링"으로 바뀜. products 칸에 상품 셋(USB-C 케이블, usb 허브, 무선 충전기)이 들어가고 초록 테두리. filtered 칸과 화면 칸은 앞 프레임과 같음. (1800ms)
3. filtered 줄과 화면 칸에 빨간 테두리. products 칸 아래에서 state 칸 아래로 가는 빨간 점선 화살표와 "useState 초기값은 첫 렌더링에서만" 꼬리표. (2200ms)
```

`products`가 바뀔 때도 `filtered`를 다시 계산하려고 effect를 붙이면 화면은 맞게 나옵니다.

```tsx
const [query, setQuery] = useState('');
const [filtered, setFiltered] = useState(products);

useEffect(() => {
  setFiltered(products.filter((p) => p.name.includes(query)));
}, [products, query]);
```

그래도 같은 정보가 `products`, `query`, `filtered` 세 곳에 나뉘어 있습니다. 가격순 정렬처럼 목록을 바꾸는 조건을 더하면 effect 안의 계산과 effect 끝의 `[products, query]` 배열을 함께 고쳐야 하고, 배열에 새 조건을 빠뜨리면 정렬 순서를 바꿔도 `filtered`는 옛 순서로 남습니다. 렌더링도 매번 두 번씩 일어납니다. 글자를 하나 치면 React는 새 `query`와 옛 `filtered`로 한 번 렌더링하고, effect가 `setFiltered`를 부른 뒤 새 `filtered`로 한 번 더 렌더링합니다.

### 계산할 수 있는 값은 렌더링 중에 계산합니다

`filtered`는 `products`와 `query`만 알면 언제든 계산할 수 있습니다. 이런 값은 state로 두지 않고 컴포넌트 함수 안에서 렌더링할 때마다 계산합니다. 아래 코드는 `filtered` state를 지우고, 걸러 낸 목록을 `visible` 변수에 계산해 담습니다.

```tsx
function ProductSearch({ products }: { products: Product[] }) {
  const [query, setQuery] = useState('');
  const visible = products.filter((p) => p.name.includes(query));

  return (
    <>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="상품 검색" />
      {visible.length === 0 ? <p>검색 결과가 없습니다</p> : <ProductList products={visible} />}
    </>
  );
}
```

`visible`은 렌더링할 때마다 그때의 `products`와 `query`로 새로 계산되므로, 상품이 늦게 도착해도 검색어를 지워도 두 값과 어긋나지 않습니다. 다른 state나 props로 계산해서 얻는 값을 파생 상태(derived state)라고 부르는데, 이름에 '상태'가 붙어 있지만 state에 넣는 값이 아니라 지금처럼 렌더링 중에 계산하는 값을 가리킵니다. 면접에서 "파생 상태를 state에 넣지 않은 이유"를 물으면 앞의 두 코드가 만든 어긋남과 두 번 렌더링을 들어 답하면 됩니다.

계산이 한 줄에 모여 있으면 요구가 늘어도 그 줄만 고칩니다. 사용자가 'usb'를 치면 'USB-C 케이블'도 찾아야 한다는 요구가 오면 이름과 검색어를 모두 소문자로 바꿔 비교합니다. 아래 코드는 두 비교로 걸러 낸 상품 수를 찍습니다. 실행하기 전에 두 줄에 각각 몇이 찍힐지 적어 보세요.

```js
const products = [
  { id: 'p1', name: 'USB-C 케이블', price: 9900 },
  { id: 'p2', name: 'usb 허브', price: 25000 },
  { id: 'p3', name: '무선 충전기', price: 32000 },
];
const query = 'usb';
console.log(products.filter((p) => p.name.includes(query)).length);
console.log(products.filter((p) => p.name.toLowerCase().includes(query.toLowerCase())).length);
```

첫 줄에는 1, 둘째 줄에는 2가 찍힙니다. 문자열의 `includes`는 대소문자를 구분해서 'usb'로는 'usb 허브'만 찾고, 양쪽을 `toLowerCase()`로 바꾸면 'USB-C 케이블'도 찾습니다. 화면 코드에서는 `visible`을 계산하는 줄을 이렇게 고치고, 검색어 앞뒤의 빈칸을 지우는 `trim()`도 같이 붙입니다.

```tsx
const keyword = query.trim().toLowerCase();
const visible = products.filter((p) => p.name.toLowerCase().includes(keyword));
```

검색창을 비우거나 빈칸만 치면 `keyword`가 빈 문자열이 되고, `includes('')`는 어느 문자열에서나 `true`를 돌려주므로 상품이 모두 보입니다. 결과가 없을 때의 문구도 `visible.length`로 정하므로 결과가 비었는지를 담는 state를 따로 두지 않습니다.

상품이 수천 개이거나 비교가 복잡해서 계산 한 번이 오래 걸리면 `useMemo`로 감쌉니다. `useMemo`는 계산 함수와 배열을 받아, 배열에 적은 값이 앞 렌더링 때와 같으면 다시 계산하지 않고 앞 렌더링의 결과를 돌려주는 훅입니다.

```tsx
const visible = useMemo(
  () => products.filter((p) => p.name.toLowerCase().includes(keyword)),
  [products, keyword],
);
```

React 문서는 `console.time`으로 계산 시간을 재 보고 1ms 정도를 넘으면 감쌀 만하다고 하며, `useMemo`가 첫 렌더링을 빠르게 하지는 못한다고 적어 둡니다. 상품 몇십 개를 거르는 정도라면 `useMemo` 없이 계산합니다.

### state로 둘지는 세 질문으로 가립니다

React 문서의 「Thinking in React」는 데이터 하나가 state인지 세 질문으로 가립니다. 시간이 지나도 바뀌지 않으면 state가 아니고, 부모가 props로 넘겨주면 state가 아니고, 다른 state나 props로 계산할 수 있으면 state가 아닙니다. 상품 검색 화면에 대 보면 검색창의 안내 글처럼 바뀌지 않는 글은 첫 질문에서, `products`는 둘째 질문에서, `visible`과 결과 개수는 셋째 질문에서 빠지고, 사용자가 친 `query`만 state로 남습니다.

목록 가운데 사용자가 고른 상품을 기억할 때도 같은 질문을 씁니다. 상품 객체를 통째로 state에 넣으면 서버에서 그 상품의 가격이 바뀌어 새 `products`가 와도 state에 담긴 사본은 옛 가격을 보여 줍니다. 고른 상품의 id만 state에 두고 상품 객체는 렌더링 중에 `products`에서 찾으면 사본이 생기지 않습니다.

```tsx
const [selectedId, setSelectedId] = useState<string | null>(null);
const selected = products.find((p) => p.id === selectedId);
```

```figure
파일: assets/7a-2.png
캡션: 그림 7A-2. 세 질문을 차례로 거치면 상품 검색 화면에서 state로 남는 값은 사용자가 친 검색어와 고른 상품의 id입니다.
내용: 위에서 아래로 질문 칸 셋. "시간이 지나도 바뀌지 않나요?", "부모가 props로 넘기나요?", "다른 state나 props로 계산할 수 있나요?". 질문 칸마다 오른쪽으로 "예" 화살표가 "state 아님" 칸을 가리킴(안내 글 '상품 검색' / products / visible, 결과 개수, 고른 상품 객체). 질문 칸 사이에 "아니요" 화살표가 아래로 이어지고 맨 아래 초록 칸에 "state로 둠: query, selectedId".
```

`useState`의 초기값이 첫 렌더링에서만 쓰인다는 성질은 앞에서 버그를 만들었지만, 처음 한 번만 읽으면 되는 값에는 맞습니다. 주소가 `/products?q=usb`처럼 검색어를 담은 채 열렸을 때 그 검색어로 검색창을 채워 두려면, 주소에서 읽은 값을 초기값으로 넘깁니다. `useState`에 함수를 넘기면 React는 첫 렌더링 때만 그 함수를 불러 초기값을 얻으므로, 렌더링할 때마다 주소를 다시 읽지 않습니다.

```tsx
const [query, setQuery] = useState(() => new URLSearchParams(window.location.search).get('q') ?? '');
```

이렇게 열고 나면 검색어가 주소와 state 두 곳에 있게 됩니다. 사용자가 검색어를 바꿀 때 주소도 같이 고쳐야 두 값이 어긋나지 않고, 그 코드는 사용자가 글자를 친 결과이므로 `onChange` 함수 안에 둡니다.

## useEffect 정리 함수는 언제 실행되나요

앞 절에서 `filtered`를 맞추려고 붙인 effect는 지울 수 있었습니다. effect는 React가 화면을 그린 뒤에 실행할 코드를 넘기는 자리이고, React 바깥에 있는 무엇인가를 지금 화면과 맞출 때 씁니다. 이 절은 상품 화면에서 effect가 필요한 일과 필요 없는 일을 나누고, effect가 돌려주는 함수가 언제 불리는지, 개발 모드에서 effect가 한 번 더 실행되는 이유를 차례로 봅니다.

### effect는 React 바깥과 맞출 때 씁니다

상품 화면에서 하는 일을 값 계산, 사용자 동작 처리, 바깥 대상과 맞추기로 나누면 effect에서 할 일은 바깥 대상과 맞추는 일입니다.

- 앞 절의 `visible`처럼 다른 state나 props로 계산할 수 있는 값은 effect 없이 렌더링 중에 계산합니다.
- [장바구니 담기]를 눌러 서버에 담기 요청을 보내는 일은 사용자가 단추를 누른 결과라서 `onClick` 함수 안에서 합니다. effect에 두면 단추를 누르지 않았는데도 화면이 다시 나타날 때 요청이 또 나갈 수 있습니다.
- `window`에 키보드 단축키를 거는 일, 재고가 바뀌면 알려 주는 서버에 구독하는 일, 화면에 보일 상품을 서버에서 받아 오는 일은 React 바깥의 대상을 화면과 맞추는 일이라서 effect에서 합니다.

effect의 두 번째 인자로 넘기는 배열을 의존성 배열이라고 합니다. 의존성 배열에는 effect 안에서 쓰는 props와 state를 적습니다. React는 컴포넌트를 다시 렌더링할 때마다 그 값들을 앞 렌더링의 값과 `Object.is`로 비교하고, 하나라도 바뀌었으면 화면을 고친 뒤 effect를 다시 실행합니다. 빈 배열 `[]`을 넘기면 비교할 값이 없어서 컴포넌트가 처음 화면에 나타날 때만 실행됩니다.

### 정리 함수는 의존성이 바뀔 때와 화면에서 빠질 때 불립니다

effect 함수가 함수 하나를 돌려주면 React는 그 함수를 기억해 두었다가, 그 effect가 한 일을 되돌릴 때 부릅니다. 이렇게 돌려준 함수를 정리 함수라고 합니다. React가 정리 함수를 부르는 때는 의존성 배열의 값이 바뀌어 effect를 다시 실행하기 직전과, 컴포넌트가 화면에서 빠질 때입니다.

아래 코드의 `StockBadge`는 상품 하나의 재고 알림을 켜 두는 컴포넌트입니다. 실제 앱이라면 `console.log` 자리에서 재고 서버에 구독하고 해지하는데, 여기서는 순서만 보려고 콘솔에 찍습니다. `App`의 [p2 보기]는 보여 줄 상품을 바꾸고, [닫기]는 `StockBadge`를 화면에서 뺍니다.

Vite로 만든 React 프로젝트의 `App.tsx`에 이 코드를 넣고, `npm run build` 뒤 `npm run preview`로 띄운 운영 빌드에서 화면을 연 다음 [p2 보기]와 [닫기]를 차례로 누른다고 해 봅니다. 콘솔에 무엇이 어떤 순서로 찍힐지 적어 보세요.

```tsx
import { useEffect, useState } from 'react';

function StockBadge({ productId }: { productId: string }) {
  useEffect(() => {
    console.log(`구독 ${productId}`);
    return () => console.log(`구독 해지 ${productId}`);
  }, [productId]);
  return <span>{productId} 재고 알림 켜짐</span>;
}

export default function App() {
  const [productId, setProductId] = useState('p1');
  const [open, setOpen] = useState(true);
  return (
    <>
      <button onClick={() => setProductId('p2')}>p2 보기</button>
      <button onClick={() => setOpen(false)}>닫기</button>
      {open && <StockBadge productId={productId} />}
    </>
  );
}
```

화면이 열리면 '구독 p1'이 찍힙니다. [p2 보기]를 누르면 `productId`가 'p2'로 바뀌어 React가 화면을 다시 그리고, 의존성 배열의 값이 바뀌었으므로 p1 때 실행된 effect의 정리 함수를 먼저 불러 '구독 해지 p1'을 찍은 뒤 새 effect를 실행해 '구독 p2'를 찍습니다. [닫기]를 누르면 `StockBadge`가 화면에서 빠지면서 마지막 effect의 정리 함수가 불려 '구독 해지 p2'가 찍힙니다. 정리 함수가 찍는 id는 그 정리 함수를 돌려준 effect가 실행될 때의 `productId`라서, 'p2'로 바뀐 뒤에 불린 정리 함수가 'p1'을 찍습니다. [p2 보기]를 한 번 더 눌러도 `productId`가 이미 'p2'라서 effect도 정리 함수도 실행되지 않습니다.

```figure
파일: assets/7b-1.gif
캡션: 그림 7B-1. productId가 바뀌면 앞 effect의 정리 함수가 먼저 불리고, 컴포넌트가 빠질 때 마지막 정리 함수가 불립니다.
프레임:
1. 위에 "재고 알림 effect와 정리 함수가 불리는 차례(운영 빌드)" 글자. 가로 시간축에 "화면 열림" 눈금과 그 아래 effect(p1) 막대. 오른쪽 콘솔 칸에 '구독 p1', 아래 화면 칸에 'p1 재고 알림 켜짐'. (1400ms)
2. "p2 보기 클릭" 눈금. effect(p1) 막대가 끝나고 주황 "정리(p1)" 칸이 붙음. 콘솔에 '구독 해지 p1'이 더해지고 화면 칸은 'p2 재고 알림 켜짐'. (1800ms)
3. 정리(p1) 뒤에 아래 줄의 effect(p2) 막대가 시작되고 콘솔에 '구독 p2'가 더해짐. (1600ms)
4. "닫기 클릭" 눈금. effect(p2) 막대 끝에 주황 "정리(p2)" 칸이 붙고 콘솔에 '구독 해지 p2'가 더해짐. 화면 칸에는 "(StockBadge가 빠짐)". (2200ms)
```

### StrictMode는 개발 모드에서 effect를 한 번 더 실행합니다

`StrictMode`는 개발 중에만 추가 검사를 켜는 React 컴포넌트이고, Vite로 만든 React 프로젝트의 `main.tsx`는 처음부터 `<App />`을 `<StrictMode>`로 감싸 둡니다. StrictMode 안의 컴포넌트가 처음 화면에 나타나면 React는 effect를 실행하고, 곧바로 정리 함수를 부른 뒤, effect를 한 번 더 실행합니다. 그래서 앞의 재고 알림 코드를 `npm run dev`로 띄운 개발 서버에서 열면 '구독 p1', '구독 해지 p1', '구독 p1'이 찍히고, 그 뒤 [p2 보기]와 [닫기]를 누를 때는 운영 빌드와 같은 줄이 찍힙니다. 운영 빌드에서는 화면이 열릴 때 '구독 p1' 한 줄만 찍힙니다.

React가 effect를 한 번 더 실행하는 까닭은 정리 함수가 effect가 한 일을 빠짐없이 되돌리는지 개발 중에 보려는 데 있습니다. 정리 함수가 맞게 짜여 있으면 실행, 정리, 실행을 거친 결과가 사용자에게는 한 번 실행한 결과와 똑같이 보입니다. 정리 함수를 빠뜨린 effect는 이 추가 실행에서 바로 드러납니다. 아래 코드는 '/' 키를 누르면 검색창으로 커서를 옮기는 단축키를 `window`에 거는데, 정리 함수가 없습니다. [검색 닫기]는 검색창을 화면에서 뺍니다.

```tsx
import { useEffect, useRef, useState } from 'react';

function SearchBox() {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key !== '/') return;
      e.preventDefault();
      console.log('검색창으로 이동');
      inputRef.current?.focus();
    }
    window.addEventListener('keydown', handleKeyDown);
  }, []);
  return <input ref={inputRef} placeholder="상품 검색" />;
}

export default function App() {
  const [open, setOpen] = useState(true);
  return (
    <>
      <button onClick={() => setOpen(false)}>검색 닫기</button>
      {open && <SearchBox />}
    </>
  );
}
```

개발 서버에서 '/'를 한 번 누르면 '검색창으로 이동'이 두 번 찍힙니다. `handleKeyDown`은 effect가 실행될 때마다 새로 만들어지는 함수라서, StrictMode가 effect를 두 번 실행하는 동안 서로 다른 함수 두 개가 `window`에 붙었습니다. 두 실행 사이에 React가 부를 정리 함수가 없었으므로 처음 붙은 함수도 떨어지지 않았습니다. [검색 닫기]를 누른 뒤에 '/'를 눌러도 두 줄이 찍힙니다. 운영 빌드에서는 함수가 한 번만 붙어 한 줄씩 찍히지만, 검색창을 닫은 뒤에도 '/'를 누를 때마다 사라진 검색창을 찾는 함수가 실행됩니다.

정리 함수에서 붙인 함수를 떼면 개발 서버에서도 '/'를 누를 때 한 줄만 찍히고, 검색창을 닫은 뒤에는 아무것도 찍히지 않습니다. `removeEventListener`는 붙일 때 넘긴 함수와 같은 함수를 받아야 그 함수를 떼므로, 정리 함수에는 같은 effect 안에서 만든 `handleKeyDown`을 그대로 넘깁니다.

```tsx
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);
```

```figure
파일: assets/7b-2.gif
캡션: 그림 7B-2. StrictMode의 실행, 정리, 실행을 거치면 정리 함수가 없는 쪽에만 키 함수가 두 개 남습니다.
프레임:
1. 왼쪽 열 "정리 함수 없음", 오른쪽 열 "정리 함수 있음". 열마다 "실행 → 정리 → 다시 실행" 단계 칸, window의 keydown 함수 칸, 콘솔 칸. 두 열 모두 "실행" 칸이 켜지고 window 칸에 "키 함수" 하나가 붙음. (1400ms)
2. 두 열 모두 "정리" 칸이 켜짐. 왼쪽은 키 함수 하나가 남고, 오른쪽은 키 함수 자리에 "떼어 냄" 표시만 남음. (1800ms)
3. 두 열 모두 "다시 실행" 칸이 켜짐. 왼쪽 window 칸에 키 함수 둘, 오른쪽은 하나. (1800ms)
4. 위 글자가 "'/'를 한 번 눌렀을 때"로 바뀜. 왼쪽 콘솔 칸에 '검색창으로 이동' 두 줄과 빨간 테두리, 오른쪽 콘솔 칸에 한 줄과 초록 테두리. (2200ms)
```

### 두 번 실행을 막지 말고 정리 함수를 고칩니다

개발 모드에서 두 줄이 찍히는 것을 보고 `useRef`에 실행 여부를 적어 두 번째 실행을 건너뛰게 고치는 코드가 자주 보입니다. 앞 `SearchBox`의 effect를 이렇게 바꾸는 식이고, `handleKeyDown`을 만드는 줄은 앞 코드와 같아서 뺐습니다.

```tsx
const didRun = useRef(false);
useEffect(() => {
  if (didRun.current) return;
  didRun.current = true;
  window.addEventListener('keydown', handleKeyDown);
}, []);
```

이렇게 고치면 개발 서버에서도 한 줄만 찍히지만, 검색창을 닫은 뒤에도 함수가 `window`에 남는 버그는 고쳐지지 않습니다. React 문서도 effect를 한 번만 실행하게 막지 말고, 다시 실행되어도 문제가 없도록 정리 함수를 고치라고 안내합니다. 정리 함수에서 할 일은 effect가 무엇을 했는지에 따라 정합니다.

- 이벤트에 붙인 함수와 서버 구독은 정리 함수에서 떼거나 해지합니다.
- `setTimeout`과 `setInterval`로 건 타이머는 정리 함수에서 `clearTimeout`과 `clearInterval`로 멈춥니다.
- 서버에서 데이터를 받아 오는 effect는 개발 모드에서 요청이 두 번 나갑니다. 정리 함수에서 첫 요청의 응답을 버리거나 요청을 끊으면 화면에는 두 번째 응답만 쓰입니다. 다음 절의 `useProducts`가 응답을 버리는 쪽으로 씁니다.
- 페이지를 몇 번 열었는지 세려고 서버에 보내는 기록처럼 서버에 남기기만 하는 요청은 개발 모드에서 두 번 가도 사용자가 보는 화면이 바뀌지 않아서 고치지 않습니다. 운영 빌드에서는 한 번만 갑니다.
- 결제나 장바구니 담기처럼 두 번 가면 안 되는 요청은 애초에 effect가 아니라 단추의 이벤트 함수에서 보냅니다.

## 서버 상태는 왜 따로 다루나요

이번에는 앞 절들의 `ProductSearch`에 넘기던 `products`를 어디서 받는지 봅니다. 화면 위쪽에 '전체', '주방', '전자기기' 분류 탭이 있고, 탭을 누르면 부모 컴포넌트가 그 분류의 상품을 서버에서 받아 `ProductSearch`에 넘깁니다.

검색어는 이 화면 안에서 생기고 이 화면 안에서만 바뀝니다. 상품 목록은 원본이 서버에 있고, 화면이 들고 있는 것은 받아 온 순간의 사본입니다. 그래서 받아 오는 데 시간이 걸리고 실패할 수도 있으며, 관리자가 가격을 고치면 화면이 모르는 사이에 낡고, 같은 목록을 여러 화면이 함께 씁니다. 이렇게 원본이 서버에 있고 화면은 받아 온 사본을 잠시 들고 있는 데이터를 서버 상태라고 부릅니다. 검색어처럼 화면 안에서 생기고 화면 안에서만 바뀌는 값은 클라이언트 상태라고 부릅니다.

### 불러오는 중, 실패, 받은 목록을 한 값에 담습니다

서버 상태를 화면에 그리려면 응답을 기다리는 동안, 요청이 실패했을 때, 목록을 받았을 때 보여 줄 화면이 각각 있어야 합니다. 세 경우를 `isLoading`, `error`, `products` state 셋으로 따로 두면 `isLoading`을 `false`로 돌리는 줄을 한 곳에서 빠뜨렸을 때 로딩 표시와 실패 문구가 함께 보이는 화면이 생깁니다. `status` 하나에 지금이 어느 경우인지 적고, 그 경우에만 있는 값을 같은 객체에 담으면 그런 조합이 생길 수 없습니다.

```ts
type ProductsState =
  | { status: 'loading' }
  | { status: 'error'; error: Error }
  | { status: 'success'; products: Product[] };
```

`useProducts`는 분류를 받아 그 분류의 상품을 서버에서 받고 `ProductsState`를 돌려주는 훅입니다. `fetchProducts(category)`는 서버에 요청을 보내고, 응답이 오면 상품 배열로 이행되는 Promise를 돌려줍니다.

```tsx
function useProducts(category: string): ProductsState {
  const [state, setState] = useState<ProductsState>({ status: 'loading' });

  useEffect(() => {
    let ignore = false;
    setState({ status: 'loading' });
    fetchProducts(category)
      .then((products) => {
        if (!ignore) setState({ status: 'success', products });
      })
      .catch((error) => {
        if (!ignore) setState({ status: 'error', error });
      });
    return () => {
      ignore = true;
    };
  }, [category]);

  return state;
}
```

사용자가 '주방' 탭을 누르고 응답이 오기 전에 '전자기기' 탭을 누르면 두 요청이 함께 진행됩니다. '주방' 응답이 더 늦게 오면, `ignore`가 없을 때는 마지막에 실행된 `setState`가 '주방' 목록을 넣어 '전자기기' 탭에 주방 상품이 보입니다. 앞서 보낸 요청의 응답이 늦게 도착해 나중 요청의 결과를 덮는 문제를 경쟁 상태(race condition)라고 합니다. 탭이 바뀌면 React가 '주방' effect의 정리 함수를 불러 그 effect의 `ignore`를 `true`로 바꾸므로, 늦게 온 '주방' 응답은 `setState`까지 가지 못합니다. 개발 모드에서 첫 렌더링 때 요청이 두 번 나가도 같은 까닭으로 화면에는 두 번째 응답만 쓰입니다. 요청 자체를 끊는 AbortController와 늦은 응답의 시간 순서는 학습 페이지 l03에서 자세히 다룹니다.

### 직접 만든 훅은 받은 목록을 한곳에 모아 두지 않습니다

`useProducts`는 부를 때마다 자기 state를 따로 만들기 때문에 아래 일은 하지 않습니다.

- 같은 분류를 화면 두 곳에서 `useProducts('주방')`으로 부르면 요청이 두 번 나가고, 두 곳이 받은 목록을 따로 들고 있어서 한 곳만 새로 받으면 두 곳의 목록이 달라집니다.
- '주방'에서 '전자기기'로 갔다가 '주방'으로 돌아오면, 조금 전에 받은 목록이 있는데도 불러오는 중 화면부터 다시 보입니다.
- 목록에 재고 수를 함께 보여 준다면, 장바구니에 담아 서버의 재고가 줄어도 받아 둔 목록은 담기 전 재고를 보여 줍니다.
- 요청이 한 번 실패하면 사용자가 다른 탭을 눌렀다가 돌아올 때까지 실패 화면에 머뭅니다.

이 일을 직접 하려면 받은 데이터를 컴포넌트 밖 한곳에 모아 두고, 무엇을 요청했는지로 칸을 나눠 꺼내 써야 합니다. 아래 코드는 그 가운데 같은 요청을 한 번만 보내는 부분만 만든 것입니다. `getCachedProducts`는 분류마다 키를 만들어 `cache`에 Promise를 담고, 같은 키로 다시 부르면 서버에 가지 않고 담아 둔 Promise를 돌려줍니다. 실행하기 전에 첫 줄에 찍힐 요청 수를 적어 보세요.

```js
const cache = new Map();
let requests = 0;

function fetchProducts(category) {
  requests += 1;
  return new Promise((resolve) => setTimeout(() => resolve([`${category} 상품`]), 100));
}

function getCachedProducts(category) {
  const key = JSON.stringify(['products', category]);
  if (!cache.has(key)) cache.set(key, fetchProducts(category));
  return cache.get(key);
}

Promise.all([getCachedProducts('주방'), getCachedProducts('주방'), getCachedProducts('전자기기')]).then((lists) => {
  console.log('요청', requests);
  console.log(lists.map((list) => list[0]).join(', '));
});
```

첫 줄에 '요청 2'가 찍히고, 둘째 줄에 '주방 상품, 주방 상품, 전자기기 상품'이 찍힙니다. '주방'을 두 번 불렀지만 둘째 부름은 첫 부름이 담아 둔 Promise를 받아서 같은 응답을 나눠 씁니다. 이 캐시는 한 번 받은 목록을 다시 받지 않고, 요청이 실패하면 거부된 Promise를 담아 둔 채 계속 돌려줍니다. 서버 상태를 제대로 다루려면 언제 다시 받을지, 실패하면 몇 번 다시 보낼지, 아무도 쓰지 않는 데이터를 언제 지울지까지 정해야 합니다. React Query(TanStack Query)는 이 일을 맡아 주는 라이브러리입니다.

### React Query는 키마다 캐시를 두고 다시 받을 때를 정합니다

React Query가 받아 온 데이터를 나눠 담는 칸의 이름으로 쓰는 배열을 쿼리 키라고 부릅니다. 앞 코드의 `['products', category]`처럼 요청에 쓰는 값을 모두 쿼리 키에 넣어야 분류가 바뀔 때 다른 칸을 씁니다. React Query v5는 쿼리 키마다 기본으로 아래처럼 동작합니다.

- 상품 목록과 상품 수 배지처럼 같은 쿼리 키를 쓰는 컴포넌트 여럿이 함께 화면에 나타나도 요청은 한 번 나가고, 받은 데이터를 함께 씁니다. 그 키의 데이터를 다시 받으면 그 키를 쓰는 컴포넌트가 모두 새 데이터로 바뀝니다.
- 받은 데이터를 얼마 동안 최신으로 볼지는 `staleTime`으로 정합니다. 기본값이 0이라서 받은 즉시 낡은 데이터로 봅니다. 낡은 데이터는 그 키를 쓰는 컴포넌트가 새로 화면에 나타나거나, 브라우저 창에 다시 초점이 오거나, 네트워크가 다시 이어질 때 뒤에서 다시 받고, 그동안 화면에는 캐시의 데이터를 먼저 보여 줍니다. '주방' 탭으로 돌아오면 쿼리 키가 다시 `['products', '주방']`이 되어 불러오는 중 화면 없이 조금 전 목록이 바로 보이고, 새 목록이 오면 바뀝니다.
- 아무 컴포넌트도 쓰지 않는 키의 데이터는 5분 동안 캐시에 남았다가 지워집니다. 이 시간은 `gcTime`으로 바꿉니다.
- 실패한 요청은 실패 화면을 보여 주기 전에 세 번 더 보내고, 다시 보낼 때마다 기다리는 시간을 늘립니다.

`staleTime`을 5분으로 늘리면 받은 뒤 5분 동안은 컴포넌트가 다시 나타나도 다시 받지 않아 요청이 줄어듭니다. 그 대신 이 앱에서 데이터를 바꾼 뒤에도 그 5분 동안은 옛 목록이 남으므로, 데이터를 바꾸는 요청을 보낸 뒤에는 그 데이터가 든 키를 낡았다고 표시해서 다시 받게 합니다. 이렇게 표시하는 일을 무효화라고 하고, React Query에서는 캐시를 다루는 `queryClient` 객체에서 `queryClient.invalidateQueries({ queryKey: ['products'] })`처럼 무효화할 키를 적어 실행합니다. 무효화는 `staleTime`과 관계없이 낡았다고 표시하고, 그 키를 지금 화면에서 쓰고 있으면 바로 다시 받습니다. `['products']`로 무효화하면 `['products', '주방']`처럼 그 배열로 시작하는 키가 모두 낡은 것으로 표시됩니다. 장바구니에 담는 요청이 성공한 뒤 `['products']`를 무효화하면 목록을 다시 받아 줄어든 재고가 보입니다.

```figure
파일: assets/7c-1.gif
캡션: 그림 7C-1. 같은 쿼리 키는 요청 하나를 함께 쓰고, 돌아온 탭은 캐시의 목록을 먼저 보여 준 뒤 뒤에서 다시 받습니다.
프레임:
1. 왼쪽에 "탭: 주방"과 컴포넌트 칸 둘("목록", "상품 수 배지"), 둘 다 "불러오는 중". 두 칸의 화살표가 가운데 캐시 칸 ['products', '주방'](불러오는 중) 하나로 모이고, 캐시 칸에서 오른쪽 서버 칸으로 화살표 하나. 위에 "요청 1번". (1600ms)
2. 서버에서 캐시 칸으로 초록 화살표. 캐시 칸이 "주방 목록"으로 채워져 초록이 되고 두 컴포넌트 칸에 "주방 목록". (1600ms)
3. "탭: 전자기기". 캐시에 ['products', '전자기기'] 칸이 새로 생겨 서버로 화살표. '주방' 칸은 흐린 색에 "쓰는 곳 없음, 5분 뒤 지움" 꼬리표. 두 컴포넌트 칸은 "불러오는 중". (1800ms)
4. "탭: 주방". '주방' 칸이 다시 초록이 되고 두 컴포넌트 칸에 "주방 목록"이 바로 보임. '주방' 칸에서 서버로 점선 화살표, 서버 칸 아래에 "뒤에서 다시 받기", "staleTime 0" 두 줄. '전자기기' 칸은 흐린 색. (2200ms)
```

### 서버 상태와 전역 상태는 따로 둡니다

여러 컴포넌트가 함께 읽는 값이 모두 서버 상태는 아닙니다. 화면 테마, 고른 언어, 비교하려고 담아 둔 상품 id처럼 서버에 없고 컴포넌트 트리 곳곳에서 함께 읽고 바꾸는 클라이언트 상태를 전역 상태라고 부릅니다. 전역 상태는 React의 Context에 두거나, Redux나 Zustand처럼 상태를 컴포넌트 밖에 모아 두는 라이브러리에 둡니다. 이런 라이브러리가 상태를 모아 두는 객체를 store라고 부릅니다.

- Context는 props를 거치지 않고 아래 컴포넌트에 값을 건네는 React 기능입니다. 위쪽 컴포넌트가 Context의 Provider로 값을 넘기면 그 아래 어느 컴포넌트든 `useContext`로 그 값을 읽습니다. Provider에 넘긴 값이 바뀌면 그 Context를 읽는 컴포넌트가 모두 다시 렌더링되고, props가 같으면 렌더링을 건너뛰게 하는 `memo`로 그 컴포넌트를 감싸 두어도 막지 못합니다. 그래서 테마나 언어처럼 드물게 바뀌는 값에 맞습니다.
- store를 쓰는 컴포넌트는 store 전체에서 필요한 조각만 골라 돌려주는 selector 함수를 넘겨 값을 읽습니다. 고른 조각이 바뀔 때만 그 컴포넌트가 다시 렌더링되므로, 자주 바뀌고 컴포넌트마다 다른 조각을 읽는 값에 맞습니다.

서버에서 받은 상품 목록을 store에 복사해 두면 첫 절의 `filtered`처럼 서버의 원본과 store의 사본 두 벌이 생깁니다. 언제 다시 받을지, 실패하면 어떻게 할지, 늦게 온 응답을 어떻게 버릴지도 store 코드에서 다시 짜야 합니다. 서버 상태는 React Query 같은 캐시에 두고, Context나 store에는 서버에 없는 클라이언트 상태만 둡니다.

```figure
파일: assets/7c-2.png
캡션: 그림 7C-2. 계산할 수 있는 값은 어디에도 저장하지 않고, 서버에서 받은 데이터는 서버 상태 캐시에만 둡니다.
내용: 가로로 칸 넷. "렌더링 중 계산"(점선 테두리, visible, 결과 개수, 고른 상품 객체, 아래에 "저장하지 않음"), "컴포넌트 state"(query, selectedId), "전역 상태"(Context, store, 테마, 언어, 비교함 id), "서버 상태 캐시"(React Query, ['products', category]). 마지막 칸 아래 "서버" 칸으로 화살표. 아래 왼쪽에 빨간 글자 "같은 데이터를 두 칸에 복사하지 않습니다".
```

## 면접에서는 이렇게 이어집니다

꼬리 질문 사슬 7-A는 이 페이지의 앞 두 절을 바탕으로, 걸러 낸 목록을 state로 둘지 계산할지, effect가 필요한 일과 필요 없는 일, 개발 모드에서 effect가 두 번 실행되는 이유를 묻습니다. 사슬 7-B는 셋째 절을 바탕으로 React Query를 쓴 이유를 겪은 문제로 묻고, `staleTime`과 무효화, 전역 상태를 Context와 store 가운데 어디에 둘지로 이어집니다. 라이브 코딩 미션 w01은 첫 절의 계산할 값으로 상품 검색을 붙이고, w03은 둘째 절의 정리 함수와 셋째 절의 상태 모양으로 거래내역 화면을 고치며, w07은 서버에 바꾼 값을 보낸 뒤 화면의 목록을 다시 맞춥니다.
