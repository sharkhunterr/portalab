import { api } from "../../api/client";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState, type FunctionalStateName } from "../../design-system/FunctionalState";
import { DataRegion } from "../../state/regions";
import { adminStrings as t } from "./strings";

interface Overview {
  panels: { panel: string; state: string; data: Record<string, unknown> }[];
  required_actions: { id: string; title_key: string; link: string; actionable: boolean }[];
}

/** Control Center (spec 020 US1): each panel shows its own state; one failing panel never hides the rest. */
export function ControlCenter() {
  return (
    <DataRegion<Overview>
      label={t.overviewTitle}
      queryKey={["admin", "overview"]}
      queryFn={async () => (await api.GET("/api/v1/admin/overview")).data as unknown as Overview}
    >
      {(overview) => (
        <div className="account-page">
          <PageHeader level={2} icon="dashboard" title={t.overviewTitle} />
          <ul className="panel-grid">
            {overview.panels.map((panel) => (
              <li key={panel.panel}>
                <h3>{panel.panel}</h3>
                {panel.state === "available" ? (
                  <dl>
                    {Object.entries(panel.data).map(([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <FunctionalState
                    state={panel.state as FunctionalStateName}
                    label={t.panelStates[panel.state] ?? panel.state}
                  />
                )}
              </li>
            ))}
          </ul>
          <h3>{t.requiredActions}</h3>
          {overview.required_actions.length === 0 ? (
            <p>{t.noActions}</p>
          ) : (
            <ol>
              {overview.required_actions.map((action) => (
                <li key={action.id}>
                  <a href={action.link}>{action.title_key}</a>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </DataRegion>
  );
}
