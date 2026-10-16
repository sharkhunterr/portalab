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
import { isWithheld, useExternalRevision } from "../visuals/registry";
import {
  DEFAULT_POLICY,
  DEFAULT_PREFERENCES,
  PREFERENCE_KEYS,
  sanitize,
  type UiPolicy,
  type UiPreferences,
} from "./preferences";

/**
 * ``PreferencesProvider`` (spec 022 T017/T031): account-level UI preferences, mirrored to localStorage for
 * an instant first paint and synchronized with ``/me/preferences`` (020). Conflicts are resolved by a local
 * ``change_seq``: unsynced local changes are pushed, otherwise the server (other devices) wins.
 */

/** 028: the looks chosen in the preferences, as they show — a look of a pack switched off shows the default
 * (the choice itself is kept). */
function shown(preferences: UiPreferences): UiPreferences {
  const look = <K extends keyof UiPreferences>(key: K, type: string): UiPreferences[K] =>
    isWithheld(type, String(preferences[key])) ? DEFAULT_PREFERENCES[key] : preferences[key];
  return {
    ...preferences,
    notificationStyle: look("notificationStyle", "notification_style"),
    notificationAnimation: look("notificationAnimation", "notification_animation"),
    ambient: look("ambient", "ambient"),
    celebration: look("celebration", "effect"),
    palette: look("palette", "palette"),
    levelUp: look("levelUp", "level_up"),
  };
}

export const MIRROR_KEY = "portalab.ui";

interface Mirror {
  preferences: UiPreferences;
  policy?: UiPolicy | undefined;
  seq: number;
  synced: boolean;
}

export interface PreferenceBackend {
  load: () => Promise<{ preferences: Partial<Record<string, unknown>>; policy?: UiPolicy }>;
  save: (values: Record<string, unknown>) => Promise<void>;
}

interface PreferencesContextValue {
  preferences: UiPreferences;
  policy: UiPolicy;
  setPreference: <K extends keyof UiPreferences>(key: K, value: UiPreferences[K]) => void;
  synced: boolean;
  /** 027: values tried on for a moment (the shop's « Try it »), never saved; ``null`` ends the trial. */
  preview: Partial<UiPreferences> | null;
  setPreview: (values: Partial<UiPreferences> | null) => void;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function readMirror(): Mirror | null {
  try {
    const raw = window.localStorage.getItem(MIRROR_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Mirror>;
    return {
      preferences: sanitize(parsed.preferences ?? {}),
      policy: parsed.policy,
      seq: typeof parsed.seq === "number" ? parsed.seq : 0,
      synced: parsed.synced !== false,
    };
  } catch {
    return null;
  }
}

function writeMirror(mirror: Mirror): void {
  try {
    window.localStorage.setItem(MIRROR_KEY, JSON.stringify(mirror));
  } catch {
    // storage unavailable (private mode): preferences still work for this session
  }
}

/** Server values (``ui.*`` keys) → preference fields. */
export function fromServer(values: Partial<Record<string, unknown>>): UiPreferences {
  const raw: Record<string, unknown> = {};
  for (const [field, key] of Object.entries(PREFERENCE_KEYS)) {
    if (key in values) raw[field] = values[key];
  }
  return sanitize(raw);
}

export interface PreferencesProviderProps {
  children: ReactNode;
  backend?: PreferenceBackend;
  initial?: Partial<UiPreferences>;
  policy?: Partial<UiPolicy>;
}

export function PreferencesProvider({
  children,
  backend,
  initial,
  policy: policyOverride,
}: PreferencesProviderProps) {
  const mirror = useRef(readMirror());
  const [state, setState] = useState<Mirror>(() => ({
    preferences: { ...(mirror.current?.preferences ?? DEFAULT_PREFERENCES), ...(initial ?? {}) },
    policy: mirror.current?.policy,
    seq: mirror.current?.seq ?? 0,
    synced: mirror.current?.synced ?? true,
  }));
  const policy = useMemo<UiPolicy>(
    () => ({ ...DEFAULT_POLICY, ...(state.policy ?? {}), ...(policyOverride ?? {}) }),
    [state.policy, policyOverride],
  );

  useEffect(() => {
    writeMirror(state);
  }, [state]);

  useEffect(() => {
    if (!backend) return;
    let cancelled = false;
    backend
      .load()
      .then(async (loaded) => {
        if (cancelled) return;
        const pending = readMirror();
        if (pending && !pending.synced) {
          await backend.save(toServer(pending.preferences));
          setState((current) => ({ ...current, policy: loaded.policy ?? current.policy, synced: true }));
          return;
        }
        setState((current) => ({
          preferences: fromServer(loaded.preferences),
          policy: loaded.policy ?? current.policy,
          seq: current.seq,
          synced: true,
        }));
      })
      .catch(() => undefined); // offline: keep the mirror
    return () => {
      cancelled = true;
    };
  }, [backend]);

  const setPreference = useCallback(
    <K extends keyof UiPreferences>(key: K, value: UiPreferences[K]) => {
      setState((current) => ({
        ...current,
        preferences: { ...current.preferences, [key]: value },
        seq: current.seq + 1,
        synced: !backend,
      }));
      if (backend) {
        backend
          .save({ [PREFERENCE_KEYS[key]]: value })
          .then(() => setState((current) => ({ ...current, synced: true })))
          .catch(() => undefined);
      }
    },
    [backend],
  );

  const [preview, setPreview] = useState<Partial<UiPreferences> | null>(null);
  const revision = useExternalRevision();
  const preferences = useMemo(() => {
    void revision; // 028: a pack switched off or on changes what shows
    return shown(preview ? { ...state.preferences, ...preview } : state.preferences);
  }, [state.preferences, preview, revision]);
  const value = useMemo(
    () => ({ preferences, policy, setPreference, synced: state.synced, preview, setPreview }),
    [preferences, policy, setPreference, state.synced, preview],
  );
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function toServer(preferences: UiPreferences): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(PREFERENCE_KEYS).map(([field, key]) => [key, preferences[field as keyof UiPreferences]]),
  );
}

export function usePreferences(): PreferencesContextValue {
  const context = useContext(PreferencesContext);
  if (context) return context;
  return {
    preferences: DEFAULT_PREFERENCES,
    policy: DEFAULT_POLICY,
    setPreference: () => undefined,
    synced: true,
    preview: null,
    setPreview: () => undefined,
  };
}
