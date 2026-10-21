import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import { App } from '@app/App';
import { renderApp } from '@kit/render';

test('1a 이름이 "더하기"인 버튼이 있습니다', () => {
  renderApp(<App />);
  expect(screen.getByRole('button', { name: '더하기' })).toBeInTheDocument();
});

test('1b 더하기 버튼을 두 번 누르면 "지금까지 2번"이 보입니다', async () => {
  renderApp(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '더하기' }));
  await user.click(screen.getByRole('button', { name: '더하기' }));
  expect(screen.getByText('지금까지 2번')).toBeInTheDocument();
});
