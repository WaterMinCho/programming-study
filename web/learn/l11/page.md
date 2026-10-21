# 바꾸기 쉬운 코드와 테스트

라이브 코딩에서 요구를 다 고치고 나면 면접관은 코드의 모양을 묻기 시작합니다. 이 코드에 리뷰를 남긴다면 무엇을 적을지, 거의 같은 두 함수를 하나로 합칠지, 가끔 실패하는 테스트를 어떻게 고칠지 같은 질문입니다. 이 페이지는 광고 캠페인을 관리하는 화면 하나로 세 질문을 차례로 따라갑니다. 첫 절은 이름 바꾸기, 훅으로 떼기, props를 덜 넘기는 구조를 리뷰 의견으로 말하는 법을, 둘째 절은 합칠 코드와 나눠 둘 코드를 가르는 기준과 시간이 부족할 때 무엇부터 할지를, 셋째 절은 화면 테스트가 가끔 실패하는 까닭과 고치는 법을 다룹니다. 끝까지 읽으면 꼬리 질문 사슬 11-A, 11-B, 11-C의 질문과 이 페이지에서 실행 결과를 예상해 보는 문제 하나에 답할 수 있습니다.

## 리뷰 의견은 어떤 변경이 쉬워지는지로 말합니다

캠페인 목록 화면은 서버에서 캠페인 목록을 받아 이름과 예산을 표로 보여 주고, 위쪽의 [전체]와 [진행 중] 단추로 진행 중인 캠페인만 거를 수 있습니다. 예산을 고칠 권한이 있는 사용자에게는 줄마다 [예산 수정] 단추가 보입니다. 이 절의 코드는 모두 아래 타입을 씁니다. `getCampaigns()`는 캠페인 배열로 이행되는 Promise를 돌려주는 함수입니다.

```ts
type Campaign = { id: string; name: string; status: 'running' | 'paused'; budget: number };
```

동료가 이 화면을 아래 코드로 만들어 리뷰를 부탁했다고 해 봅니다. `CampaignPage`가 목록을 받아 거르고, `CampaignTable`이 표를 그리며, `CampaignRow`가 한 줄을 그립니다. effect 안의 `ignore`는 컴포넌트가 화면에서 빠진 뒤에 도착한 응답을 화면에 쓰지 않으려고 둔 변수입니다.

```tsx
export function CampaignPage({ canEdit }: { canEdit: boolean }) {
  const [data, setData] = useState<Campaign[]>([]);
  const [flag, setFlag] = useState(true);
  const [tab, setTab] = useState('all');

  useEffect(() => {
    let ignore = false;
    getCampaigns().then((list) => {
      if (!ignore) {
        setData(list);
        setFlag(false);
      }
    });
    return () => {
      ignore = true;
    };
  }, []);

  const list = tab === 'all' ? data : data.filter((c) => c.status === tab);

  if (flag) return <p>불러오는 중</p>;
  return (
    <>
      <button onClick={() => setTab('all')}>전체</button>
      <button onClick={() => setTab('running')}>진행 중</button>
      <CampaignTable campaigns={list} canEdit={canEdit} />
    </>
  );
}

function CampaignTable({ campaigns, canEdit }: { campaigns: Campaign[]; canEdit: boolean }) {
  return (
    <table>
      <tbody>
        {campaigns.map((c) => (
          <CampaignRow key={c.id} campaign={c} canEdit={canEdit} />
        ))}
      </tbody>
    </table>
  );
}

function CampaignRow({ campaign, canEdit }: { campaign: Campaign; canEdit: boolean }) {
  return (
    <tr>
      <td>{campaign.name}</td>
      <td>{campaign.budget.toLocaleString()}원</td>
      <td>{canEdit && <button>예산 수정</button>}</td>
    </tr>
  );
}
```

목록을 받으면 화면은 요구대로 동작합니다. 리뷰 맨 위에는 목록을 받지 못했을 때 생기는 버그를 적습니다. `getCampaigns()`가 실패하면 `then`에 넘긴 함수가 불리지 않아 `flag`가 `true`로 남고, 화면은 '불러오는 중'에서 멈춥니다. 거부된 Promise를 받는 `catch`도 없어서 콘솔에는 처리되지 않은 거부 에러만 찍힙니다. 이 버그를 고쳐 달라는 의견을 먼저 적고, 이름과 구조에 대한 의견은 그 아래에 제안으로 적습니다. 제안 하나에는 무엇을 봤는지, 어떻게 바꾸면 좋을지, 바꾸면 어떤 변경이 쉬워지는지를 함께 씁니다. 쉬워지는 변경이 빠지면 작성자는 그 제안이 취향인지 이유가 있는 것인지 가리지 못합니다.

### 이름은 값이 무엇인지 말하게 짓습니다

`flag`가 무엇을 표시하는지 알려면 effect를 끝까지 읽고 `setFlag(false)`가 목록을 받은 뒤에 불린다는 것을 찾아야 합니다. `data`와 `list`도 둘 다 캠페인 배열이라 이름만으로는 어느 쪽이 걸러 낸 목록인지 알 수 없습니다. 리뷰 의견은 이렇게 적을 수 있습니다.

