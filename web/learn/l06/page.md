# React 렌더링과 key

React 화면에서 버튼을 누르면 React는 컴포넌트 함수를 다시 불러 새 화면을 계산하고, 앞 화면과 달라진 곳만 DOM에 고칩니다. 이 페이지는 장바구니 화면 하나로 그 과정을 따라갑니다. 첫 절은 state가 바뀐 뒤 React가 렌더링과 커밋을 차례로 하는 모습과 어떤 컴포넌트가 다시 렌더링되는지를, 둘째 절은 목록의 `key`가 행을 알아보는 방법과 `key`를 잘못 줬을 때 입력칸의 글자가 다른 상품으로 옮겨 가는 버그를, 셋째 절은 `memo`로 다시 렌더링을 건너뛰는 조건과 쓸 만한 때를, 넷째 절은 state를 바꾸는 함수를 부른 직후에 state가 어떤 값인지와 여러 번 부른 결과를 React가 모아서 처리하는 방법을 다룹니다. 끝까지 읽으면 꼬리 질문 사슬 6-A와 6-B의 질문, 그리고 이 페이지에서 실행 결과를 예상해 보는 문제 두 개에 답할 수 있습니다.

## 화면이 바뀔 때 React는 무엇을 하나요

장바구니 화면 맨 위에는 담은 상품 수를 보여 주는 머리글과 배송 요청 사항을 적는 입력칸이 있습니다. 화면 전체를 그리는 `CartPage`가 담은 상품 배열을 `items` state로 들고 있고, 머리글을 그리는 `CartHeader`는 상품 수를 `count` props로 받습니다. 이 페이지의 코드는 모두 아래 타입과 상품 셋을 씁니다.

```ts
type CartItem = { id: string; name: string; price: number };

const INITIAL_ITEMS: CartItem[] = [
  { id: 'c1', name: '텀블러', price: 15000 },
  { id: 'c2', name: '머그컵', price: 9000 },
  { id: 'c3', name: '드립백 세트', price: 12000 },
];
```

### set 함수를 부르면 렌더링과 커밋이 차례로 일어납니다

`useState`가 돌려주는 배열의 두 번째 값, 아래 코드의 `setItems` 같은 함수를 이 페이지에서는 set 함수라고 부릅니다. 아래 `CartPage`의 [맨 위 상품 빼기]는 `setItems`에 맨 앞 상품을 뺀 새 배열을 넘기고, `CartHeader`는 자기가 불릴 때마다 콘솔에 한 줄을 찍습니다. 입력칸에 '문 앞에 놓아 주세요'를 적은 뒤 [맨 위 상품 빼기]를 누르면 입력칸의 글자가 어떻게 될지 예상해 보세요.

```tsx
import { useState } from 'react';

function CartHeader({ count }: { count: number }) {
  console.log('CartHeader 렌더링', count);
  return (
    <header>
      <h2>장바구니 {count}개</h2>
      <input placeholder="배송 요청 사항" />
    </header>
  );
}

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>(INITIAL_ITEMS);
  return (
    <>
      <CartHeader count={items.length} />
      <button onClick={() => setItems(items.slice(1))}>맨 위 상품 빼기</button>
    </>
  );
}
```

머리글은 '장바구니 2개'로 바뀌고, 입력칸에는 '문 앞에 놓아 주세요'가 남습니다. set 함수는 state를 그 자리에서 고치지 않고, 바뀐 state로 화면을 다시 계산해 달라고 React에 요청합니다.

React가 컴포넌트 함수를 불러 화면에 무엇이 보여야 하는지 계산하는 일을 렌더링이라고 합니다. 요청을 받은 React는 state가 바뀐 `CartPage`를 다시 부르고, `CartPage`가 돌려준 JSX 안에 있는 `CartHeader`도 새 `count`로 부릅니다. 그래서 콘솔에는 처음 화면이 열릴 때 찍힌 'CartHeader 렌더링 3' 아래에 'CartHeader 렌더링 2'가 찍힙니다. 이 페이지의 콘솔 줄 수는 `StrictMode` 없이 센 것이고, 개발 서버에서 `StrictMode`로 감싼 앱은 개발 중에만 컴포넌트 함수를 한 번 더 부르므로 같은 줄이 두 번씩 찍힐 수 있습니다. 렌더링하는 동안 React는 DOM에 손대지 않고, 새로 계산한 결과를 앞 렌더링의 결과와 비교해 달라진 곳만 알아 둡니다.

