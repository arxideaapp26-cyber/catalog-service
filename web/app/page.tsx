type Product = {
  id: number;
  title: string;
  image_url: string;
};

type Catalog = {
  products: Product[];
  error: string | null;
};

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

async function loadProducts(): Promise<Catalog> {
  const api = process.env.API_URL;
  if (!api) {
    return { products: [], error: "Не задан адрес API" };
  }
  try {
    const response = await fetch(`${api.replace(/\/$/, "")}/products`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return { products: [], error: "Не удалось загрузить товары" };
    }
    const products = (await response.json()) as Product[];
    return { products, error: null };
  } catch {
    return { products: [], error: "Не удалось загрузить товары" };
  }
}

export default async function CatalogPage() {
  const catalog = await loadProducts();

  return (
    <main>
      <h1>Каталог</h1>
      {catalog.error ? <p>{catalog.error}</p> : null}
      <ul>
        {catalog.products.map((product) => (
          <li key={product.id}>
            <img src={product.image_url} alt={product.title} />
            <div>{product.title}</div>
          </li>
        ))}
      </ul>
    </main>
  );
}
