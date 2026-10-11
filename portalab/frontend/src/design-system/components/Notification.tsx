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
import { Link, useInRouterContext } from "react-router";
import { usePreferences } from "../a11y/PreferencesProvider";
import { sound } from "../sound/SoundService";
import { FX_NOTIFICATION_ANIMATIONS, FX_NOTIFICATION_SHAPES, FX_STYLES } from "../themes/premium/fxLooks";
import { useTheme } from "../themes/ThemeProvider";
import { FxLayer } from "./Fx";
import { Icon } from "./Icon";

/**
 * Notifications (spec 022 T035; 027 redesign — delivery belongs to 010). A card with a coloured icon by
 * tone, a title, a short description, an optional image, badge and link, and a countdown bar until it goes
 * away. Its *style* (card, banner, capsule, minimal, frosted glass, neon) and *animation* (slide, fade,
 * pop, zoom, bounce, flip, swing) are the member's choice, independent of the theme — some are sold in the
 * shop. Severity is always icon + text (never colour alone); reduced motion removes every animation;
 * sounds go through the ``SoundService`` (sound-off honoured, no autoplay before a gesture).
 */
export type Severity = "info" | "success" | "warning" | "critical";
export type NotificationTone = Severity | "reward";

const SEVERITY_LABEL: Record<Severity, string> = {
  info: "Information",
  success: "Success",
  warning: "Warning",
  critical: "Critical",
};
const TONE_ICON: Record<NotificationTone, string> = {
  info: "bell",
  success: "check",
  warning: "warning",
  critical: "alert",
  reward: "trophy",
};

export interface NotificationItem {
  id: string;
  severity: Severity;
  title: string;
  body?: string;
  /** 027: richer cards — colour family, icon, link, image (a portal URL) and a short badge. */
  tone?: NotificationTone | undefined;
  icon?: string | undefined;
  href?: string | undefined;
  linkLabel?: string | undefined;
  image?: string | undefined;
  badge?: string | undefined;
}

/** The notification area lives outside the router: navigate through it when present, else a plain link. */
function NotificationLink({
  href,
  label,
  onFollow,
}: {
  href: string;
  label: string;
  onFollow?: (() => void) | undefined;
}) {
  const routed = useInRouterContext();
  const body = (
    <>
      {label}
      <Icon name="chevron-right" size={14} />
    </>
  );
  if (!routed) {
    return (
      <a
        className="ds-notification__link"
        href={href}
        onClick={(event) => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
          event.preventDefault(); // stay in the app: the router follows history changes
          window.history.pushState({}, "", href);
          window.dispatchEvent(new PopStateEvent("popstate"));
          onFollow?.();
        }}
      >
        {body}
      </a>
    );
  }
  return (
    <RoutedLink href={href} onFollow={onFollow}>
      {body}
    </RoutedLink>
  );
}

function RoutedLink({
  href,
  onFollow,
  children,
}: {
  href: string;
  onFollow?: (() => void) | undefined;
  children: ReactNode;
}) {
  return (
    <Link className="ds-notification__link" to={href} onClick={onFollow}>
      {children}
    </Link>
  );
}

export function Notification({
  item,
  onDismiss,
  durationMs,
  leaving = false,
  fx,
  fxShape,
  burst,
}: {
  item: NotificationItem;
  onDismiss?: () => void;
  durationMs?: number | undefined;
  /** 027: playing its exit animation. */
  leaving?: boolean;
  /** #78: the GPU effect of the chosen style, drawn behind it */
  fx?: string | undefined;
  /** #78: the shape it draws itself in (not always a rectangle) */
  fxShape?: number | undefined;
  /** #78: the GPU effect bursting as it appears and as it leaves (its animation) */
  burst?: string | undefined;
}) {
  const tone = item.tone ?? item.severity;
  const internal = item.href?.startsWith("/") && !item.href.startsWith("//");
  return (
    <div
      className="ds-notification"
      data-severity={item.severity}
      data-tone={tone}
      data-leaving={leaving || undefined}
      data-fx={fx}
      data-burst={burst ? "true" : undefined}
      data-fx-shape={fx ? (fxShape ?? 0) : undefined}
      role={item.severity === "critical" ? "alert" : "status"}
    >
      {fx ? <FxLayer effect={fx} calm shape={fxShape ?? 0} /> : null}
      {burst ? (
        // only around it: the notification keeps the look chosen for it — the animation is only its arrival
        <FxLayer effect={`burst:${burst}`} shape={fxShape ?? 0} aura className="fx-layer fx-layer--burst" />
      ) : null}
      <span className="ds-notification__icon" aria-hidden="true">
        <Icon name={item.icon ?? TONE_ICON[tone]} size={20} />
      </span>
      <div className="ds-notification__content">
        <p className="ds-notification__head">
          <span className="visually-hidden">{SEVERITY_LABEL[item.severity]}: </span>
          <strong className="ds-notification__title">{item.title}</strong>
          {item.badge ? <span className="ds-notification__badge">{item.badge}</span> : null}
        </p>
        {item.body ? <p className="ds-notification__body">{item.body}</p> : null}
        {item.href && internal ? (
          <NotificationLink href={item.href} label={item.linkLabel ?? "Open"} onFollow={onDismiss} />
        ) : null}
      </div>
      {item.image ? <img className="ds-notification__image" src={item.image} alt="" /> : null}
      {onDismiss ? (
        <button
          type="button"
          className="ds-notification__close"
          onClick={onDismiss}
          aria-label={`Dismiss: ${item.title}`}
        >
          <Icon name="close" size={16} />
        </button>
      ) : null}
      {durationMs && item.severity !== "critical" ? (
        <span className="ds-notification__timer" style={{ animationDuration: `${durationMs}ms` }} />
      ) : null}
    </div>
  );
}