> 제안: `flag`는 목록을 받는 동안 `true`인 값이니 `isLoading`으로, `data`와 `list`는 `campaigns`와 `visibleCampaigns`로 바꾸면 어떨까요? 실패를 처리하려고 `error` state를 더할 때도 `isLoading` 옆에 두면 두 값이 무엇인지 이름만으로 읽힙니다.

`tab`은 이름과 타입을 함께 고칠 곳입니다. `useState('all')`처럼 문자열로 시작하면 TypeScript는 `tab`을 `string`으로 보므로, 단추 하나에 `setTab('runing')`처럼 철자를 틀려도 컴파일되고 그 단추를 누르면 빈 목록이 나옵니다. 들어갈 수 있는 값을 유니온 타입으로 적어 두면 같은 오타가 컴파일 에러가 되고, 이름도 무엇을 거르는 값인지 말하게 바꿉니다.

```tsx
type StatusFilter = 'all' | 'running';
const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
```

참이나 거짓만 담는 값은 `isLoading`, `canEdit`처럼 `is`, `can`, `has`로 시작하게 지으면 `if (isLoading)`이 문장처럼 읽힙니다. props를 처음 한 번만 쓰고 그 뒤에 바뀌는 값은 무시하는 컴포넌트라면, React 문서의 관례대로 이름을 `initialStatus`처럼 `initial`로 시작해 그 뜻을 이름에 남깁니다. 셋째 절의 `CampaignStatus`가 이렇게 짓습니다.

### effect와 그 state는 커스텀 훅으로 뗍니다

`CampaignPage`의 앞쪽 절반은 목록을 받아 오는 일을 하고 뒤쪽 절반은 받은 목록을 거르고 그립니다. 목록을 받아 오는 effect와 그 effect가 채우는 state 둘을 함수 하나로 옮기면 화면 컴포넌트에는 거르고 그리는 일만 남습니다. 이름이 `use`로 시작하고 안에서 다른 훅을 부르는 함수를 커스텀 훅이라고 부릅니다. React 문서는 훅 이름을 `use` 뒤에 대문자가 오게 짓고, 안에서 훅을 부르지 않는 함수에는 `use`를 붙이지 말라고 안내합니다.

```tsx
function useCampaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let ignore = false;
    getCampaigns().then((list) => {
      if (!ignore) {
        setCampaigns(list);
        setIsLoading(false);
      }
    });
    return () => {
      ignore = true;
    };
  }, []);

  return { campaigns, isLoading };
}
```

화면 쪽의 state 두 줄과 effect는 `const { campaigns, isLoading } = useCampaigns();` 한 줄로 바뀝니다. 이렇게 떼어 두면 아래 변경이 쉬워집니다.

- 받아 오는 방법을 바꾸는 일이 대부분 훅 안에서 끝납니다. 실패를 처리하려면 훅 안에 `catch`와 `error` state를 더해 돌려주는 객체에 `error`를 넣고, 화면에는 `error`일 때 보여 줄 문구 한 줄만 더합니다. 나중에 React Query 같은 라이브러리로 옮길 때도 화면 컴포넌트는 그대로 두고 훅의 몸통을 바꿉니다. React 문서도 effect를 커스텀 훅으로 감싸 두면 더 나은 방법이 생겼을 때 컴포넌트를 고치지 않고 옮길 수 있다고 적습니다. React Query의 훅은 `QueryClientProvider` 안에서만 동작하므로, 옮길 때 앱 맨 위를 이 컴포넌트로 한 번 감싸고 화면 테스트의 `render`에도 `QueryClientProvider`로 감싸는 `wrapper` 옵션을 넘깁니다.
- 대시보드의 요약 카드처럼 캠페인 목록이 필요한 다른 화면은 같은 훅을 부르면 됩니다. 다만 state까지 함께 쓰지는 않습니다. 훅을 부르는 컴포넌트마다 state가 따로 생겨서, 두 화면은 요청을 각자 보내고 받은 목록도 각자 들고 있습니다.
- 화면을 보는 테스트는 고치지 않아도 됩니다. 테스트가 `getCampaigns`를 가짜 함수로 바꿔 끼우고 화면에 보이는 글자만 본다면, 훅으로 떼기 전과 뒤에 같은 테스트가 통과합니다. 이런 테스트는 셋째 절에서 씁니다.

비슷한 줄이 두 번 보일 때마다 훅을 떼지는 않습니다. React 문서는 작은 중복은 두어도 된다고 하면서, effect를 쓸 때마다 커스텀 훅으로 감싸는 편이 더 읽기 쉬운지 생각해 보라고 권합니다.

### 쓰지 않는 props를 넘기기만 하는 컴포넌트를 줄입니다

`canEdit`은 `CampaignPage`가 받아 `CampaignTable`에 넘기고, `CampaignTable`은 그 값을 읽지 않은 채 `CampaignRow`에 다시 넘깁니다. 이렇게 중간 컴포넌트가 쓰지도 않는 props를 아래로 넘기기만 하는 일을 prop drilling이라고 부릅니다. 지금은 한 겹이지만 캠페인을 중지할 권한을 뜻하는 `canPause`를 더하면 `CampaignTable`의 props 타입과 넘기는 줄도 함께 고쳐야 하고, 겹이 늘수록 고칠 곳도 늘어납니다.

