import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
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
    <div className="ds-stack">
      <PageHeader icon="plug" title={t("plugins:modules.title")} />
      {modules.isError ? <FunctionalState state="unavailable" /> : null}
      {action.error instanceof ApiError ? <p role="alert">{action.error.message}</p> : null}
      <ul className="ds-stack">
        {(modules.data ?? []).map((module) => (
          <li key={module.key} className="ds-card ds-stack--row">
            <strong>{module.key}</strong>
            <span>{module.enabled ? t("plugins:modules.enabled") : t("plugins:modules.disabled")}</span>
            {module.requires.length ? (
              <span className="community-meta">
                {t("plugins:modules.requires", { list: module.requires.join(", ") })}
              </span>
            ) : null}
            {module.needs_restart ? <span>{t("plugins:needsRestart")}</span> : null}
            {module.essential ? (
              <span className="community-meta">{t("plugins:modules.essential")}</span>
            ) : (
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
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