렌더링에서 찾은 차이를 실제 DOM에 고치는 차례를 커밋 단계라고 합니다. 이번 비교에서 달라진 곳은 `<h2>` 안의 숫자 하나라서, React는 커밋 단계에서 그 글자를 3에서 2로만 바꿉니다. `<input>`은 앞 렌더링과 같은 자리에 같은 태그로 있어서 React가 DOM 노드를 새로 만들지 않고, 사용자가 적은 글자도 그 노드에 남습니다. 커밋이 끝나면 브라우저가 바뀐 DOM으로 화면을 다시 칠합니다.

```figure
파일: assets/6a-1.gif
캡션: 그림 6A-1. set 함수가 렌더링을 요청하면 React는 새 결과를 앞 결과와 비교하고, 커밋 단계에서 달라진 숫자만 DOM에 고칩니다.
프레임:
1. 위에 "[맨 위 상품 빼기] 클릭" 글자. 왼쪽부터 단계 칸 셋 "요청", "렌더링", "커밋 단계"를 화살표로 이음. "요청" 칸이 켜지고 아래에 setItems(items.slice(1)) 와 "다시 렌더링을 React에 요청함". 오른쪽 화면 칸에 '장바구니 3개'와 입력칸 '문 앞에 놓아 주세요'. (1400ms)
2. "렌더링" 칸이 켜짐. 가운데에 "앞 결과" 칸과 "새 결과" 칸을 나란히 둠. 앞 결과 <h2>장바구니 3개</h2>, 새 결과 <h2>장바구니 2개</h2>. 두 숫자에 주황 테두리, 새 결과 칸에 "다름" 꼬리표, 두 <input /> 줄 끝에 회색 "같음". 화면 칸은 앞 프레임과 같음. (2000ms)
3. "커밋 단계" 칸이 켜짐. 화면 칸의 숫자만 2로 바뀌고 그 숫자에 초록 테두리. 입력칸의 글자는 남고 아래에 "노드를 새로 만들지 않음" 꼬리표. (2200ms)
```

### 부모가 다시 렌더링되면 자식도 다시 렌더링됩니다

`CartPage`에 쿠폰 코드를 적는 입력칸을 더해 봅니다. 쿠폰 코드는 `coupon` state에 담고, 입력칸에 글자를 칠 때마다 `setCoupon`을 부릅니다.

```tsx
export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>(INITIAL_ITEMS);
  const [coupon, setCoupon] = useState('');
  return (
    <>
      <CartHeader count={items.length} />
      <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="쿠폰 코드" />
      <button onClick={() => setItems(items.slice(1))}>맨 위 상품 빼기</button>
    </>
  );
}
```

쿠폰 입력칸에 'A'를 치면 콘솔에 'CartHeader 렌더링 3'이 한 줄 더 찍힙니다. `coupon`이 바뀐 `CartPage`를 React가 다시 부르면, `CartPage`가 돌려준 JSX 안의 `CartHeader`도 함께 부르기 때문입니다. `CartHeader`가 받은 `count`는 앞과 같은 3이어서 새 결과에서 달라진 곳이 없고, 커밋 단계에서 머리글의 DOM은 바뀌지 않습니다.

컴포넌트는 아래 세 경우에 다시 렌더링됩니다.

- 그 컴포넌트의 state가 set 함수로 바뀔 때.
- 부모 컴포넌트가 다시 렌더링될 때. React는 props가 앞과 같은지 따지지 않고 자식 컴포넌트를 모두 다시 부릅니다.
- 그 컴포넌트가 `useContext`로 읽는 Context의 값이 바뀔 때.

set 함수에 넘긴 값이 지금 state와 `Object.is`로 같으면 React는 그 컴포넌트와 자식의 다시 렌더링을 건너뜁니다. 그래서 배열이나 객체 state를 직접 고친 뒤 같은 배열을 다시 넘기면 화면이 바뀌지 않습니다. 아래 `addGift`는 [사은품 담기]를 누르면 불리는 함수로, `items`에 사은품을 `push`로 넣고 같은 배열을 `setItems`에 넘깁니다.

```tsx
function addGift() {
  items.push({ id: 'g1', name: '사은품 컵받침', price: 0 });
  setItems(items);
}
```

[사은품 담기]를 누르면 배열에는 상품이 넷 들어 있지만, `setItems`가 받은 배열이 지금 state와 같은 배열이라서 React는 다시 렌더링하지 않고 머리글에는 '장바구니 3개'가 남습니다. `push`는 `INITIAL_ITEMS` 배열까지 고쳐서, 이 상품 배열로 처음 값을 정하는 다른 화면도 상품 넷으로 시작하게 됩니다. state를 바꿀 때는 `setItems([...items, { id: 'g1', name: '사은품 컵받침', price: 0 }])`처럼 새 배열을 만들어 넘깁니다.

## 목록의 key는 React에게 무엇을 알려 주나요

