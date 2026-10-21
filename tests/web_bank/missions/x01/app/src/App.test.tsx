import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { App } from './App';

test('제목이 보입니다', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: '횟수 세기' })).toBeDefined();
});
