import { formatAmount, formatDate } from '../format';
import type { Transaction } from '../types';

export function TransactionRow({ transaction }: { transaction: Transaction }) {
  return (
    <li>
      <span>{formatDate(transaction.date)}</span>
      <span>{transaction.title}</span>
      <span>{formatAmount(transaction.amount)}</span>
    </li>
  );
}