앞 절의 배송 요청 사항 입력칸은 다시 렌더링한 뒤에도 같은 자리에 같은 태그로 있어서 글자가 남았습니다. React는 컴포넌트와 태그를 화면 트리 안의 자리로 알아보고, 앞 렌더링과 같은 자리에 같은 컴포넌트가 있으면 그 컴포넌트의 state를 남겨 둡니다. 배열을 `map`으로 그린 목록에서는 배열 안의 순서가 자리가 되는데, 각 항목에 `key`를 주면 React는 순서 대신 `key`로 앞 렌더링의 항목과 짝을 맞춥니다.

### index를 key로 쓰면 요청 사항이 다른 상품으로 옮겨 갑니다

이번에는 장바구니에 담은 상품을 한 줄씩 보여 주는 목록을 봅니다. `CartRow`는 상품마다 요청 사항을 적는 입력칸을 두고, 적은 글자를 자기 `note` state에 담습니다. `CartList`는 배열의 순서 번호 `index`를 `key`로 줍니다.

```tsx
function CartRow({ item, onRemove }: { item: CartItem; onRemove: (id: string) => void }) {
  const [note, setNote] = useState('');
  return (
    <li>
      {item.name}
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={`${item.name} 요청 사항`} />
      <button onClick={() => onRemove(item.id)}>{item.name} 빼기</button>
    </li>
  );
}

function CartList() {
  const [items, setItems] = useState<CartItem[]>(INITIAL_ITEMS);

  function remove(id: string) {
    setItems(items.filter((item) => item.id !== id));
  }

  return (
    <ul>
      {items.map((item, index) => (
        <CartRow key={index} item={item} onRemove={remove} />
      ))}
    </ul>
  );
}
```

텀블러 입력칸에 '파란색으로'를, 드립백 세트 입력칸에 '디카페인'을 적은 뒤 [텀블러 빼기]를 누른다고 해 봅니다. 남은 두 행의 입력칸에 무엇이 보일지 적어 보세요.

텀블러 행은 사라지지만, 머그컵 행의 입력칸에 '파란색으로'가 보이고 드립백 세트 행의 입력칸은 비어 있습니다. 빼기 전에는 텀블러, 머그컵, 드립백 세트의 `key`가 0, 1, 2였고, 빼고 난 새 배열에서는 머그컵이 0, 드립백 세트가 1입니다. React는 `key`가 0인 행을 앞 렌더링의 `key` 0 행과 같은 `CartRow`로 보고, 텀블러 때 만든 `note` state('파란색으로')를 남긴 채 `item` props만 머그컵으로 바꿉니다. `key` 1 행도 머그컵 때의 빈 `note`를 남긴 채 드립백 세트를 받고, 새 배열에 없는 `key` 2 행은 React가 지우면서 그 행이 들고 있던 '디카페인'도 함께 버립니다. 입력칸의 안내 글은 `item`에서 만들어서 '머그컵 요청 사항'으로 바뀌지만, 칸 안의 글자는 `note` state라서 바뀌지 않습니다.

```figure
파일: assets/6b-1.gif
캡션: 그림 6B-1. index를 key로 주면 텀블러를 뺀 뒤 머그컵이 텀블러 행의 state를 넘겨받고, id를 key로 주면 요청 사항이 상품을 따라갑니다.
프레임:
1. 왼쪽 열 "key={index}", 오른쪽 열 "key={item.id}". 두 열 모두 행 셋(텀블러 '파란색으로', 머그컵 빈칸, 드립백 세트 '디카페인'). 행마다 왼쪽에 key 꼬리표(왼쪽 0, 1, 2 / 오른쪽 c1, c2, c3). (1600ms)
2. 위 글자 "[텀블러 빼기] 클릭: 새 배열의 key". 두 열 모두 텀블러 행에 빨간 줄. 남는 행의 꼬리표 옆에 새 key 를 노란 글자로 적음(왼쪽 →0, →1 / 오른쪽 →c2, →c3). (1800ms)
3. 위 글자 "React가 key로 짝지은 결과". 왼쪽 열: key 0 행이 머그컵이 되고 입력칸에 '파란색으로'가 남아 빨간 테두리, key 1 행은 드립백 세트에 빈칸, key 2 행은 "(지워짐)"과 흐린 '디카페인'에 회색 줄. 오른쪽 열: c1 행이 "(지워짐)"에 회색 줄, c2 머그컵 빈칸, c3 드립백 세트 '디카페인'에 초록 테두리. (2400ms)
```

### 데이터의 id를 key로 줍니다

`key={item.id}`로 바꾸면 같은 순서로 입력하고 눌렀을 때 텀블러 행만 사라지고, 머그컵 입력칸은 비어 있고 드립백 세트 입력칸에는 '디카페인'이 남습니다. React가 `c2`, `c3`을 앞 렌더링의 `c2`, `c3` 행과 짝지어 그 행의 state를 남기고, 새 배열에 없는 `c1` 행만 지우기 때문입니다. React 문서는 `key`에 아래 규칙을 둡니다.

