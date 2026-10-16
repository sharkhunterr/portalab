import { useEffect, useRef } from "react";
import type { ExternalElement } from "./registry";
import { runSandbox } from "./sandbox";
import "./external.css";

/**
 * issue 1: an imported look drawn by its own script (a level-up, a celebration) — always in a sandbox (an
 * iframe of an opaque origin: no account, no network, no page of Portalab's), never in this page. Decorative:
 * hidden from assistive technologies, never focused, no pointer events.
 */
export function ExternalScript({
  element,
  context,
  className,
}: {
  element: ExternalElement;
  context: { reducedMotion: boolean; level?: number; text?: string };
  className?: string;
}) {
  const frame = useRef<HTMLIFrameElement>(null);
  const { reducedMotion, level, text } = context;
  useEffect(() => {
    const target = frame.current;
    if (!target) return;
    const sandbox = runSandbox(target, element, {
      type: element.type,
      look: element.look,
      reducedMotion,
      ...(level === undefined ? {} : { level }),
      ...(text === undefined ? {} : { text }),
    });
    return () => sandbox.stop();
  }, [element, reducedMotion, level, text]);
  return (
    <iframe
      ref={frame}
      className={className}
      data-sandboxed=""
      data-external={element.product}
      sandbox="allow-scripts"
      title={element.names.en || element.product}
      aria-hidden="true"
      tabIndex={-1}
    />
  );
}
