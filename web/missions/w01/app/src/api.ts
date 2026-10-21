import type { Product } from './types';

// 가짜 서버. 실제 서버 대신 정해 둔 상품 목록을 잠시 기다렸다가 돌려줌.
// 개발 모드(npm run dev)에서만 0.6초를 기다리고, 테스트에서는 바로 응답함.

const PRODUCTS: Product[] = [
  { id: 'p1', name: '스테인리스 텀블러 500ml', price: 18900 },
  { id: 'p2', name: '보온 텀블러 350ml', price: 15900 },
  { id: 'p3', name: 'USB-C 충전 케이블 1m', price: 7900 },
  { id: 'p4', name: 'LED 무드등', price: 23000 },
  { id: 'p5', name: 'mini 가습기', price: 19800 },
  { id: 'p6', name: '무선 마우스', price: 12500 },
  { id: 'p7', name: '캠핑 의자', price: 39000 },
  { id: 'p8', name: '접이식 우산', price: 11000 },
  { id: 'p9', name: '블루투스 스피커', price: 45000 },
  { id: 'p10', name: '노트북 거치대', price: 26500 },
];

const DELAY_MS = 600;

const SLOW = import.meta.env.DEV && import.meta.env.MODE !== 'test';

export function getProducts(): Promise<Product[]> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(PRODUCTS.map((product) => ({ ...product })));
    }, SLOW ? DELAY_MS : 0);
  });
}
