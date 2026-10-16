import { AdminSection } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import type { VersionDetail } from "../api";
import { Findings, findingsByElement, nameOf, OutcomeBadge } from "../parts";

/** Analysis: what the version holds — its elements, their kinds and looks, and what the analysis found
 * about the format, the looks, the texts, the economy, the interfaces. */
export function AnalysisStep({ detail }: { detail: VersionDetail }) {
  const t = useT();
  const byElement = findingsByElement(detail.report.items, "analysis");
  const general = byElement.get(null) ?? [];
  return (
    <AdminSection
      title={t("admin:visuals.step.analysis")}
      icon="list"
      actions={<OutcomeBadge outcome={detail.outcomes.analysis ?? "todo"} />}
      description={t("admin:visuals.summary", {
        blocking: detail.report.summary.blocking,
        warning: detail.report.summary.warning,
        info: detail.report.summary.info,
      })}
    >
      <Findings findings={general} />
      <ul className="visuals-elements">
        {detail.report.elements.map((element) => (
          <li className="visuals-element" key={element.product}>
            <div className="visuals-element__body">
              <p className="visuals-element__name">
                {nameOf(element.names, element.product)}
                <span className="visuals-element__type">{t(`admin:visuals.type.${element.type}`)}</span>
                {element.hd ? (
                  <span className="visuals-flag" data-flag="hd">
                    HD
                  </span>
                ) : null}
              </p>
              <p className="visuals-element__meta">
                <code>{element.product}</code>
                {element.look ? (
                  <>
                    {" "}
                    · {t("admin:visuals.look")} <code>{element.look}</code>
                  </>
                ) : null}{" "}
                · {t(`admin:visuals.kind.${element.kind}`)} ·{" "}
                {t("admin:visuals.sizeKb", { size: Math.ceil(element.bytes / 1024) })}
              </p>
              <Findings findings={byElement.get(element.product) ?? []} />
            </div>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