`CampaignTable`이 행을 직접 만들지 않고 `children`으로 받게 바꾸면, 행을 만드는 일이 `CampaignPage`로 올라가 `canEdit`이 `CampaignRow`에 바로 갑니다.

```tsx
function CampaignTable({ children }: { children: ReactNode }) {
  return (
    <table>
      <tbody>{children}</tbody>
    </table>
  );
}

// CampaignPage의 return 안
<CampaignTable>
  {visibleCampaigns.map((c) => (
    <CampaignRow key={c.id} campaign={c} canEdit={canEdit} />
  ))}
</CampaignTable>
```

이제 `canPause`를 더할 때는 값을 받는 `CampaignPage`와 값을 쓰는 `CampaignRow`만 고칩니다. `CampaignTable`은 안에 무엇이 들어오는지 모르는 표 틀이 되어, 광고 그룹 목록처럼 다른 행을 그리는 화면에서도 쓸 수 있습니다.

```figure
파일: assets/11a-1.png
캡션: 그림 11A-1. 표가 행을 children으로 받으면 canEdit이 표를 거치지 않고 CampaignPage에서 CampaignRow로 바로 갑니다.
내용: 왼쪽 칸 "고치기 전", 오른쪽 칸 "children으로 받은 뒤". 왼쪽은 CampaignPage → CampaignTable → CampaignRow 세로 사슬이고 화살표마다 canEdit 꼬리표, CampaignTable 칸은 흐린 색에 "읽지 않고 넘김". 오른쪽은 CampaignPage 아래에 점선 틀 "CampaignTable (표 틀)"이 있고 그 안에 CampaignRow 칸이 들어 있음. canEdit 화살표는 CampaignPage 에서 CampaignRow 로 바로 감. 두 칸 아래에 "canPause를 더할 때 고칠 곳: 셋"(빨강)과 "둘"(초록).
```

props를 거치지 않고 아래 컴포넌트에 값을 건네는 React 기능을 Context라고 하고, `canEdit`도 Context로 내려 줄 수 있습니다. React 문서는 Context를 쓰기 전에 props로 넘기기와 `children`으로 넘기기를 먼저 해 보라고 권합니다. props로 넘기면 어느 컴포넌트가 어떤 값을 쓰는지 코드에 드러나지만, Context로 옮기면 그 값을 읽는 컴포넌트를 찾으려고 `useContext`를 부르는 곳을 따로 뒤져야 합니다. 여러 겹 아래의 많은 컴포넌트가 함께 읽는 값이고 앞의 두 방법으로 겹이 줄지 않을 때 Context를 씁니다.

## 함께 바뀌는 코드는 한곳에 둡니다

캠페인 화면에 캠페인 이름 입력칸과 메모 입력칸이 생겼고, 두 입력칸을 검사하는 함수가 거의 같은 모양으로 들어왔습니다. 두 함수는 문제가 없으면 `null`을, 문제가 있으면 화면에 보여 줄 문구를 돌려줍니다.

```ts
function validateCampaignName(name: string) {
  if (name.trim() === '') return '캠페인 이름을 입력해 주세요';
  if (name.length > 30) return '30자까지 입력할 수 있습니다';
  return null;
}

function validateMemo(memo: string) {
  if (memo.trim() === '') return '메모를 입력해 주세요';
  if (memo.length > 30) return '30자까지 입력할 수 있습니다';
  return null;
}
```

줄이 거의 같으니 하나로 합치고 싶어집니다. 합칠지는 생김새가 아니라 두 함수가 같은 이유로 함께 바뀌는지로 정합니다. 이 앱에서 캠페인 이름의 규칙은 광고를 내보내기 전에 거치는 심사 기준을 따르고, 메모는 운영 팀이 남기는 내부 기록이라 길이도 운영 팀이 정해서, 두 규칙은 따로 바뀝니다.

두 함수를 `validateText` 하나로 합쳐 두었는데, 메모를 200자까지 받게 해 달라는 요구가 와서 최대 길이를 30에서 200으로 바꿨다고 해 봅니다. 실행하기 전에 아래 코드의 두 줄에 무엇이 찍힐지 적어 보세요.

```js
const MAX_LENGTH = 200;

function validateText(text) {
  if (text.trim() === '') return '내용을 입력해 주세요';
  if (text.length > MAX_LENGTH) return `${MAX_LENGTH}자까지 입력할 수 있습니다`;
  return null;
}

const memo = '다음 주 월요일부터 예산을 두 배로 올리기로 했고, 담당자 확인을 기다리는 중입니다.';
const campaignName = '가을 신상품 할인 캠페인 2026년 10월 셋째 주 수도권 20대 대상 영상 광고';

console.log(memo.length, validateText(memo));
console.log(campaignName.length, validateText(campaignName));
```

첫 줄에는 메모 길이와 함께 `47 null`이, 둘째 줄에는 캠페인 이름 길이와 함께 `45 null`이 찍힙니다. 메모가 바라던 대로 통과할 때, 30자를 넘는 캠페인 이름도 함께 통과합니다. 메모에 대한 요구 하나가 캠페인 이름 규칙을 바꿨는데 캠페인 이름 입력칸을 고친 사람은 아무도 없어서, 리뷰에서도 잡히기 어렵습니다. 두 함수를 따로 두었다면 `validateMemo`의 숫자 하나만 바뀌었을 것입니다.

