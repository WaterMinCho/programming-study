import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, test } from 'vitest';
import App from './App';

afterEach(cleanup);

test('통장 탭 세 개가 보이고 생활비 통장이 골라져 있습니다', () => {
  render(<App />);
  const tabs = screen.getAllByRole('tab');
  expect(tabs.map((tab) => tab.textContent)).toEqual(['생활비 통장', '저축 통장', '새 통장']);
  expect(screen.getByRole('tab', { name: '생활비 통장' }).getAttribute('aria-selected')).toBe('true');
});

test('응답이 오면 생활비 통장의 거래가 날짜, 내용, 금액 순서로 보입니다', async () => {
  render(<App />);
  const row = (await screen.findByText('편의점')).closest('li');
  expect(row?.textContent).toBe('10월 2일편의점-4,500원');
});

test('저축 통장 탭을 누르면 저축 통장의 거래가 보입니다', async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole('tab', { name: '저축 통장' }));
  expect(await screen.findByText('이자')).toBeTruthy();
  expect(screen.getByRole('tab', { name: '저축 통장' }).getAttribute('aria-selected')).toBe('true');
});
