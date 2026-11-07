import { useEffect, useRef, useState } from "react";
import { StillMotionZone, useHeldMotion } from "../../../design-system/motion/still";
import type { Product } from "../api";
import { type ArtSize, ProductArt } from "./ProductArt";
import { ProductPoster } from "./ProductPoster";
import { useStillPreviews } from "./stillPreviews";

/**
 * Art drawn when it comes near the screen (027): a cheap poster first, the live pre-rendering (animated
 * notifications, ambient layers, effects…) once the card is about to be seen — a shop of hundreds of
 * products opens at once. Held still while the member browses without them (issue 381).
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
  const still = useStillPreviews();
  useHeldMotion(holder, still && near);
  return (
    <span ref={holder} className="lazy-art">
      <StillMotionZone value={still}>
        {near ? <ProductArt product={product} size={size} /> : <ProductPoster product={product} />}
      </StillMotionZone>
    </span>
  );
}
