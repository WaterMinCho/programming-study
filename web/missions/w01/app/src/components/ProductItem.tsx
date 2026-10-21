import { formatPrice } from '../format';
import type { Product } from '../types';

export function ProductItem({ product }: { product: Product }) {
  return (
    <li>
      <span>{product.name}</span>
      <span>{formatPrice(product.price)}</span>
    </li>
  );
}
