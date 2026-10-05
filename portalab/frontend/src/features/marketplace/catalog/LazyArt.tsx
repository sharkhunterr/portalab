import { useEffect, useRef, useState } from "react";
import type { Product } from "../api";
import { type ArtSize, ProductArt } from "./ProductArt";
import { ProductPoster } from "./ProductPoster";

/**
 * Art drawn when it comes near the screen (027): a cheap poster first, the live pre-rendering (animated
 * notifications, ambient layers, effects…) once the card is about to be seen — a shop of hundreds of
 * products opens at once.
 */
export function LazyArt({ product, size = "card" }: { product: Product; size?: ArtSize }) {
  const holder = useRef<HTMLSpanElement>(null);
  const [near, setNear] = useState(typeof IntersectionObserver === "undefined");
  useEffect(() => {
    const element = holder.current;
    if (near || !element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [near]);
  return (
    <span ref={holder} className="lazy-art">
      {near ? <ProductArt product={product} size={size} /> : <ProductPoster product={product} />}
    </span>
  );
}
