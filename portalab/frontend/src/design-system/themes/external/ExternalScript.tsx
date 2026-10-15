import { useEffect, useRef } from "react";
import { type ExternalElement, mountScript, type ScriptContext } from "./external";

/**
 * issue 1: an imported look drawn by its own script — its module mounted into this element when it shows,
 * stopped when it leaves. Decorative: hidden from assistive technologies, no pointer events (its CSS).
 */
export function ExternalScript({
  element,
  context,
  className,
}: {
  element: ExternalElement;
  context: Omit<ScriptContext, "asset" | "type" | "look">;
  className?: string;
}) {
  const host = useRef<HTMLSpanElement>(null);
  const { reducedMotion, level, text } = context;
  useEffect(() => {
    const target = host.current;
    if (!target) return;
    let stop: (() => void) | null = null;
    let cancelled = false;
    void mountScript(element, target, {
      reducedMotion,
      ...(level === undefined ? {} : { level }),
      ...(text === undefined ? {} : { text }),
    }).then((done) => {
      if (cancelled) done?.();
      else stop = done;
    });
    return () => {
      cancelled = true;
      stop?.();
      target.replaceChildren();
    };
  }, [element, reducedMotion, level, text]);
  return <span ref={host} className={className} data-external={element.product} aria-hidden="true" />;
}
