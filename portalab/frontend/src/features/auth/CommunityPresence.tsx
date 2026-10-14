import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { useT } from "../../i18n/hooks/useT";
import { SettingsCard } from "../account/SettingsKit";

type Inventory = components["schemas"]["PrivacyInventory"];

const DATUM = "progression";
const CHOICES = [
  { key: "public", level: "community", icon: "users" },
  { key: "anonymous", level: "private", icon: "hide" },
] as const;

/**
 * « My presence in the community » (issue 120): public — my name and avatar beside my place in the
 * leaderboards and my activity — or anonymous — still counted, never named. It is the visibility of my
 * progression (013) for the other members; the privacy centre keeps the finer levels.
 */
export function CommunityPresence() {
  const t = useT();
  const notify = useNotify();
  const queryClient = useQueryClient();
  const inventory = useQuery({
    queryKey: ["privacy", "me"],
    queryFn: async () => (await api.GET("/api/v1/me/privacy")).data as Inventory,
  });
  const items = Array.isArray(inventory.data?.data) ? inventory.data.data : [];
  const datum = items.find((item) => item.datum_class === DATUM); // none (privacy off): no card
  const change = useMutation({
    mutationFn: async (level: "community" | "private") => {
      const result = await api.PUT("/api/v1/me/privacy/visibility/{datum_class}", {
        params: { path: { datum_class: DATUM } },
        body: { level },
      });
      if (result.error) throw new Error("presence");
    },
    onSuccess: () => {
      notify({ severity: "success", title: t("account:presence.saved") });
      void queryClient.invalidateQueries({ queryKey: ["privacy", "me"] });
      void queryClient.invalidateQueries({ queryKey: ["community"] });
    },
    onError: () => notify({ severity: "warning", title: t("account:error") }),
  });
  if (!datum) return null;
  const level = datum.effective_level;
  const current = level === "private" ? "anonymous" : level === "leaderboard" ? null : "public";
  const locked = Boolean(datum.locked_by_policy) || !datum.user_choosable;
  return (
    <SettingsCard
      icon="eye"
      title={t("account:presence.title")}
      hint={t("account:presence.hint")}
      aside={
        <Link to="/privacy" className="account-presence__more">
          {t("account:presence.more")}
        </Link>
      }
    >
      <fieldset className="account-presence" disabled={locked || change.isPending}>
        <legend className="visually-hidden">{t("account:presence.title")}</legend>
        {CHOICES.map((choice) => (
          <label key={choice.key} className="account-presence__choice" data-current={current === choice.key}>
            <input
              type="radio"
              name="community-presence"
              value={choice.key}
              checked={current === choice.key}
              onChange={() => change.mutate(choice.level)}
            />
            <span className="account-presence__icon" aria-hidden="true">
              <Icon name={choice.icon} size={20} />
            </span>
            <span className="account-presence__text">
              <strong>{t(`account:presence.${choice.key}`)}</strong>
              <span>{t(`account:presence.${choice.key}Hint`)}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {locked ? <p className="ds-field__hint">{t("account:presence.locked")}</p> : null}
      {current === null ? <p className="ds-field__hint">{t("account:presence.custom")}</p> : null}
    </SettingsCard>
  );
}
