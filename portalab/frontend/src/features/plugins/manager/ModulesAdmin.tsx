import { AdminPage, AdminSection, AdminTable, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { useModules, usePluginActions } from "../api";

/** ``/admin/modules`` (spec 023 T029): first-party modules, their dependencies, enable/disable. */
export default function ModulesAdmin() {
  const t = useT();
  const modules = useModules();
  const action = usePluginActions();
  return (
    <AdminPage icon="plug" title={t("plugins:modules.title")} description={t("plugins:modules.description")}>
      {modules.isError ? <FunctionalState state="unavailable" /> : null}
      {action.error instanceof ApiError ? <p role="alert">{action.error.message}</p> : null}
      <AdminSection title={t("plugins:modules.title")} icon="dashboard" flush>
        <AdminTable
          label={t("plugins:modules.title")}
          rows={modules.data ?? []}
          rowKey={(module) => module.key}
          columns={[
            {
              key: "key",
              header: t("plugins:modules.module"),
              primary: true,
              render: (module) => (
                <span className="services-admin__name">
                  <strong>{module.key}</strong>
                  {module.requires.length ? (
                    <span className="admin-muted">
                      {t("plugins:modules.requires", { list: module.requires.join(", ") })}
                    </span>
                  ) : null}
                </span>
              ),
            },
            {
              key: "state",
              header: t("plugins:modules.state"),
              render: (module) => (
                <StatusBadge tone={module.enabled ? "ok" : "neutral"}>
                  {module.enabled ? t("plugins:modules.enabled") : t("plugins:modules.disabled")}
                </StatusBadge>
              ),
            },
            {
              key: "notes",
              header: t("plugins:modules.notes"),
              render: (module) =>
                [
                  module.essential ? t("plugins:modules.essential") : null,
                  module.needs_restart ? t("plugins:needsRestart") : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "—",
            },
          ]}
          actions={(module) =>
            module.essential ? null : (
              <Button
                variant="secondary"
                onClick={() =>
                  action.mutate({
                    path: `/api/v1/admin/modules/${module.key}/${module.enabled ? "disable" : "enable"}`,
                    body: module.enabled ? { cascade: window.confirm(t("plugins:modules.cascade")) } : {},
                  })
                }
              >
                {module.enabled ? t("plugins:actions.disable") : t("plugins:actions.enable")}
              </Button>
            )
          }
        />
      </AdminSection>
    </AdminPage>
  );
}