반대로 합쳐야 하는 코드도 있습니다. 예산을 '50,000원'처럼 보여 주는 코드가 표의 예산 칸, 예산 수정 확인 창, 화면 위쪽 요약 카드에 한 줄씩 따로 들어 있다고 해 봅니다. 예산을 '5만 원'처럼 만 원 단위로 보여 달라는 요구가 오면 세 곳이 모두 바뀌어야 하고, 한 곳을 빠뜨리면 화면마다 예산 표기가 달라집니다. 세 줄은 예산을 어떻게 보여 줄지라는 같은 이유로 함께 바뀌므로 함수 하나로 모읍니다.

```ts
function formatBudget(won: number) {
  return `${won.toLocaleString('ko-KR')}원`;
}
```

함께 바뀌는 코드가 한곳에 모여 있는 정도를 응집도라고 부르고, 한 곳을 고칠 때 다른 곳도 따라 고쳐야 하는 정도를 결합도라고 부릅니다. `formatBudget`으로 모으면 예산 표기 규칙이 한곳에 모여 응집도가 높아지고, 두 검사 함수를 따로 두면 메모 규칙을 고칠 때 캠페인 이름 검사를 건드리지 않아 결합도가 낮아집니다. 면접에서 응집도는 높이고 결합도는 낮춘다고 답했다면 이 코드에서 무엇을 모으고 무엇을 떼었는지까지 이어서 말하세요. 원칙만 말하면 면접관은 "이 코드에서는 어디가 그런가요?"라고 다시 묻습니다.

```figure
파일: assets/11b-1.png
캡션: 그림 11B-1. 생김새가 비슷해도 바뀌는 이유가 다르면 따로 두고, 흩어져 있어도 같은 이유로 바뀌면 한곳에 모읍니다.
내용: 왼쪽 칸 "따로 둠: 바뀌는 이유가 다름". validateCampaignName 칸과 validateMemo 칸이 위아래로 있고 칸마다 오른쪽에 바뀌는 이유("광고 심사 기준", "운영 팀 메모 규칙"), 아래에 "…이 바뀌면 이 함수만 고침". 오른쪽 칸 "한곳에 모음: 바뀌는 이유가 같음". "표의 예산 칸", "예산 수정 확인 창", "요약 카드" 작은 칸 셋이 오른쪽 formatBudget 칸 하나로 화살표를 모으고, formatBudget 아래에 "예산 표기 규칙".
```

이미 합쳐 둔 함수에 부르는 곳마다 다른 옵션이 붙기 시작하면 잘못 합친 것일 수 있습니다. 메모 요구 뒤에 캠페인 이름에는 특수 문자를 막아 달라는 요구가 오면 `validateText(text, { max: 30, allowSpecial: false })`처럼 옵션이 늘고, 함수 안의 `if`도 부르는 곳마다 하나씩 늘어납니다. 이 함수를 고치는 사람은 이 함수를 부르는 모든 곳의 옵션 조합을 알아야 합니다. Sandi Metz는 「The Wrong Abstraction」이라는 글에서 중복이 잘못 합친 공통 코드보다 훨씬 싸다고 썼고, 이럴 때는 공통 함수를 부르는 곳마다 다시 풀어 놓고 각자 필요한 줄만 남긴 뒤, 그래도 같은 부분이 남으면 그때 다시 모으라고 권합니다.

### 큰 파일은 함께 바뀌는 것끼리 나눕니다

나눌 때도 같은 질문을 씁니다. 캠페인 화면이 600줄짜리 파일 하나에 들어 있고, 그 안에 상태 필터, 필터 값을 주소 쿼리에 맞추는 코드, 표, 예산 수정, 여러 캠페인을 한 번에 중지하는 일괄 처리가 섞여 있다고 해 봅니다.

- 필터 state와 그 값을 주소 쿼리에 맞추는 코드는 필터 요구가 바뀌면 함께 바뀌므로 `useCampaignFilters` 훅 하나로 묶습니다.
- 예산 입력칸, 저장 요청, 저장에 실패했을 때의 문구는 예산 수정 요구가 바뀔 때 함께 바뀌므로 `BudgetCell` 컴포넌트 하나에 그 state까지 옮깁니다.
- 일괄 처리는 고른 캠페인 목록과 처리 결과 요약을 들고 따로 바뀌므로 `BulkActions` 컴포넌트로 뗍니다.

줄 수나 코드 종류로 나누면 반대가 됩니다. 타입은 `types.ts`, 상수는 `constants.ts`, 도우미 함수는 `utils.ts`로 나누면 예산 수정 요구 하나를 고칠 때 네 파일을 오가야 합니다. 나눈 뒤에는 최근에 들어온 요구 몇 개를 떠올려 요구 하나가 한두 파일에서 끝나는지 확인합니다. 컴포넌트와 그 테스트 파일을 같은 폴더에 나란히 두면, 컴포넌트를 고칠 때 함께 고칠 테스트가 바로 옆에 보입니다.

### 시간이 부족하면 동작부터 끝냅니다

라이브 코딩 면접은 시간이 정해져 있어서 합치고 나누는 일을 다 할 수 없습니다. 요구 하나에 남은 시간이 10분인데 아직 동작하지 않고 코드도 지저분하다면 아래 순서로 씁니다.