- 같은 배열 안의 형제끼리는 `key`가 겹치지 않아야 합니다. 다른 배열에서는 같은 `key`를 써도 됩니다.
- 한 항목의 `key`는 렌더링이 바뀌어도 같아야 합니다. 서버가 준 id처럼 데이터에 들어 있는 값을 씁니다.
- 렌더링하면서 `key={Math.random()}`처럼 새로 만들면 렌더링할 때마다 모든 `key`가 달라집니다. React는 행을 모두 지우고 새로 만들어서 느려지고, 입력칸에 적은 글자도 사라집니다. 이 목록 위에 앞 절의 쿠폰 입력칸을 두면, 쿠폰을 한 글자 칠 때마다 모든 행의 요청 사항이 지워집니다.

`index`를 `key`로 써도 되는 목록은 항목이 끼어들거나 빠지거나 순서가 바뀌지 않는 목록입니다. 항목이 빠지는 장바구니처럼 순서가 바뀌는 목록에서는 앞의 버그가 생깁니다. `key`는 React가 짝을 맞출 때만 쓰고 컴포넌트의 props로 넘어가지 않으므로, 컴포넌트 안에서 id가 필요하면 `<CartRow key={item.id} id={item.id} … />`처럼 따로 넘깁니다.

### key를 바꿔 state를 처음으로 되돌립니다

같은 자리에 같은 컴포넌트가 있으면 state가 남는다는 규칙은 처음 값으로 되돌리고 싶을 때 방해가 됩니다. 배송지를 집에서 회사로 바꾸면 집으로 받을 때 적은 요청 사항을 비우고 싶은데, `DeliveryNote`가 같은 자리에 있으면 `note` state가 남습니다. 이럴 때 `key`에 배송지 id를 줍니다.

```tsx
function DeliveryNote() {
  const [note, setNote] = useState('');
  return <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="배송 요청 사항" />;
}

function Checkout() {
  const [addressId, setAddressId] = useState('home');
  return (
    <>
      <button onClick={() => setAddressId('office')}>회사로 받기</button>
      <DeliveryNote key={addressId} />
    </>
  );
}
```

[회사로 받기]를 누르면 `key`가 'home'에서 'office'로 바뀝니다. React는 `key`가 다른 `DeliveryNote`를 다른 컴포넌트로 보고, 앞 컴포넌트를 state와 함께 지운 뒤 새 컴포넌트를 만들어서 `note`가 빈 글자부터 다시 시작합니다. `key`는 목록 밖의 컴포넌트에도 줄 수 있고, 같은 부모 아래의 형제끼리만 겹치지 않으면 됩니다.

## memo는 언제 다시 렌더링을 막아 주나요

첫 절에서 쿠폰 코드를 칠 때 `count`가 바뀌지 않은 `CartHeader`까지 다시 렌더링되었습니다. 머리글은 가벼워서 문제가 없지만, 장바구니 아래에 추천 상품 300개를 그리는 `RecommendList`를 두면 쿠폰 코드를 칠 때마다 300줄을 다시 계산합니다. `RecommendList`는 추천 상품을 담은 배열 `RECOMMENDED`를 그리고, [담기]를 누르면 `onAdd` props로 받은 함수에 그 상품을 넘깁니다. 이 절의 `CartPage`는 코드를 줄이려고 머리글을 `CartHeader` 대신 `<h2>` 한 줄로 그립니다.

```tsx
function RecommendList({ onAdd }: { onAdd: (item: CartItem) => void }) {
  console.log('RecommendList 렌더링');
  return (
    <ul>
      {RECOMMENDED.map((item) => (
        <li key={item.id}>
          {item.name} <button onClick={() => onAdd(item)}>담기</button>
        </li>
      ))}
    </ul>
  );
}

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>(INITIAL_ITEMS);
  const [coupon, setCoupon] = useState('');
  return (
    <>
      <h2>장바구니 {items.length}개</h2>
      <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="쿠폰 코드" />
      <RecommendList onAdd={(item) => setItems([...items, item])} />
    </>
  );
}
```

쿠폰 입력칸에 'SALE'을 치면 'RecommendList 렌더링'이 네 줄 더 찍힙니다. 글자마다 `CartPage`가 다시 렌더링되고, 그때마다 React가 `RecommendList`를 불러 추천 상품 300줄을 다시 계산한 뒤 앞 결과와 비교합니다. 추천 상품은 바뀌지 않았으므로 커밋 단계에서 고칠 DOM은 없습니다.

### memo는 props를 얕은 비교로 견줍니다

