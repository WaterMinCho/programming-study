import type { Product } from '../types';
import { ProductItem } from './ProductItem';

export function ProductList({ products }: { products: Product[] }) {
  return (
    <ul aria-label="상품 목록">
      {products.map((product) => (
        <ProductItem key={product.id} product={product} />
      ))}
    </ul>
  );
}
