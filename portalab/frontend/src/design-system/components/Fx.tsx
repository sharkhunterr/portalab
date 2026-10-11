import { useEffect, useRef } from "react";

/**
 * #73, #78: a look drawn by the GPU, on a canvas laid behind its element (its parent): flames, electricity,
 * water… The shared renderer is loaded only when one is shown; when the device cannot draw it the element
 * is marked ``data-fx-failed`` and keeps its CSS look.
 */
export function FxLayer({
  effect,
  calm = false,
  shape = 0,
  maxSide,
  aura = false,
  cycle = false,
  from,
  className = "fx-layer",
}: {
  effect: string;
  /** text is written over it: its inside is kept dark enough to read */
  calm?: boolean;
  shape?: number;
  maxSide?: number;
  /** nothing drawn inside the element (a name keeps its letters) */
  aura?: boolean;
  /** comes and goes over and over (the time portal as a teleporter) */
  cycle?: boolean;
  /** seconds into its timeline it starts at */
  from?: number;
  className?: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    const host = element?.parentElement;
    if (!element || !host) return;
    let stop: (() => void) | null = null;
    let cancelled = false;
    void import("../themes/premium/badgeFx").then(({ attachFx }) => {
      if (cancelled) return;
      stop = attachFx(element, host, effect as "blaze", {
        calm,
        shape,
        aura,
        cycle,
        ...(maxSide ? { maxSide } : {}),
        ...(from ? { from } : {}),
      });
      if (!stop) host.dataset.fxFailed = "true";
    });
    return () => {
      cancelled = true;
      stop?.();
    };
  }, [effect, calm, shape, maxSide, aura, cycle, from]);
  return <canvas ref={canvas} className={className} />;
}
