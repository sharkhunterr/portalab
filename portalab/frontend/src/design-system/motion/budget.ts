/**
 * #29: how much decorative motion the portal may spend — one word on the root (``data-motion-budget``)
 * that the GPU looks, the canvas ambiences and the CSS read:
 *
 * * ``full``: everything moves (still within a budget of looks animated at once);
 * * ``eco``: fewer looks at once, half the frame rate, half the particles — the member chose « discreet »
 *   animations, or the device saves energy (battery low and not charging, data saver);
 * * ``still``: a still frame — the member chose « none », or motion is reduced.
 */
import "./motion.css";

export type MotionBudget = "full" | "eco" | "still";

const LOW_BATTERY = 0.2;
let choice: "all" | "discreet" | "none" = "all";
let reduced = false;
let saving = false;
let watching = false;
let current: MotionBudget = "full";

function compute(): MotionBudget {
  if (reduced || choice === "none") return "still";
  if (choice === "discreet" || saving) return "eco";
  return "full";
}

function publish() {
  current = compute();
  if (typeof document !== "undefined") document.documentElement.dataset.motionBudget = current;
}

interface BatteryLike extends EventTarget {
  level: number;
  charging: boolean;
}

/** Energy saving on the device: a low battery that is not charging, or the browser's data saver. */
function watchDevice() {
  if (watching || typeof navigator === "undefined") return;
  watching = true;
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  const dataSaver = Boolean(connection?.saveData);
  const getBattery = (navigator as Navigator & { getBattery?: () => Promise<BatteryLike> }).getBattery;
  saving = dataSaver;
  if (typeof getBattery !== "function") return;
  getBattery
    .call(navigator)
    .then((battery) => {
      const update = () => {
        saving = dataSaver || (!battery.charging && battery.level <= LOW_BATTERY);
        publish();
      };
      battery.addEventListener("levelchange", update);
      battery.addEventListener("chargingchange", update);
      update();
    })
    .catch(() => undefined);
}

/** Called whenever the preferences are applied: the member's choice and whether motion is reduced. */
export function setMotionChoice(animations: "all" | "discreet" | "none", reducedMotion: boolean): void {
  choice = animations;
  reduced = reducedMotion;
  watchDevice();
  publish();
}

/** Issue 381: the attribute of a part of a page whose motion is held still (``still.tsx``). */
export const STILL_ATTRIBUTE = "data-motion-still";

/** Whether what is drawn in ``element`` holds a still frame: the budget says so, or its part of the page. */
export function stillFor(element: Element | null | undefined): boolean {
  return current === "still" || Boolean(element?.closest(`[${STILL_ATTRIBUTE}]`));
}

/** The budget now (read every frame by the renderers: a cheap variable). */
export function motionBudget(): MotionBudget {
  return current;
}

/** Phones have far less to spend: fewer looks animated at once. */
const PHONE =
  typeof window !== "undefined" &&
  (window.matchMedia?.("(pointer: coarse)").matches || window.innerWidth < 700);

/** How many GPU looks may move at once (the others hold a still frame until hovered). */
export function liveLooks(): number {
  if (current === "still") return 0;
  if (current === "eco") return PHONE ? 2 : 3;
  return PHONE ? 4 : 8;
}

/** How many canvas ambiences (the page's, a profile's animated banner, the shop's previews) may run at
 * once — when saving, still the page's and the banner in view (at half the frame rate). */
export function liveAmbiences(): number {
  if (current === "still") return 0;
  if (current === "eco") return PHONE ? 2 : 3;
  return PHONE ? 2 : 6;
}

/** The frame interval of the canvas renderers (30 a second, 15 when saving). */
export function frameInterval(): number {
  return current === "eco" ? 1000 / 15 : 1000 / 30;
}
