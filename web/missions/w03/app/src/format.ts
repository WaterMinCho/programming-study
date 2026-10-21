export function formatAmount(amount: number): string {
  const sign = amount < 0 ? '-' : '+';
  return `${sign}${Math.abs(amount).toLocaleString('ko-KR')}원`;
}

export function formatDate(date: string): string {
  const [, month, day] = date.split('-').map(Number);
  return `${month}월 ${day}일`;
}
