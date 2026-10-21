## 면접관은 무엇을 보았나요

- 버튼 이름을 바꿀 때 글자만 바꿨는지, 아니면 `aria-label` 같은 속성을 더했는지 봅니다.
- 두 버튼이 같은 state 를 바꾼다는 것을 말로 설명했는지 봅니다.

## 모범 답안

```tsx
export function App() {
  const [count, setCount] = useState(0);
  return (
    <main>
      <h1>횟수 세기</h1>
      <p>지금까지 {count}번</p>
      <button type="button" onClick={() => setCount((n) => n + 1)}>더하기</button>
      <button type="button" onClick={() => setCount(0)}>초기화</button>
    </main>
  );
}
```

## 단계마다 무엇을 바꿨나요

1단계에서는 버튼 안의 글자를 "더하기"로 바꿨습니다. `setCount(count + 1)`은 그대로 두어도 검사를 통과하지만, 모범 답안은 지금 값을 받아 1 더하는 함수를 넘겼습니다. 한 이벤트에서 두 번 부르더라도 두 번 모두 반영되기 때문입니다.

2단계에서는 `setCount(0)`을 부르는 버튼을 하나 더 두었습니다. 두 버튼이 같은 state 를 바꾸므로 어느 쪽을 눌러도 같은 `<p>`가 다시 그려집니다.
