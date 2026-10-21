import { expect, test } from 'vitest';
import { formatPrice } from './format';

test('가격은 천 단위 쉼표를 붙여 원 단위로 보여 줍니다', () => {
  expect(formatPrice(18900)).toBe('18,900원');
  expect(formatPrice(7900)).toBe('7,900원');
  expect(formatPrice(0)).toBe('0원');
});
