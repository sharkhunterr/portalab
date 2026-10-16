import { AdminSection, KeyValues } from "../../../design-system/admin/AdminKit";
import { useT } from "../../../i18n/hooks/useT";
import type { VersionDetail } from "../api";

/** Import: where the version came from, its fingerprint, what it holds — and, for one of Portalab's own
 * packs updated by a release, what changed. */
export function ImportStep({ detail }: { detail: VersionDetail }) {
  const t = useT();
  const meta = detail.report.pack ?? {};
  const bytes = detail.report.elements.reduce((sum, e) => sum + (e.bytes || 0), 0);
  const changes = detail.changes;
  return (
    <>
      <AdminSection title={t("admin:visuals.step.import")} icon="inbox">
        <KeyValues
          items={[
            { key: "id", label: t("admin:visuals.field.id"), value: <code>{detail.pack}</code> },
            { key: "version", label: t("admin:visuals.field.version"), value: detail.version },
            { key: "sha", label: t("admin:visuals.field.fingerprint"), value: <code>{detail.sha}</code> },
            {
              key: "source",
              label: t("admin:visuals.field.source"),
              value: detail.builtin ? t("admin:visuals.builtin") : t("admin:visuals.field.imported"),
            },
            { key: "author", label: t("admin:visuals.field.author"), value: String(meta.author ?? "—") },
            { key: "license", label: t("admin:visuals.field.license"), value: String(meta.license ?? "—") },
            {
              key: "size",
              label: t("admin:visuals.field.size"),
              value: t("admin:visuals.sizeKb", { size: Math.ceil(bytes / 1024) }),
            },
            {
              key: "elements",
              label: t("admin:visuals.field.elements"),
              value: t("admin:visuals.elements", { count: detail.report.elements.length }),
            },
          ]}
        />
      </AdminSection>
      {changes ? (
        <AdminSection title={t("admin:visuals.changes.title")} icon="sync">
          <ul className="visuals-changes">
            {(["added", "removed", "changed"] as const).map((kind) =>
              changes[kind]?.length ? (
                <li key={kind}>
                  <strong>{t(`admin:visuals.changes.${kind}`)}</strong> {changes[kind]?.join(", ")}
                </li>
              ) : null,
            )}
          </ul>
        </AdminSection>
      ) : null}
    </>
  );
}