`memo`는 컴포넌트를 감싸서, 부모가 다시 렌더링될 때 새 props가 앞 렌더링의 props와 같으면 그 컴포넌트의 렌더링을 건너뛰게 하는 함수입니다. props가 같은지는 props 객체의 키마다 앞 값과 새 값을 `Object.is`로 비교해서 정하는데, 이렇게 객체 안을 한 단계만 들여다보며 값을 하나씩 견주는 방식을 얕은 비교라고 부릅니다. 아래 코드는 앞의 `RecommendList`를 고치지 않고 `memo`로 감싸기만 합니다.

```tsx
import { memo } from 'react';

const RecommendList = memo(function RecommendList({ onAdd }: { onAdd: (item: CartItem) => void }) {
  console.log('RecommendList 렌더링');
  return (
    <ul>
      {RECOMMENDED.map((item) => (
        <li key={item.id}>
          {item.name} <button onClick={() => onAdd(item)}>담기</button>
        </li>
      ))}
    </ul>
  );
});
```

`CartPage`를 그대로 두고 'SALE'을 치면 'RecommendList 렌더링'이 여전히 네 줄 더 찍힙니다. 아래 코드는 얕은 비교를 흉내 낸 `sameProps` 함수로 props 세 쌍을 견줍니다. 실행하기 전에 세 줄에 무엇이 찍힐지 적어 보세요.

```js
function sameProps(prev, next) {
  const keys = Object.keys(next);
  if (keys.length !== Object.keys(prev).length) return false;
  return keys.every((key) => Object.is(prev[key], next[key]));
}

const addToCart = (item) => console.log(item.name);

console.log(sameProps({ title: '추천 상품', onAdd: addToCart }, { title: '추천 상품', onAdd: addToCart }));
console.log(sameProps({ title: '추천 상품', onAdd: addToCart }, { title: '추천 상품', onAdd: (item) => console.log(item.name) }));
console.log(sameProps({ ids: ['r1', 'r2'] }, { ids: ['r1', 'r2'] }));
```

`true`, `false`, `false`가 차례로 찍힙니다. 문자열 '추천 상품'은 글자가 같으면 `Object.is`로 같다고 나오지만, 함수와 배열은 같은 객체일 때만 같다고 나옵니다. 둘째 줄의 화살표 함수는 하는 일이 `addToCart`와 똑같아도 새로 만든 함수라서 `Object.is`가 `false`를 돌려주고, 셋째 줄의 두 배열도 따로 만든 배열이라서 `false`가 나옵니다. `CartPage`는 렌더링할 때마다 `(item) => setItems([...items, item])`라는 새 화살표 함수를 만들어 `onAdd`로 넘기므로, `memo`가 비교하는 `onAdd`는 매번 달라서 렌더링을 건너뛰지 못합니다.

### 넘기는 함수는 useCallback으로 같은 함수를 씁니다

`useCallback`은 함수와 의존성 배열을 받아, 의존성 배열의 값이 앞 렌더링과 같으면 앞 렌더링에서 만든 함수를 돌려주는 훅입니다.

```tsx
import { useCallback, useState } from 'react';

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>(INITIAL_ITEMS);
  const [coupon, setCoupon] = useState('');
  const handleAdd = useCallback((item: CartItem) => setItems([...items, item]), [items]);
  return (
    <>
      <h2>장바구니 {items.length}개</h2>
      <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="쿠폰 코드" />
      <RecommendList onAdd={handleAdd} />
    </>
  );
}
```

이제 'SALE'을 쳐도 'RecommendList 렌더링'은 처음 화면이 열릴 때 찍힌 한 줄뿐입니다. 쿠폰 코드만 바뀌고 `items`는 바뀌지 않아서, `useCallback`이 앞 렌더링에서 만든 `handleAdd`를 돌려주기 때문입니다. [담기]를 누르면 `items`가 바뀌어 `handleAdd`도 새 함수가 되고, `RecommendList`가 한 번 다시 렌더링됩니다. 넷째 절에서 이 의존성까지 없애는 방법을 봅니다.

```figure
파일: assets/6c-1.png
캡션: 그림 6C-1. 쿠폰 코드를 칠 때 RecommendList는 memo로 감싸고 같은 onAdd 함수를 받을 때만 렌더링을 건너뜁니다.
내용: 가로로 열 셋. 열 제목 "memo 없음", "memo, 새 화살표 함수", "memo, useCallback". 열마다 위에 "CartPage 다시 렌더링(coupon 바뀜)" 칸, 아래로 화살표 두 개가 "h2" 칸과 "RecommendList" 칸으로 이어짐. RecommendList 칸 안에 비교 줄 "onAdd 같음?" 과 답(첫 열 "비교 안 함", 둘째 열 "아니요", 셋째 열 "예"). 첫째·둘째 열의 RecommendList 칸은 빨간 테두리에 "다시 렌더링", 셋째 열은 초록 테두리에 "건너뜀".
```

