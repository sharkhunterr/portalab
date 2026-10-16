import { Link } from "react-router";
import { AdminPage, AdminSection, StatusBadge } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { ApiError } from "../../../state/regions";
import { ImportPanel } from "../../extensions/ImportPanel";
import "../../extensions/extensions.css";
import { useModules, usePluginActions } from "../api";

/** ``/admin/modules`` (spec 023 T029): first-party modules, their dependencies, enable/disable. */
export default function ModulesAdmin() {
  const t = useT();
  const modules = useModules();
  const action = usePluginActions();
  return (
    <AdminPage icon="plug" title={t("plugins:modules.title")} description={t("plugins:modules.description")}>
      {/* 028 (issue 138): every tab of Extensions opens with its import — modules come with Portalab itself,
          so this one says where a new feature comes from instead */}
      <ImportPanel
        title={t("admin:extensions.import")}
        description={t("plugins:modules.importHelp")}
        sources={[
          {
            key: "plugin",
            icon: "plug",
            label: t("plugins:modules.importPlugin"),
            hint: t("plugins:modules.importPluginHint"),
            render: ({ className, children }) => (
              <Link className={className} to="/admin/plugins">
                {children}
              </Link>
            ),
          },
          {
            key: "release",
            icon: "package",
            label: t("plugins:modules.importRelease"),
            hint: t("plugins:modules.importReleaseHint"),
            render: ({ className, children }) => (
              <span className={className} aria-disabled="true">
                {children}
              </span>
            ),
          },
        ]}
      />
      {modules.isError ? <FunctionalState state="unavailable" /> : null}
      {action.error instanceof ApiError ? <p role="alert">{action.error.message}</p> : null}
      {/* 028 (issue 138): compact — the kernel's modules in one line of names (they never stop), the others
          one short row each: what it needs, its state, the switch */}
      <AdminSection title={t("plugins:modules.title")} icon="dashboard" flush>
        <p className="mod-kernel">
          <strong>{t("plugins:modules.essential")}</strong>{" "}
          {(modules.data ?? [])
            .filter((module) => module.essential)
            .map((module) => module.key)
            .join(" · ")}
        </p>
        <ul className="mod-list mod-list__modules">
          {(modules.data ?? [])
            .filter((module) => !module.essential)
            .map((module) => (
              <li key={module.key} data-enabled={module.enabled || undefined}>
                <span className="mod-list__name">
                  <strong>{module.key}</strong>
                  {module.requires.length ? (
                    <span>{t("plugins:modules.requires", { list: module.requires.join(", ") })}</span>
                  ) : null}
                  {module.needs_restart ? <span>{t("plugins:needsRestart")}</span> : null}
                </span>
                <StatusBadge tone={module.enabled ? "ok" : "neutral"}>
                  {module.enabled ? t("plugins:modules.enabled") : t("plugins:modules.disabled")}
                </StatusBadge>
                <Button
                  variant="ghost"
                  onClick={() =>
                    action.mutate({
                      path: `/api/v1/admin/modules/${module.key}/${module.enabled ? "disable" : "enable"}`,
                      body: module.enabled ? { cascade: window.confirm(t("plugins:modules.cascade")) } : {},
                    })
                  }
                >
                  {module.enabled ? t("plugins:actions.disable") : t("plugins:actions.enable")}
                </Button>
              </li>
            ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}
