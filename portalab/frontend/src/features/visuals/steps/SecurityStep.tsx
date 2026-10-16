import { AdminSection } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import type { VersionDetail } from "../api";
import { Findings, findingsByElement, nameOf, OutcomeBadge } from "../parts";

/** Security: per element, what its stylesheets and scripts would try and what Portalab refuses — in plain
 * words — and, when the version runs scripts, what a script may and may not do. */
export function SecurityStep({ detail }: { detail: VersionDetail }) {
  const t = useT();
  const byElement = findingsByElement(detail.report.items, "security");
  const general = byElement.get(null) ?? [];
  const concerned = detail.report.elements.filter((e) => byElement.get(e.product)?.length);
  return (
    <>
      <AdminSection
        title={t("admin:visuals.step.security")}
        icon="shield"
        actions={<OutcomeBadge outcome={detail.outcomes.security ?? "todo"} />}
      >
        <Findings findings={general} />
        {concerned.length === 0 && general.length === 0 ? (
          <p className="visuals-empty">{t("admin:visuals.security.none")}</p>
        ) : null}
        <ul className="visuals-elements">
          {concerned.map((element) => (
            <li className="visuals-element" key={element.product}>
              <div className="visuals-element__body">
                <p className="visuals-element__name">
                  {nameOf(element.names, element.product)}
                  <span className="visuals-element__type">{t(`admin:visuals.kind.${element.kind}`)}</span>
                </p>
                <Findings findings={byElement.get(element.product) ?? []} />
              </div>
            </li>
          ))}
        </ul>
      </AdminSection>
      {detail.report.summary.script ? (
        <AdminSection title={t("admin:visuals.security.scripts")} icon="code">
          <div className="visuals-rules">
            <div>
              <p className="visuals-rules__title">{t("admin:visuals.security.mayTitle")}</p>
              <p>{t("admin:visuals.security.may")}</p>
            </div>
            <div>
              <p className="visuals-rules__title">{t("admin:visuals.security.mayNotTitle")}</p>
              <p>{t("admin:visuals.security.mayNot")}</p>
            </div>
          </div>
        </AdminSection>
      ) : null}
    </>
  );
}
