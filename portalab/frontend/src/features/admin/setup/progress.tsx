import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useSite } from "../../../shell/site/site";
import { type SettingItem, useSettings } from "../ConfigEditor";
import "./setup.css";

/** Issue 6: the setup assistant's steps, where it is (kept by the server) and what is ready — shared by the
 * assistant and the Control Center's card (which does not load the assistant's screens). */
export type StepKey =
  | "identity"
  | "features"
  | "account"
  | "access"
  | "services"
  | "members"
  | "media"
  | "communication"
  | "appearance"
  | "play"
  | "ai"
  | "summary";

export interface Step {
  key: StepKey;
  icon: string;
  settings?: readonly string[];
  links?: ReadonlyArray<readonly [to: string, label: string]>;
}

export const STEPS: readonly Step[] = [
  {
    key: "identity",
    icon: "sparkles",
    settings: [
      "i18n.defaultLanguage",
      "i18n.defaultLocale",
      "i18n.defaultTimeZone",
      "notifications.email.portalUrl",
    ],
  },
  { key: "features", icon: "blocks", links: [["/admin/modules", "modules"]] }, // issue 246
  {
    key: "account",
    icon: "user",
    links: [
      ["/account", "account"],
      ["/admin/roles", "roles"],
    ],
  },
  {
    key: "access",
    icon: "users",
    settings: [
      "identity.registrationMode",
      "identity.oidc.enabled",
      "identity.oidc.label",
      "identity.oidc.issuer",
      "identity.oidc.clientId",
      "identity.oidc.clientSecret",
      "identity.oidc.createAccounts",
      "identity.oidc.trustUnverifiedEmail",
    ],
    links: [["/admin/members", "members"]],
  },
  { key: "services", icon: "server", links: [["/admin/services", "services"]] },
  { key: "members", icon: "users", links: [["/admin/members", "members"]] }, // issue 246
  {
    key: "media",
    icon: "film",
    settings: ["media.requests.quotaPerPeriod", "media.requests.period"],
    links: [
      ["/admin/media-quotas", "quotas"],
      ["/admin/media-requests", "requests"],
      ["/admin/media-sources", "sources"],
    ],
  },
  {
    key: "communication",
    icon: "mail",
    links: [
      ["/admin/newsletters", "newsletters"],
      ["/admin/terms", "terms"],
      ["/admin/announcements", "announcements"],
    ],
  },
  {
    key: "appearance",
    icon: "palette",
    settings: ["ui.defaultTheme", "ui.allowedThemes"],
    links: [
      ["/admin/visuals", "visuals"],
      ["/admin/themes", "themes"],
    ],
  },
  {
    key: "play",
    icon: "trophy",
    settings: ["economy.timezone", "economy.contribution.amount"],
    links: [
      ["/admin/modules", "modules"],
      ["/admin/gamification", "gamification"],
      ["/admin/marketplace", "marketplace"],
    ],
  },
  {
    key: "ai",
    icon: "bot",
    settings: [
      "ai.enabled",
      "ai.provider.kind",
      "ai.provider.endpoint",
      "ai.provider.model",
      "ai.provider.apiKey",
    ],
    links: [["/admin/ai", "ai"]],
  },
  { key: "summary", icon: "check" },
];

export interface Progress {
  step?: StepKey;
  done?: StepKey[];
  skipped?: StepKey[];
  finished_at?: string | null;
}

const PROGRESS = "admin.setup.progress";

/** Where the assistant is, kept by the server (a global setting: every administrator sees the same). */
export function useSetupProgress() {
  const client = useQueryClient();
  const settings = useSettings();
  const progress = (settings.data?.find((s) => s.key === PROGRESS)?.value ?? {}) as Progress;
  const save = useMutation({
    mutationFn: async (next: Progress) => {
      await api.PUT("/api/v1/admin/config", {
        body: {
          changes: [{ key: PROGRESS, value: next, scope: "global", scope_ref: "", unset: false }],
          reason: "setup assistant",
        } as never,
      });
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["admin", "config"] }),
  });
  return { settings, progress, save };
}

/** Whether a step is ready, tested on the portal itself (``null``: nothing to test, its mark decides). */
export function useReadiness(settings: SettingItem[] | undefined): Partial<Record<StepKey, boolean>> {
  const site = useSite();
  const services = useQuery({
    queryKey: ["services", "health"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/services/health")).data as unknown as { items: unknown[] }).items ?? [],
  });
  const value = (key: string) => settings?.find((s) => s.key === key);
  const set = (key: string) => {
    const item = value(key);
    return Boolean(item && item.source !== "default");
  };
  return {
    identity: site.custom,
    services: (services.data?.length ?? 0) > 0,
    communication:
      Boolean(value("notifications.email.enabled")?.value) && set("notifications.email.smtp.host"),
    ai: Boolean(value("ai.enabled")?.value) && set("ai.provider.model"),
  };
}

/** The Control Center's card: where the assistant is, to continue it — or open it again once finished. */
export function SetupCard() {
  const t = useT();
  const { progress, settings } = useSetupProgress();
  const ready = useReadiness(settings.data);
  if (!settings.data) return null;
  const steps = STEPS.filter((s) => s.key !== "summary");
  const done = steps.filter((s) => ready[s.key] === true || progress.done?.includes(s.key)).length;
  const finished = Boolean(progress.finished_at);
  return (
    <div className="setup-card" data-finished={finished || undefined}>
      <Icon name="rocket" size={22} />
      <span className="setup-card__text">
        <strong>{t(finished ? "admin:setup.card.again" : "admin:setup.card.title")}</strong>
        <span>{t("admin:setup.card.progress", { done, total: steps.length })}</span>
      </span>
      <Link to="/admin/setup" className={`ds-button ${finished ? "ds-button--ghost" : "ds-button--primary"}`}>
        {t(
          finished
            ? "admin:setup.card.reopen"
            : progress.step
              ? "admin:setup.card.continue"
              : "admin:setup.card.start",
        )}
      </Link>
    </div>
  );
}
