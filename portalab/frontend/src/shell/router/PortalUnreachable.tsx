import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { rememberedSite, useSite } from "../site/site";

/**
 * Issue 16 — the portal cannot be reached (restarting, maintenance, a cut): a page of its own instead of a
 * bare « Error / Retry » — the site's name, what is happening, a new try on its own (sooner, then less
 * often), a countdown and a « Retry » button. As soon as the portal answers, the same page comes back.
 */
const WAITS = [5, 10, 20, 30, 60] as const; // seconds between tries, the last one repeated
// the words when the catalogs themselves could not be read (the portal is away)
const FALLBACK: Record<string, string> = {
  "shell:down.title": "The portal is unavailable for a moment",
  "shell:down.text": "It may be restarting or under maintenance. Your page will come back on its own.",
  "shell:down.next": "Trying again in {seconds} s…",
  "shell:down.trying": "Trying again…",
  "shell:retry": "Retry",
};

/** Whether the portal answers (its liveness, never cached). */
export async function portalAnswers(): Promise<boolean> {
  try {
    const answer = await fetch("/livez", { cache: "no-store" });
    return answer.ok;
  } catch {
    return false;
  }
}

export function PortalUnreachable({ onBack }: { onBack?: () => void }) {
  const t = useT();
  const live = useSite();
  const site = live.custom ? live : (rememberedSite() ?? live); // the portal is away: its last known name
  const say = (key: string, values?: Record<string, number>) => {
    const text = t(key, values);
    if (text !== key.split(":")[1] && text !== key) return text;
    const fallback = FALLBACK[key] ?? key;
    return values
      ? fallback.replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? ""))
      : fallback;
  };
  const [attempt, setAttempt] = useState(0);
  const [left, setLeft] = useState<number>(WAITS[0]);
  const [trying, setTrying] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const back = useCallback(() => (onBack ? onBack() : window.location.reload()), [onBack]);

  const tryNow = useCallback(async () => {
    setTrying(true);
    const up = await portalAnswers();
    setTrying(false);
    if (up) {
      back();
      return;
    }
    setAttempt((n) => n + 1);
  }, [back]);

  useEffect(() => {
    button.current?.focus();
  }, []);

  // the countdown to the next try, longer each time
  useEffect(() => {
    const wait = WAITS[Math.min(attempt, WAITS.length - 1)] ?? 60;
    setLeft(wait);
    const timer = window.setInterval(() => {
      setLeft((s) => {
        if (s <= 1) {
          window.clearInterval(timer);
          void tryNow();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [attempt, tryNow]);

  return (
    <main className="portal-down" role="alert" aria-live="assertive">
      <div className="portal-down__card">
        <p className="portal-down__brand">
          {site.icon ? <img src={site.icon} alt="" width={28} height={28} /> : null}
          {site.name}
        </p>
        <span className="portal-down__art" aria-hidden="true">
          <Icon name="server" size={40} />
          <span className="portal-down__pulse" />
        </span>
        <h1 className="portal-down__title">{say("shell:down.title")}</h1>
        <p className="portal-down__text">{say("shell:down.text")}</p>
        <p className="portal-down__next" aria-live="polite">
          {trying || left === 0 ? say("shell:down.trying") : say("shell:down.next", { seconds: left })}
        </p>
        <button
          ref={button}
          type="button"
          className="ds-button ds-button--primary portal-down__retry"
          onClick={() => void tryNow()}
          disabled={trying}
        >
          <Icon name="retry" size={16} />
          {say("shell:retry")}
        </button>
      </div>
    </main>
  );
}
