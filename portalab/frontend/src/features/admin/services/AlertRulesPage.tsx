import { AdminPage, AdminSection } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import { AlertRulesPanel } from "./AlertRules";
import "../admin.css";

/**
 * ``/admin/services/alerts`` (admin reorganisation, trial): when a service goes down — an incident after a
 * delay, who is told, a banner — one rule per importance; each service may still override it in its form.
 */
export default function AlertRulesPage() {
  const t = useT();
  return (
    <AdminPage icon="bell" title={t("admin:alerting.title")} description={t("admin:alerting.description")}>
      <AdminSection title={t("admin:alerting.byImportance")} icon="shield" span="full">
        <AlertRulesPanel />
      </AdminSection>
    </AdminPage>
  );
}