1. 요구한 동작을 지금 구조 안에서 끝냅니다. 비슷한 코드를 복사해 고치는 편이 빠르면 복사합니다. 공통 함수를 만들거나 파일을 나누는 일은 미룹니다.
2. 요구에 나온 장면을 화면에서 눌러 보거나 테스트를 돌려 동작을 확인합니다.
3. 남은 시간에 이름 바꾸기처럼 작고 동작을 바꾸지 않는 정리를 하고, 바꾼 뒤 테스트를 한 번 더 돌립니다.
4. 손대지 못한 구조 개선은 말로 남깁니다. "검사 함수 두 개는 바뀌는 이유가 달라서 일부러 합치지 않았고, 시간이 더 있으면 예산 수정 부분을 BudgetCell로 떼겠습니다"처럼 무엇을 왜 하려는지까지 말합니다.

정리부터 시작하면 시간이 끝났을 때 요구는 동작하지 않고 코드는 반쯤 옮겨진 채 남아서, 보여 줄 것도 설명할 것도 없게 됩니다. 동작부터 끝내고 다음에 할 일을 말한 쪽은 동작하는 코드와 설계 판단을 함께 보여 줍니다. 학습 페이지 l21에도 요구를 만족하는 가장 작은 변경을 먼저 하고 이름 정리와 파일 나누기는 뒤로 미루는 순서가 적혀 있습니다.

```figure
파일: assets/11b-2.gif
캡션: 그림 11B-2. 남은 10분을 정리부터 쓰면 요구가 끝나지 않고, 동작부터 끝내면 확인과 이름 정리까지 하고 남은 일을 말로 남깁니다.
프레임:
1. 가로 시간축 0~10분, 위 줄 "정리부터", 아래 줄 "동작부터". 두 줄 모두 비어 있고 10분 자리에 "면접 끝" 세로 점선. (1400ms)
2. 4분. 위 줄에 주황 막대 "파일 나누기"가 0~4분. 아래 줄에 초록 막대 "요구 동작"이 0~4분. (1600ms)
3. 7분. 위 줄에 주황 막대 "공통 함수 만들기"가 4~7분. 아래 줄에 "확인" 막대 4~5분, "이름 정리" 막대 5~7분. (1800ms)
4. 10분. 위 줄 7~10분 자리에 빗금 막대와 빨간 글자 "요구 동작: 끝나지 않음". 아래 줄 7~10분에 초록 테두리 막대 "남은 일을 말함". (2500ms)
```

## 가끔 실패하는 테스트는 무엇을 기다리지 않았나요

이번에는 캠페인 상세 화면의 상태 영역을 테스트합니다. 이 절의 테스트는 저장소의 미션 검사와 같은 도구로 씁니다. vitest는 테스트 파일을 찾아 돌리는 실행기이고, React Testing Library는 컴포넌트를 그린 뒤 단추(`button`) 같은 역할과 보이는 글자로 화면의 요소를 찾게 해 주며, user-event는 사용자의 클릭과 입력을 흉내 냅니다.

`CampaignStatus`는 캠페인의 상태를 보여 주고, 진행 중인 캠페인에는 [중지] 단추를 둡니다. 단추를 누르면 `pauseCampaign(id)`로 서버에 중지 요청을 보내고, 응답이 오면 상태를 '중지됨'으로 바꾸고 '캠페인을 중지했습니다' 안내를 3초 동안 보여 줍니다. 부모가 넘긴 처음 상태만 쓰고 그 뒤에 바뀌는 값은 무시하므로 props 이름을 `initialStatus`로 지었습니다.

```tsx
type Props = { id: string; initialStatus: 'running' | 'paused' };

export function CampaignStatus({ id, initialStatus }: Props) {
  const [status, setStatus] = useState(initialStatus);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    if (notice === '') return;
    const timer = setTimeout(() => setNotice(''), 3000);
    return () => clearTimeout(timer);
  }, [notice]);

  async function handlePause() {
    await pauseCampaign(id);
    setStatus('paused');
    setNotice('캠페인을 중지했습니다');
  }

  return (
    <div>
      <span>{status === 'running' ? '진행 중' : '중지됨'}</span>
      {status === 'running' && <button onClick={handlePause}>중지</button>}
      <p role="status">{notice}</p>
    </div>
  );
}
```

같은 코드로 돌려도 통과했다 실패했다 하는 테스트를 불안정한 테스트(flaky test)라고 부릅니다. 테스트가 기다려야 할 것을 기다리지 않으면, 그때그때 무엇이 먼저 끝나느냐에 따라 결과가 바뀝니다. 이 절의 테스트는 모두 `pauseCampaign`을 가짜 함수로 바꿔 끼우고 시작합니다. `vi.mock`이 `./api` 모듈을 가짜로 바꾸고, `beforeEach`가 테스트마다 가짜 함수의 호출 기록을 지운 뒤 곧바로 이행되는 Promise를 돌려주게 합니다. 아래 테스트 코드에서는 import 줄을 뺐습니다.

```tsx
vi.mock('./api', () => ({ pauseCampaign: vi.fn() }));

beforeEach(() => {
  vi.mocked(pauseCampaign).mockReset();
  vi.mocked(pauseCampaign).mockResolvedValue(undefined);
});
```

