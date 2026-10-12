import { lazy, Suspense, useEffect, useState } from "react";
import { BOOSTER_EVENT, type Booster, useBoosters } from "./api";

const BoosterReveal = lazy(() => import("./BoosterReveal").then((m) => ({ default: m.BoosterReveal })));

/**
 * #81: the stage, over everything — a booster opened from anywhere (``openBooster``: the shop's sheet, the
 * reserve) plays its reveal here. Light: the reveal itself loads when a booster is opened.
 */
export function BoosterStageHost() {
  const [open, setOpen] = useState<{ key: string; sealed: boolean } | null>(null);
  const boosters = useBoosters(open !== null);
  useEffect(() => {
    const listen = (event: Event) => setOpen((event as CustomEvent<{ key: string; sealed: boolean }>).detail);
    window.addEventListener(BOOSTER_EVENT, listen);
    return () => window.removeEventListener(BOOSTER_EVENT, listen);
  }, []);
  // kept as it was when opened: once its last offered one is opened, an off-season booster leaves the
  // list — the stage must not vanish with it
  const [booster, setBooster] = useState<Booster | null>(null);
  const found = open ? boosters.data?.find((b) => b.key === open.key) : undefined;
  useEffect(() => {
    if (!open) setBooster(null);
    else if (found && booster?.key !== open.key) setBooster(found);
  }, [open, found, booster?.key]);
  if (!open || !booster) return null;
  return (
    <Suspense fallback={null}>
      <BoosterReveal booster={found ?? booster} sealed={open.sealed} onClose={() => setOpen(null)} />
    </Suspense>
  );
}
