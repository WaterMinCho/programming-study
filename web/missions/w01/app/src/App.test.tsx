import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, test } from 'vitest';
import App from './App';

afterEach(cleanup);

test('상품을 받기 전에는 불러오는 중 문구가 보입니다', () => {
  render(<App />);
  expect(screen.getByRole('status').textContent).toBe('상품을 불러오는 중입니다');
});

test('응답이 오면 상품 열 개가 이름과 가격 순서로 한 줄씩 보입니다', async () => {
  render(<App />);
  const rows = await screen.findAllByRole('listitem');
  expect(rows).toHaveLength(10);
  expect(rows[3].textContent).toBe('LED 무드등23,000원');
  expect(screen.queryByRole('status')).toBeNull();
});