### memo를 붙이기 전에 재 봅니다

`memo`를 모든 컴포넌트에 붙인다고 앱이 빨라지지는 않습니다. React 문서는 `memo`가 쓸 만한 때를 같은 props로 자주 다시 렌더링되고 그 렌더링이 오래 걸리는 컴포넌트로 좁히고, 다시 렌더링할 때 느껴지는 지연이 없으면 `memo`가 필요 없다고 적어 둡니다. 비교하는 데도 시간이 들고, 앞의 화살표 함수처럼 매번 새로 만드는 props가 하나만 섞여도 비교가 늘 실패합니다. 느린 곳은 React Developer Tools의 Profiler로 어느 컴포넌트가 오래 렌더링되는지 보고 찾고, 시간을 잴 때는 개발 서버 대신 운영 빌드로 잽니다. 그리고 `memo`는 부모가 넘긴 props만 비교하므로, 감싼 컴포넌트도 자기 state가 바뀌거나 `useContext`로 읽는 Context 값이 바뀌면 다시 렌더링됩니다.

`memo` 없이 다시 렌더링되는 범위를 줄일 수도 있습니다. 쿠폰 코드는 쿠폰 입력칸 말고는 아무도 읽지 않으므로, `coupon` state를 입력칸 컴포넌트 안으로 내리면 글자를 칠 때 `CouponInput`만 다시 렌더링되고 `CartPage`와 `RecommendList`는 불리지 않습니다.

```tsx
function CouponInput() {
  const [coupon, setCoupon] = useState('');
  return <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="쿠폰 코드" />;
}
```

React Compiler를 켠 프로젝트에서는 컴파일러가 컴포넌트마다 `memo`와 같은 일을 해 주므로 `memo`를 직접 붙일 일이 줄어듭니다.

## set 함수를 부른 직후에 state를 읽으면 무엇이 나오나요

이번에는 장바구니 행의 수량을 고르는 `QuantityPicker`를 봅니다. 수량은 `qty` state에 담고, [3개 더]를 누르면 `setQty(qty + 1)`을 세 번 부른 뒤 콘솔에 `qty`를 찍습니다. [3개 더]를 한 번 누르면 화면의 수량과 콘솔에 찍히는 값이 무엇일지 예상해 보세요.

```tsx
function QuantityPicker() {
  const [qty, setQty] = useState(1);

  function addThree() {
    setQty(qty + 1);
    setQty(qty + 1);
    setQty(qty + 1);
    console.log('클릭 직후', qty);
  }

  return (
    <>
      <span>{qty}개</span>
      <button onClick={addThree}>3개 더</button>
    </>
  );
}
```

화면에는 '2개'가 보이고 콘솔에는 '클릭 직후 1'이 찍힙니다. React는 렌더링할 때마다 `QuantityPicker` 함수를 새로 부르고, 그 렌더링의 `qty`는 `const`로 받은 값이라서 한 번 정해지면 바뀌지 않습니다. 처음 렌더링에서 만든 `addThree`는 그 렌더링의 `qty`인 1을 보므로, 세 줄 모두 `setQty(2)`를 부르는 것과 같습니다. set 함수는 다음 렌더링에서 쓸 값을 React에 맡길 뿐 지금 실행 중인 함수의 `qty` 변수를 고치지 않아서, 바로 다음 줄의 `console.log`도 1을 찍습니다.

`await`로 기다린 뒤에 읽어도 1이 나옵니다. 아래 함수는 `setQty`를 부르고 1초를 기다린 뒤 `qty`를 찍습니다.

```tsx
async function addOneLater() {
  setQty(qty + 1);
  await new Promise((resolve) => setTimeout(resolve, 1000));
  console.log('1초 뒤', qty);
}
```

1초 사이에 React는 수량 2로 다시 렌더링해서 화면에는 '2개'가 보이지만, 콘솔에는 '1초 뒤 1'이 찍힙니다. 다시 렌더링하면 새 `qty`를 받은 새 함수가 만들어지고, 이미 실행 중이던 `addOneLater`는 클릭한 렌더링의 `qty`를 계속 봅니다. 그래서 "set 함수가 비동기라서 늦게 바뀐다"는 설명만으로는 이 결과를 설명하지 못합니다.

### 앞 값으로 다음 값을 계산할 때는 업데이트 함수를 넘깁니다

set 함수에는 값 대신 함수를 넘길 수도 있습니다. 앞 state를 받아 다음 state를 돌려주는 이 함수를 업데이트 함수(updater function)라고 부릅니다.

