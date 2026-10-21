import { useState } from 'react';

export function App() {
  const [count, setCount] = useState(0);
  return (
    <main>
      <h1>횟수 세기</h1>
      <p>지금까지 {count}번</p>
      <button type="button" onClick={() => setCount(count + 1)}>
        누르기
      </button>
    </main>
  );
}
