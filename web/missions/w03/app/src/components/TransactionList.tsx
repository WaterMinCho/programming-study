import { useEffect, useState } from 'react';
import { getTransactions } from '../api';
import type { Transaction } from '../types';
import { TransactionRow } from './TransactionRow';

export function TransactionList({ accountId }: { accountId: string }) {
  const [items, setItems] = useState<Transaction[]>([]);

  useEffect(() => {
    getTransactions(accountId).then(setItems);
  }, [accountId]);

  return (
    <ul aria-label="거래내역">
      {items.map((t) => (
        <TransactionRow key={t.id} transaction={t} />
      ))}
    </ul>
  );
}
