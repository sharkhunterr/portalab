import { AdminSection } from "../../../design-system/admin/AdminKit";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { SavedNote, Switch } from "../../account/SettingsKit";
import { useHouseholdGrouping } from "./tuning";

/**
 * Issue 441: whether a household profile's XP, contribution and statistics also count on its master's account
 * (« group », as before) or stay the profile's own (« dispatch »). The Coins are the household's either way.
 */
export function HouseholdGrouping() {
  const t = useT();
  const { query, save } = useHouseholdGrouping();
  if (query.isPending) return <FunctionalState state="loading" />;
  const grouped = save.isPending ? Boolean(save.variables) : (query.data?.grouped ?? true);
  return (
    <AdminSection
      icon="users"
      title={t("gamification:admin.household.title")}
      description={t("gamification:admin.household.hint")}
    >
      <Switch
        label={t("gamification:admin.household.grouped")}
        checked={grouped}
        disabled={save.isPending}
        onChange={(e) => save.mutate(e.target.checked)}
      />
      <p className="admin-muted">
        {grouped
          ? t("gamification:admin.household.groupedHint")
          : t("gamification:admin.household.dispatchedHint")}{" "}
        <SavedNote shown={save.isSuccess} text={t("gamification:admin.household.saved")} />
      </p>
    </AdminSection>
  );
}
