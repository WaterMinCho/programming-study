import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test } from 'vitest';
import { App } from '@app/App';
import { renderApp } from '@kit/render';

test('2a 더하기를 누른 뒤 초기화를 누르면 "지금까지 0번"이 보입니다', async () => {
  renderApp(<App />);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: '더하기' }));
  await user.click(screen.getByRole('button', { name: '초기화' }));
  expect(screen.getByText('지금까지 0번')).toBeInTheDocument();
});
