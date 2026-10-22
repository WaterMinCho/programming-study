import type { Transaction } from './types';

// 가짜 서버. 실제 서버 대신 정해 둔 거래내역을 잠시 기다렸다가 돌려줌.
// 개발 모드(npm run dev)에서만 통장마다 다른 지연을 둠. 주소 끝에 ?fail=1 을 붙이면 화면을 연 뒤 1초 안에 보낸 요청이 모두 실패함.
// 테스트에서는 바로 응답함.

const TRANSACTIONS: Record<string, Transaction[]> = {
  living: [
    { id: 'l1', date: '2026-10-02', title: '편의점', amount: -4500 },
    { id: 'l2', date: '2026-10-03', title: '월급', amount: 2400000 },
    { id: 'l3', date: '2026-10-05', title: '전기 요금', amount: -38200 },
    { id: 'l4', date: '2026-10-07', title: '점심', amount: -9800 },
    { id: 'l5', date: '2026-10-09', title: '교통카드 충전', amount: -50000 },
  ],
  saving: [
    { id: 's1', date: '2026-10-01', title: '자동이체 저축', amount: 300000 },
    { id: 's2', date: '2026-10-08', title: '이자', amount: 1250 },
    { id: 's3', date: '2026-10-15', title: '자동이체 저축', amount: 300000 },
  ],
  fresh: [],
};

const DELAY_MS: Record<string, number> = { living: 1500, saving: 300, fresh: 300 };

const SLOW = import.meta.env.DEV && import.meta.env.MODE !== 'test';

const FAIL_UNTIL =
  SLOW && typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('fail') === '1' ? Date.now() + 1000 : 0;

export type GetTransactionsOptions = {
  /** 요청을 그만두라는 신호. abort() 가 불리면 Promise 가 AbortError 로 거부됨 */
  signal?: AbortSignal;
};

export function getTransactions(accountId: string, options: GetTransactionsOptions = {}): Promise<Transaction[]> {
  const { signal } = options;
  const fail = Date.now() < FAIL_UNTIL;
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(abortError());
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      if (fail) {
        reject(new Error('서버와 연결하지 못했습니다'));
        return;
      }
      resolve((TRANSACTIONS[accountId] ?? []).map((t) => ({ ...t })));
    }, SLOW ? (DELAY_MS[accountId] ?? 300) : 0);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

function abortError(): Error {
  return new DOMException('요청이 끊겼습니다', 'AbortError');
}