### user-event는 await을 붙여 부릅니다

아래 테스트는 [중지]를 누르면 서버에 중지 요청이 가는지 보는데, `user.click`을 `await` 없이 부릅니다.

```tsx
test('중지를 누르면 서버에 중지 요청을 보냅니다', async () => {
  const user = userEvent.setup();
  render(<CampaignStatus id="c1" initialStatus="running" />);
  user.click(screen.getByRole('button', { name: '중지' }));
  expect(pauseCampaign).toHaveBeenCalledWith('c1');
});
```

이 테스트는 `pauseCampaign`이 한 번도 불리지 않았다며 실패합니다. user-event는 마우스를 단추 위로 옮기는 동작과 누르는 동작을 차례로 흉내 내는데, 동작마다 앞에서 `setTimeout`으로 잠깐 기다린 뒤 이벤트를 보내고 모든 동작이 끝나면 이행되는 Promise를 돌려줍니다. `await` 없이 부르면 첫 동작을 시작하기도 전에 다음 줄의 `expect`가 실행됩니다. `await user.click(...)`으로 고치면 클릭이 끝난 뒤에 `expect`가 실행되어 통과합니다.

`await`이 빠진 줄은 늘 이렇게 바로 드러나지는 않습니다. 다음 줄이 `expect(await screen.findByText('중지됨'))`처럼 기다리는 줄이면 그사이 클릭이 끝나서 테스트가 통과하고, 빠진 `await`은 숨어 있다가 누군가 뒤 줄을 바꾸는 날 실패로 드러납니다. 테스트끼리 남긴 것도 결과를 바꿉니다. 앞의 `beforeEach`에서 `mockReset()`을 빼고 이 테스트를 `await`을 붙인 다른 테스트 뒤에 돌리면, 앞 테스트가 남긴 호출 기록 때문에 `await`이 빠진 이 테스트가 통과합니다. 같은 테스트가 혼자 돌 때는 실패하고 파일 전체를 돌릴 때는 통과하면 이런 기록부터 의심합니다.

### 나중에 나타날 요소는 findBy로 찾습니다

`await`을 붙였는데도 가끔 실패하는 테스트가 있습니다. 실제 서버처럼 응답이 조금 늦게 오게 가짜 함수를 바꾸고, 클릭한 뒤 바로 안내 글자를 찾는 테스트입니다. 가짜 `pauseCampaign`은 실제 시간으로 20ms 뒤에 이행되는 Promise를 돌려줍니다.

```tsx
test('중지하면 안내가 보입니다', async () => {
  vi.mocked(pauseCampaign).mockImplementation(
    () => new Promise((resolve) => setTimeout(resolve, 20)),
  );
  const user = userEvent.setup();
  render(<CampaignStatus id="c1" initialStatus="running" />);
  await user.click(screen.getByRole('button', { name: '중지' }));
  expect(screen.getByText('캠페인을 중지했습니다')).toBeInTheDocument();
});
```

`await user.click()`은 클릭 이벤트를 다 보낼 때까지만 기다리고, 클릭이 보낸 중지 요청의 응답은 기다리지 않습니다. `getByText`는 부르는 순간 화면을 한 번 찾아보고 없으면 바로 에러를 던집니다. 응답이 20ms 뒤에 오면 `getByText`가 찾는 순간에는 안내가 아직 없어서 실패하고, 곧바로 이행되는 가짜 함수로 바꾸면 클릭이 끝나기 전에 화면이 바뀌어 통과합니다. 지연을 2ms로 줄여 열 번 돌려 보면 몇 번은 통과하고 나머지는 실패해서, 돌릴 때마다 결과가 바뀝니다. 가짜 서버의 응답 시간이 클릭이 끝나는 시점 앞뒤를 오가면, 내 컴퓨터에서 통과하던 테스트가 코드를 올릴 때마다 테스트를 자동으로 돌리는 서버(CI)에서 가끔 실패합니다.

마지막 줄을 `findByText`로 바꾸면 응답이 20ms 뒤에 오든 300ms 뒤에 오든 통과합니다.

```tsx
expect(await screen.findByText('캠페인을 중지했습니다')).toBeInTheDocument();
```

`findBy`로 시작하는 쿼리는 요소를 찾으면 이행되고, 기본 1000ms가 지나도 없으면 거부되는 Promise를 돌려줍니다. 그동안 화면이 바뀔 때마다, 그리고 바뀌지 않아도 50ms마다 다시 찾습니다. 나중에 나타날 요소는 `findBy`로, 지금 있어야 할 요소는 `getBy`로, 없어야 할 요소는 `queryBy`로 찾습니다. `queryBy`는 요소가 없으면 에러 대신 `null`을 돌려주므로, 중지한 뒤 [중지] 단추가 사라졌는지는 `expect(screen.queryByRole('button', { name: '중지' })).toBeNull()`로 확인합니다.

