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
/** issue 243: what makes a member seen by the others — their progression, their place in the members'
 * directory and their activity. Issue 347: public or anonymous, the member stays in the directory and the
 * activity; anonymous only takes their name and avatar away (their progression kept to themselves). */
const PRESENT = ["member_listing", "community_activity"] as const;
export const PRESENCE_CHOICES = [
  { key: "public", level: "community", icon: "users" },
  { key: "anonymous", level: "private", icon: "hide" },
] as const;
export type PresenceLevel = (typeof PRESENCE_CHOICES)[number]["level"];

/** Public (``community``) or anonymous (``private``): the progression's level, and the member back in the
 * directory and the activity; only the progression's answer counts (the others may be off, or set by an
 * administrator). */
export async function setPresence(level: PresenceLevel): Promise<void> {
  const results = await Promise.all(
    [{ datum: DATUM, level }, ...PRESENT.map((datum) => ({ datum, level: "community" as const }))].map(
      ({ datum, level: chosen }) =>
        api.PUT("/api/v1/me/privacy/visibility/{datum_class}", {
          params: { path: { datum_class: datum } },
          body: { level: chosen },
        }),
    ),
  );
  if (results[0]?.error) throw new Error("presence");
}

/** Issue 347: the member's presence as it stands — none when the privacy centre is off; ``current`` is null
 * for a finer level set in the privacy centre (a leaderboard-only progression, or kept out of the directory
 * or the activity). Asked at the welcome, whatever the play gauge, and here. */
export function usePresence() {
  const inventory = useQuery({
    queryKey: ["privacy", "me"],
    queryFn: async () => (await api.GET("/api/v1/me/privacy")).data as Inventory,
  });
  const items = Array.isArray(inventory.data?.data) ? inventory.data.data : [];
  const datum = items.find((item) => item.datum_class === DATUM);
  const level = datum?.effective_level;
  const away = items.some(
    (item) => (PRESENT as readonly string[]).includes(item.datum_class) && item.effective_level === "private",
  );
  const current: PresenceLevel | null =
    away || level === "leaderboard" ? null : level === "private" ? "private" : "community";
  return {
    available: Boolean(datum),
    current,
    locked: Boolean(datum?.locked_by_policy) || !datum?.user_choosable,
  };
}

/**
 * « My presence in the community » (issue 120): public — my name and avatar beside my place in the
 * leaderboards and my activity — or anonymous — still counted, never named. It is the visibility of my
 * progression (013) for the other members; the privacy centre keeps the finer levels.
 */
export function CommunityPresence() {
  const t = useT();
  const notify = useNotify();
  const queryClient = useQueryClient();
  const { available, current, locked } = usePresence();
  const change = useMutation({
    mutationFn: setPresence,
    onSuccess: () => {
      notify({ severity: "success", title: t("account:presence.saved") });
      void queryClient.invalidateQueries({ queryKey: ["privacy", "me"] });
      void queryClient.invalidateQueries({ queryKey: ["community"] });
    },
    onError: () => notify({ severity: "warning", title: t("account:error") }),
  });
  if (!available) return null; // none (privacy off): no card
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
        {PRESENCE_CHOICES.map((choice) => (
          <label
            key={choice.key}
            className="account-presence__choice"
            data-current={current === choice.level}
          >
            <input
              type="radio"
              name="community-presence"
              value={choice.key}
              checked={current === choice.level}
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
