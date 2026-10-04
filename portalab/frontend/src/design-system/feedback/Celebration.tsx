import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useAnnounce } from "../a11y/Announce";
import { sound } from "../sound/SoundService";
import { useTheme } from "../themes/ThemeProvider";

/**
 * Celebrations (spec 027 FR-007, R17): rewards and level-ups are acknowledged by a short, non-blocking
 * effect in the theme's style (``data-celebration``: sparkle, confetti, glow). At most one plays at a time
 * and at most one waits — further events are coalesced into the waiting one. Reduced motion replaces the
 * effect with a static badge; sounds follow the sound preference through ``SoundService``. The effect is
 * ``aria-hidden``; the message is announced politely.
 */

export interface CelebrationEvent {
  kind: "reward" | "level";
  /** Short visible text, e.g. "+40 XP" or "Level 5!". */
  text: string;
}

/** Coalescing queue: one playing, at most one pending; a pending level-up wins over rewards. */
export class CelebrationQueue {
  current: CelebrationEvent | null = null;
  pending: CelebrationEvent | null = null;

  push(event: CelebrationEvent): void {
    if (!this.current) {
      this.current = event;
      return;
    }
    if (this.pending?.kind === "level" && event.kind !== "level") return; // a waiting level-up wins
    this.pending = event; // newer replaces older: one effect for a burst of gains
  }

  next(): CelebrationEvent | null {
    this.current = this.pending;
    this.pending = null;
    return this.current;
  }
}

type Celebrate = (event: CelebrationEvent) => void;
const CelebrationContext = createContext<Celebrate>(() => {});

export function useCelebrate(): Celebrate {
  return useContext(CelebrationContext);
}

const DURATION_MS = { reward: 1400, level: 2600 } as const;
const PARTICLES = 18;

export function CelebrationProvider({ children }: { children: ReactNode }) {
  const queue = useRef(new CelebrationQueue());
  const [shown, setShown] = useState<CelebrationEvent | null>(null);
  const announce = useAnnounce();
  const { effective } = useTheme();
  const reduced = effective.reducedMotion;

  const celebrate = useCallback<Celebrate>((event) => {
    const idle = queue.current.current === null;
    queue.current.push(event);
    if (idle) setShown(queue.current.current);
  }, []);

  useEffect(() => {
    if (!shown) return;
    announce(shown.text);
    void sound.play(shown.kind === "level" ? "levelUp" : "reward");
    const timer = window.setTimeout(() => setShown(queue.current.next()), DURATION_MS[shown.kind]);
    return () => window.clearTimeout(timer);
  }, [shown, announce]);

  const value = useMemo(() => celebrate, [celebrate]);
  return (
    <CelebrationContext.Provider value={value}>
      {children}
      {shown ? <CelebrationLayer event={shown} reduced={reduced} /> : null}
    </CelebrationContext.Provider>
  );
}

function CelebrationLayer({ event, reduced }: { event: CelebrationEvent; reduced: boolean }) {
  return (
    <div
      className="ds-celebration"
      data-kind={event.kind}
      data-reduced={reduced ? "true" : undefined}
      aria-hidden="true"
    >
      {reduced ? null : (
        <div className="ds-celebration__particles">
          {Array.from({ length: PARTICLES }, (_, index) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: decorative particles
              key={index}
              className="ds-celebration__particle"
              style={{ "--i": index, "--n": PARTICLES } as React.CSSProperties}
            />
          ))}
        </div>
      )}
      <span className="ds-celebration__badge">{event.text}</span>
    </div>
  );
}