```figure
파일: assets/11c-1.gif
캡션: 그림 11C-1. getBy는 클릭이 끝난 순간 한 번만 찾아 실패하고, findBy는 안내가 그려질 때까지 기다렸다가 다시 찾아 통과합니다.
프레임:
1. 가로 시간축 0~30ms. 위 줄 "테스트"(user.click), 가운데 줄 "가짜 서버"(중지 요청), 아래 줄 "findByText". 0ms 에 클릭 막대와 중지 요청 막대가 시작됨. 오른쪽 화면 칸에 '진행 중'과 '[중지]'. (1400ms)
2. 클릭 막대가 3ms 쯤에서 닫히고 그 옆에 빨간 점과 꼬리표 "getByText: 안내 없음, 에러". 화면 칸은 그대로 '진행 중'. (2000ms)
3. 20ms 에 중지 요청 막대가 닫히고 "응답" 세로선. 화면 칸이 '중지됨'과 '캠페인을 중지했습니다'로 바뀜. (1800ms)
4. findByText 줄: 클릭이 끝난 자리에 회색 점 "없음", 20ms 까지 점선 "기다림", 20ms 자리에 초록 점 "찾음". 화면 칸에 초록 테두리. (2200ms)
```

### 3초를 기다리는 테스트는 가짜 타이머로 바꿉니다

안내가 3초 뒤에 사라지는지도 확인해야 합니다. 안내가 보인 것을 `findBy`로 확인한 뒤 사라질 때까지 기다리려고 아래 줄을 쓰면, 이 테스트는 1초쯤 뒤에 실패합니다. `waitFor`는 넘긴 함수가 통과할 때까지 다시 부르는 도구이고, `findBy`처럼 기본으로 1000ms까지만 기다립니다.

```tsx
await waitFor(() => expect(screen.queryByText('캠페인을 중지했습니다')).toBeNull());
```

`waitFor`에 `{ timeout: 4000 }`을 넘기면 통과하지만 테스트 하나가 3초씩 걸리고, vitest가 테스트 하나에 주는 기본 시간 5000ms의 절반 넘게 실제 시간을 기다립니다. 이럴 때는 테스트가 시계를 직접 움직입니다. `vi.useFakeTimers()`를 부르면 `setTimeout`, `setInterval`, `Date` 같은 시계 함수가 테스트가 앞당길 때만 흐르는 가짜 시계 위에서 돌고, 이렇게 바꾼 시계 함수를 가짜 타이머라고 부릅니다. 아래 테스트는 가짜 타이머로 2초와 1초를 차례로 앞당기며 안내가 남았는지와 사라졌는지를 봅니다.

```tsx
describe('안내가 사라지는 시간', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('안내는 3초 동안 보이고 그 뒤에 사라집니다', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<CampaignStatus id="c1" initialStatus="running" />);
    await user.click(screen.getByRole('button', { name: '중지' }));
    expect(await screen.findByText('캠페인을 중지했습니다')).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByText('캠페인을 중지했습니다')).toBeInTheDocument();

    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.queryByText('캠페인을 중지했습니다')).toBeNull();
  });
});
```

`vi.advanceTimersByTimeAsync(2000)`은 가짜 시계를 2초 앞당기면서 그사이 시간이 된 타이머를 실행하고, Promise 콜백 안에서 새로 건 타이머까지 실행합니다. 타이머가 바꾼 state를 React가 화면에 반영하도록 `act`로 감쌉니다. 2초 뒤에는 안내가 남아 있고 1초를 더 앞당기면 사라지므로 3초라는 길이까지 확인하며, 이 테스트는 실제로는 몇십 ms 안에 끝납니다. 나머지 설정은 아래 일을 합니다.

- `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`은 user-event가 동작 사이에 기다리는 시간만큼 가짜 시계를 앞당기게 합니다. user-event 문서는 가짜 타이머를 쓸 때 이 옵션에 테스트 도구의 시계 앞당기는 함수를 넘기라고 적습니다.
- `shouldAdvanceTime: true`는 가짜 시계가 실제 시간이 흐르는 만큼 저절로도 흐르게 합니다. 이 저장소처럼 vitest와 React Testing Library를 함께 쓰면, 이 옵션 없이 `vi.useFakeTimers()`만 부른 테스트는 `await user.click()`이 끝나지 않아 5초 뒤 시간 초과로 실패합니다. React Testing Library가 클릭을 마무리하며 `setTimeout`으로 잠깐 기다리는데, 그 시계를 직접 앞당기는 것은 Jest의 가짜 타이머일 때뿐이기 때문입니다.
- `afterEach`의 `vi.useRealTimers()`는 진짜 시계로 되돌립니다. 되돌리지 않으면 같은 파일에서 뒤에 도는 테스트도 가짜 시계 위에서 돌고, 그 테스트의 `Date.now()`는 앞 테스트가 앞당긴 3초쯤 실제 시각보다 앞선 값을 돌려줍니다. 테스트가 앞 테스트의 시계를 이어받으면 테스트 순서에 따라 결과가 바뀔 수 있습니다.

