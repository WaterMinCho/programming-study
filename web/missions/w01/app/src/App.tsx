import { useEffect, useState } from 'react';
import { getProducts } from './api';
import { ProductList } from './components/ProductList';
import type { Product } from './types';

export default function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProducts().then((items) => {
      setProducts(items);
      setLoading(false);
    });
  }, []);

  return (
    <main>
      <h1>상품 목록</h1>
      {loading ? <p role="status">상품을 불러오는 중입니다</p> : <ProductList products={products} />}
    </main>
  );
}
