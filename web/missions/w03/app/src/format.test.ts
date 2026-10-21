import { expect, test } from 'vitest';
import { formatAmount, formatDate } from './format';

test('금액은 부호와 천 단위 쉼표를 붙여 원 단위로 보여 줍니다', () => {
  expect(formatAmount(2400000)).toBe('+2,400,000원');
  expect(formatAmount(-4500)).toBe('-4,500원');
  expect(formatAmount(0)).toBe('+0원');
});

test('날짜는 월과 일만 보여 줍니다', () => {
  expect(formatDate('2026-10-02')).toBe('10월 2일');
  expect(formatDate('2026-01-15')).toBe('1월 15일');
});