```figure
파일: assets/11c-2.gif
캡션: 그림 11C-2. 진짜 시계로는 waitFor가 1초에 포기하지만, 가짜 시계는 테스트가 2초와 1초를 앞당겨 안내가 사라지는 때를 바로 확인합니다.
프레임:
1. 위 줄 "진짜 시계", 아래 줄 "가짜 시계". 두 줄 모두 0~3초 시간축과 3초 자리의 빨간 "안내 사라짐" 세로선, 오른쪽에 "안내 보임" 칸. 아래 줄 0초에 노란 바늘. (1400ms)
2. 위 줄에 waitFor 막대가 0~1초, 막대 끝에 빨간 꼬리표 "1초에 포기, 실패". (2000ms)
3. 아래 줄 바늘이 2초로 건너뛰고 0~2초에 노란 점선, 꼬리표 "advanceTimersByTimeAsync(2000)". 아래 화면 칸은 "안내 보임". (1800ms)
4. 바늘이 3초로 건너뜀. 0~2초 점선은 흐리게, 2~3초 점선은 노랑, 꼬리표 "advanceTimersByTimeAsync(1000)". 아래 화면 칸이 "(비어 있음)"과 초록 테두리, 축 아래에 "실제 걸린 시간: 몇십 ms". (2200ms)
```

### 구현 세부를 묻는 테스트는 화면을 보게 고칩니다

마지막은 실패하지 않아서 문제인 테스트입니다. 아래 테스트는 안내가 3초 뒤에 사라지는지를 `setTimeout`이 3000으로 불렸는지로 확인합니다. `vi.spyOn`은 진짜 `setTimeout`을 그대로 부르면서 무엇을 넘겨 불렀는지 기록하는 함수로 감쌉니다.

```tsx
test('중지하면 3초짜리 타이머를 겁니다', async () => {
  const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');
  const user = userEvent.setup();
  render(<CampaignStatus id="c1" initialStatus="running" />);
  await user.click(screen.getByRole('button', { name: '중지' }));
  await waitFor(() => expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 3000));
  setTimeoutSpy.mockRestore();
});
```

어느 함수를 무엇으로 불렀는지, state가 몇 개인지, 요소에 붙은 클래스 이름이 무엇인지처럼 사용자가 보지 못하는 코드 안쪽 사정을 구현 세부라고 부릅니다. 이 테스트는 구현 세부를 묻고 있어서 두 방향으로 틀립니다.

- 안내를 지우는 콜백을 `() => {}`로 비운 망가진 코드에서도 `setTimeout`은 3000으로 불리므로 통과합니다. 화면에서는 안내가 사라지지 않는데 테스트는 통과로 표시됩니다.
- 안내를 1초마다 남은 시간을 하나씩 줄이는 `setInterval`로 지우게 바꾸면, 안내가 3초 뒤에 사라지는 동작이 같아도 `setTimeout`이 3000으로 불리지 않아 실패합니다.

앞의 가짜 타이머 테스트는 화면만 봅니다. 콜백을 비운 코드에서는 3초를 앞당겨도 안내가 남아 실패하고, `setInterval`로 바꾼 코드에서는 3초 뒤에 안내가 사라져 통과합니다. Testing Library는 테스트가 소프트웨어를 쓰는 방식과 닮을수록 더 믿을 수 있다는 원칙을 두고, 요소를 찾을 때는 역할로 찾는 `getByRole`을 가장 먼저 쓰고 사용자가 볼 수 없는 `data-testid`는 가장 나중에 쓰라고 권합니다. 첫 절에서 훅을 떼고 이름을 바꾼 뒤에도 화면을 보는 테스트를 고치지 않아도 된 것은, 그 테스트가 `getCampaigns`의 가짜 응답과 화면의 글자만 보고 훅이나 state의 이름은 보지 않기 때문입니다.

```figure
파일: assets/11c-3.png
캡션: 그림 11C-3. setTimeout을 엿보는 테스트는 망가진 코드를 통과시키고 동작이 같은 코드를 떨어뜨리며, 화면을 보는 테스트는 그 반대로 맞게 가립니다.
내용: 가로 칸 셋 "맞는 코드", "콜백을 비운 코드(안내가 남음)", "setInterval로 바꾼 코드(3초 뒤 사라짐)". 세로 줄 둘 "setTimeout을 엿보는 테스트", "가짜 타이머로 화면을 보는 테스트". 칸마다 통과 또는 실패. 위 줄은 통과, 통과, 실패이고 가운데와 오른쪽 칸에 빨간 테두리. 아래 줄은 통과, 실패, 통과이고 모두 초록 테두리.
```

## 면접에서는 이렇게 이어집니다

꼬리 질문 사슬 11-A는 첫 절의 캠페인 목록 코드를 보여 주고 리뷰 의견을 무엇부터 적을지, 이름을 어떻게 바꿀지, 커스텀 훅으로 떼면 무엇이 쉬워지는지, prop drilling을 어떻게 줄일지를 묻습니다. 11-B는 둘째 절의 두 검사 함수를 합칠지에서 시작해 합쳐야 하는 코드, 600줄 파일을 나누는 자리, 시간이 부족할 때 무엇부터 할지로 이어집니다. 11-C는 셋째 절의 `CampaignStatus`로 `await`이 빠진 user-event, `getBy`와 `findBy`, 가짜 타이머, 구현 세부를 묻는 테스트를 차례로 묻습니다. 라이브 코딩 미션 w13(광고 캠페인 관리 화면)은 600줄 파일을 읽고 고치는 미션이고, w12(버그 제보를 테스트로 고정하기)는 셋째 절처럼 화면 테스트를 직접 쓰고 불안정한 테스트를 고치는 미션입니다.