/** 027: how long a notification takes to leave (its exit animation). */
const EXIT_MS = 520;
const FX_EXIT_MS = 800;

interface NotifyContextValue {
  notify: (item: Omit<NotificationItem, "id">) => void;
}

const NotifyContext = createContext<NotifyContextValue>({ notify: () => undefined });

export function NotificationArea({ children }: { children: ReactNode }) {
  const { preferences } = usePreferences();
  const { looks, effective } = useTheme(); // 027: the member's look, or the theme's when they follow it
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [paused, setPaused] = useState(false);
  const counter = useRef(0);
  sound.enabled = preferences.soundEnabled;
  // 027: a notification leaves with its animation (sucked into a black hole, melting…) before it goes
  const [leaving, setLeaving] = useState<ReadonlySet<string>>(new Set());
  const reduced = effective.reducedMotion;
  const dismiss = useCallback(
    (id: string) => {
      const remove = () => {
        setItems((current) => current.filter((i) => i.id !== id));
        setLeaving((current) => {
          const next = new Set(current);
          next.delete(id);
          return next;
        });
      };
      if (reduced) {
        remove();
        return;
      }
      setLeaving((current) => new Set(current).add(id));
      // #78: an animation drawn by the GPU bursts again as it leaves — a little longer to see it
      window.setTimeout(
        remove,
        FX_NOTIFICATION_ANIMATIONS[looks.notificationAnimation] ? FX_EXIT_MS : EXIT_MS,
      );
    },
    [reduced, looks.notificationAnimation],
  );
  const notify = useCallback((item: Omit<NotificationItem, "id">) => {
    counter.current += 1;
    const id = `n${counter.current}`;
    setItems((current) => [...current, { ...item, id }].slice(-5)); // never more than five at once
    void sound.play(
      item.severity === "critical" ? "alert" : item.tone === "reward" ? "reward" : "notification",
    );
  }, []);
  const durationMs = preferences.notificationDurationSeconds * 1000;
  useEffect(() => {
    if (!items.length || paused) return;
    const oldest = items.find((i) => i.severity !== "critical" && !leaving.has(i.id));
    if (!oldest) return; // critical notifications stay until dismissed
    const timer = setTimeout(() => dismiss(oldest.id), durationMs);
    return () => clearTimeout(timer);
  }, [items, durationMs, dismiss, paused, leaving]);
  const value = useMemo(() => ({ notify }), [notify]);
  const style = looks.notificationStyle === "banner" ? " ds-notifications--banner" : "";
  return (
    <NotifyContext.Provider value={value}>
      {children}
      <section
        className={`ds-notifications ds-notifications--${preferences.notificationPosition}${style}`}
        aria-label="Notifications"
        data-position={preferences.notificationPosition}
        data-style={looks.notificationStyle}
        data-animation={looks.notificationAnimation}
        data-paused={paused || undefined}
        onPointerEnter={() => setPaused(true)}
        onPointerLeave={() => setPaused(false)}
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
      >
        {items.map((item) => (
          <Notification
            key={item.id}
            item={item}
            onDismiss={() => dismiss(item.id)}
            durationMs={durationMs}
            leaving={leaving.has(item.id)}
            fx={FX_STYLES[looks.notificationStyle]}
            fxShape={FX_NOTIFICATION_SHAPES[looks.notificationStyle]}
            burst={FX_NOTIFICATION_ANIMATIONS[looks.notificationAnimation]}
          />
        ))}
      </section>
    </NotifyContext.Provider>
  );
}

export function useNotify(): NotifyContextValue["notify"] {
  return useContext(NotifyContext).notify;
}
