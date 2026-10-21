import { useState } from 'react';
import { ACCOUNTS } from './accounts';
import { AccountTabs } from './components/AccountTabs';
import { TransactionList } from './components/TransactionList';

export default function App() {
  const [accountId, setAccountId] = useState(ACCOUNTS[0].id);

  return (
    <main>
      <h1>거래내역</h1>
      <AccountTabs accounts={ACCOUNTS} selectedId={accountId} onSelect={setAccountId} />
      <TransactionList accountId={accountId} />
    </main>
  );
}
