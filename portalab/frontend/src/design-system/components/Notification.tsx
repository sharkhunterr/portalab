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
import { usePreferences } from "../a11y/PreferencesProvider";
import { sound } from "../sound/SoundService";
import { FunctionalState } from "../state/FunctionalState";
import type { FunctionalStateName } from "../state/stateMap";

/**
 * Notification appearance primitives (spec 022 T035; delivery belongs to 010). Position, duration and
 * style come from the user's preferences; severity is always icon + text (style/position never change the
 * meaning); reduced motion removes the entrance animation through the shared tokens; sounds go through the
 * ``SoundService`` (sound-off honoured, no autoplay before a gesture).
 */
export type Severity = "info" | "success" | "warning" | "critical";

const SEVERITY_STATE: Record<Severity, FunctionalStateName> = {
  info: "available",
  success: "available",
  warning: "partial",
  critical: "error",
};
const SEVERITY_LABEL: Record<Severity, string> = {
  info: "Information",
  success: "Success",
  warning: "Warning",
  critical: "Critical",
};

export interface NotificationItem {
  id: string;
  severity: Severity;
  title: string;
  body?: string;
}

export function Notification({ item, onDismiss }: { item: NotificationItem; onDismiss?: () => void }) {
  return (
    <div
      className="ds-notification"
      data-severity={item.severity}
      role={item.severity === "critical" ? "alert" : "status"}
    >
      <FunctionalState state={SEVERITY_STATE[item.severity]} label={SEVERITY_LABEL[item.severity]} />
      <div>
        <strong>{item.title}</strong>
        {item.body ? <p>{item.body}</p> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          className="ds-button ds-button--secondary"
          onClick={onDismiss}
          aria-label={`Dismiss: ${item.title}`}
        >
          ×
        </button>
      ) : null}
    </div>
  );
}

interface NotifyContextValue {
  notify: (item: Omit<NotificationItem, "id">) => void;
}

const NotifyContext = createContext<NotifyContextValue>({ notify: () => undefined });

export function NotificationArea({ children }: { children: ReactNode }) {
  const { preferences } = usePreferences();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const counter = useRef(0);
  sound.enabled = preferences.soundEnabled;
  const dismiss = useCallback((id: string) => setItems((current) => current.filter((i) => i.id !== id)), []);
  const notify = useCallback((item: Omit<NotificationItem, "id">) => {
    counter.current += 1;
    const id = `n${counter.current}`;
    setItems((current) => [...current, { ...item, id }]);
    void sound.play(item.severity === "critical" ? "alert" : "notification");
  }, []);
  const durationMs = preferences.notificationDurationSeconds * 1000;
  useEffect(() => {
    if (!items.length) return;
    const oldest = items.find((i) => i.severity !== "critical");
    if (!oldest) return; // critical notifications stay until dismissed
    const timer = setTimeout(() => dismiss(oldest.id), durationMs);
    return () => clearTimeout(timer);
  }, [items, durationMs, dismiss]);
  const value = useMemo(() => ({ notify }), [notify]);
  const style = preferences.notificationStyle === "banner" ? " ds-notifications--banner" : "";
  return (
    <NotifyContext.Provider value={value}>
      {children}
      <section
        className={`ds-notifications ds-notifications--${preferences.notificationPosition}${style}`}
        aria-label="Notifications"
        data-position={preferences.notificationPosition}
      >
        {items.map((item) => (
          <Notification key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
        ))}
      </section>
    </NotifyContext.Provider>
  );
}

export function useNotify(): NotifyContextValue["notify"] {
  return useContext(NotifyContext).notify;
}