```tsx
function addThree() {
  setQty((q) => q + 1);
  setQty((q) => q + 1);
  setQty((q) => q + 1);
  console.log('클릭 직후', qty);
}
```

이렇게 고치면 [3개 더]를 한 번 눌렀을 때 화면에 '4개'가 보이고, 콘솔에는 여전히 '클릭 직후 1'이 찍힙니다. React는 set 함수에 넘긴 값과 함수를 부른 순서대로 쌓아 두었다가, 다음 렌더링에서 지금 state부터 차례로 적용합니다. 값을 넘겼으면 그 값으로 바꾸고, 업데이트 함수를 넘겼으면 앞 항목까지 적용한 값을 그 함수에 넣어 나온 값으로 바꿉니다. 아래 코드는 이 처리를 흉내 낸 `nextState` 함수로, 쌓인 목록 세 개를 차례로 적용합니다. 실행하기 전에 세 줄에 찍힐 수를 적어 보세요.

```js
function nextState(current, queue) {
  return queue.reduce((value, update) => (typeof update === 'function' ? update(value) : update), current);
}

const qty = 1;
console.log(nextState(qty, [qty + 1, qty + 1, qty + 1]));
console.log(nextState(qty, [(q) => q + 1, (q) => q + 1, (q) => q + 1]));
console.log(nextState(qty, [qty + 5, (q) => q + 1, 42]));
```

2, 4, 42가 차례로 찍힙니다. 첫 줄은 2로 바꾸라는 값만 세 개 쌓여 2가 되고, 둘째 줄은 업데이트 함수가 1, 2, 3을 차례로 받아 4가 됩니다. 셋째 줄은 6으로 바꾼 뒤 업데이트 함수가 7을 만들지만, 마지막에 쌓인 값 42가 그 결과를 덮습니다. `QuantityPicker`에서 같은 세 줄을 한 클릭 안에 부르면 화면에도 2개, 4개, 42개가 보입니다.

```figure
파일: assets/6d-1.gif
캡션: 그림 6D-1. qty + 1을 세 번 넘기면 2로 바꾸라는 요청만 쌓이고, 업데이트 함수를 세 번 넘기면 앞 결과를 받아 하나씩 더해 4가 됩니다.
프레임:
1. 위 글자 "[3개 더] 한 번 클릭: 쌓인 요청". 왼쪽 열 "setQty(qty + 1) 세 번", 오른쪽 열 "setQty((q) => q + 1) 세 번". 열마다 위에 "지금 state 1" 칸, 아래에 쌓인 요청 세 칸(왼쪽 "2로 바꿈" 셋, 오른쪽 "q => q + 1" 셋). (1600ms)
2. 위 글자가 "[3개 더] 한 번 클릭 뒤 다음 렌더링"으로 바뀜. 두 열의 첫째 요청 칸이 켜지고 화살표 뒤에 결과(왼쪽 2, 오른쪽 1 → 2). (1400ms)
3. 둘째 요청 칸이 켜짐. 결과 왼쪽 2, 오른쪽 2 → 3. (1400ms)
4. 셋째 요청 칸이 켜짐. 결과 왼쪽 2, 오른쪽 3 → 4. 아래 화면 칸에 왼쪽 '2개'(빨간 테두리), 오른쪽 '4개'(초록 테두리). (2200ms)
```

업데이트 함수는 다음 렌더링 중에 실행되므로 받은 값으로 계산해 돌려주기만 하고, 그 안에서 state를 바꾸거나 요청을 보내지 않습니다. 개발 모드의 `StrictMode`는 이런 실수를 찾으려고 업데이트 함수를 두 번 부르고 그중 한 번의 결과만 씁니다. 클릭 한 번에 set 함수를 한 번만 부르는 코드라면 `setQty(qty + 1)`로 써도 결과가 같습니다. React는 사용자가 클릭할 때마다 앞 클릭의 결과로 다시 렌더링한 뒤에 다음 클릭을 처리하므로, 클릭을 시작할 때 읽은 `qty`는 앞 클릭이 반영된 값입니다.

셋째 절의 `handleAdd`도 업데이트 함수로 바꾸면 `items`를 읽지 않게 되어 의존성 배열을 비울 수 있습니다.

```tsx
const handleAdd = useCallback((item: CartItem) => setItems((prev) => [...prev, item]), []);
```

`handleAdd`가 처음 렌더링에서 만든 함수 하나로 남으므로, [담기]를 눌러 `items`가 바뀌어도 `RecommendList`는 다시 렌더링되지 않습니다.

### 묶음 렌더링은 set 함수 여러 번을 렌더링 한 번으로 모읍니다

`addThree`는 set 함수를 세 번 불렀지만 React는 다시 렌더링을 한 번만 했습니다. 이벤트 함수 안의 코드가 끝날 때까지 기다렸다가 그사이 부른 set 함수를 모아 다시 렌더링을 한 번만 하는 동작을 묶음 렌더링(batching)이라고 합니다. 일부 state만 바뀐 어중간한 화면이 그려지지 않고 렌더링 횟수도 줄어듭니다.

아래 `QuantitySaver`는 렌더링할 때마다 콘솔에 한 줄을 찍습니다. [1개 더]는 수량과 안내 문구를 함께 바꾸고, [저장]은 `save`가 돌려준 Promise를 기다린 뒤 두 state를 바꿉니다. `save(qty)`는 서버에 수량을 저장하고 저장된 수량으로 이행되는 Promise를 돌려준다고 봅니다.

```tsx
function QuantitySaver() {
  const [qty, setQty] = useState(1);
  const [message, setMessage] = useState('');
  console.log('QuantitySaver 렌더링');

  function addOne() {
    setQty(qty + 1);
    setMessage('저장 중');
  }

  async function saveNow() {
    const saved = await save(qty);
    setQty(saved);
    setMessage(`${saved}개 저장함`);
  }

  return (
    <>
      <span>{qty}개</span>
      <p>{message}</p>
      <button onClick={addOne}>1개 더</button>
      <button onClick={saveNow}>저장</button>
    </>
  );
}
```

[1개 더]를 누르면 'QuantitySaver 렌더링'이 한 줄 더 찍힙니다. [저장]을 누르면 응답이 온 뒤 `setQty`와 `setMessage`가 수량과 문구를 함께 바꾸는데, 두 업데이트가 렌더링 한 번으로 묶여서 이때도 한 줄만 더 찍힙니다. React 18부터는 `createRoot`로 띄운 앱이면 Promise의 `then`이나 `await` 뒤, `setTimeout` 콜백 안에서 부른 set 함수도 함께 묶습니다. React 17까지는 React가 부른 이벤트 함수 안에서만 묶었기 때문에, `await` 뒤에서 set 함수 두 개로 state 둘을 바꾸면 렌더링이 두 번 일어났습니다. 버튼을 두 번 누르면 클릭마다 따로 렌더링하고, 두 클릭을 한 번으로 묶지는 않습니다.

### 타이머 안에서 앞 값을 읽으면 첫 렌더링의 값에 머뭅니다

쿠폰을 받으면 남은 시간을 180초부터 1초씩 줄여 보여 주는 `CouponTimer`를 만든다고 해 봅니다. 화면이 열릴 때 타이머를 한 번 걸고 화면에서 빠질 때 멈추려고, 의존성 배열이 빈 effect에서 `setInterval`을 걸고 정리 함수에서 `clearInterval`을 부릅니다.

```tsx
function CouponTimer() {
  const [left, setLeft] = useState(180);

  useEffect(() => {
    const id = setInterval(() => setLeft(left - 1), 1000);
    return () => clearInterval(id);
  }, []);

  return <p>쿠폰 남은 시간 {left}초</p>;
}
```

이 화면은 1초 뒤 179초가 된 다음 계속 179초에 머뭅니다. effect는 첫 렌더링 뒤에 한 번만 실행되어서, `setInterval`에 넘긴 화살표 함수는 첫 렌더링의 `left`인 180을 계속 봅니다. 1초마다 `setLeft(179)`를 부르게 되고, 두 번째부터는 지금 state와 같은 179를 넘기므로 화면이 바뀌지 않습니다. `setLeft((l) => l - 1)`로 업데이트 함수를 넘기면 화살표 함수가 `left`를 읽지 않고 React가 쌓인 최신 값을 넣어 주므로, 3초 뒤에는 177초가 보입니다. 의존성 배열에 `left`를 넣어도 숫자는 줄어들지만, 1초마다 effect가 다시 실행되어 타이머를 멈추고 새로 거는 일이 되풀이됩니다.

## 면접에서는 이렇게 이어집니다

꼬리 질문 사슬 6-A는 이 페이지의 앞 세 절을 바탕으로, 쿠폰 코드를 칠 때 React가 무엇을 렌더링하고 무엇을 DOM에 고치는지에서 시작해 index를 `key`로 쓴 장바구니의 버그와 `memo`가 렌더링을 건너뛰지 못하는 까닭을 묻습니다. 사슬 6-B는 넷째 절을 바탕으로 set 함수를 부른 직후의 값, 업데이트 함수, 묶음 렌더링, 멈춰 버린 타이머를 묻습니다. 라이브 코딩 미션 w06(포인트 적립 내역)과 w08(알림 설정 화면)은 아직 준비 중입니다. 두 미션이 열리면 w06에서는 행이 이어 붙는 목록을, w08에서는 다시 렌더링되는 범위를 줄이는 코드를 직접 짭니다.
