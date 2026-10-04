import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { PageHeader } from "../../design-system/components/PageHeader";
import { DataRegion } from "../../state/regions";
import { type LevelKey, privacyStrings as t } from "./strings";

type Inventory = components["schemas"]["PrivacyInventory"];

/** "Profile / Data Center": inventory, effective visibility, admin locks, retention, export/delete (CD-016). */
export function PrivacyCenter() {
  return (
    <DataRegion<Inventory>
      label={t.centerTitle}
      queryKey={["privacy", "me"]}
      queryFn={async () => (await api.GET("/api/v1/me/privacy")).data as Inventory}
    >
      {(inventory) => (
        <div className="account-page">
          <PageHeader level={2} icon="shield" title={t.centerTitle} />
          <p>{t.centerIntro}</p>
          <table>
            <caption className="sr-only">{t.centerTitle}</caption>
            <thead>
              <tr>
                <th scope="col">{t.dataClass}</th>
                <th scope="col">{t.owner}</th>
                <th scope="col">{t.classification}</th>
                <th scope="col">{t.visibility}</th>
                <th scope="col">{t.retention}</th>
              </tr>
            </thead>
            <tbody>
              {inventory.data.map((item) => (
                <tr key={item.datum_class}>
                  <th scope="row">{item.description || item.datum_class}</th>
                  <td>{item.owner.replace(/^module:/, "")}</td>
                  <td>{item.classification}</td>
                  <td>
                    {t.levels[item.effective_level as LevelKey] ?? item.effective_level}
                    {item.locked_by_policy ? <p className="field-hint">{t.locked}</p> : null}
                  </td>
                  <td>{item.retention_days ? t.retentionDays(item.retention_days) : t.retentionNone}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            <a href={inventory.export_endpoint}>{t.exportLink}</a>
          </p>
          <p>
            <a href="#delete-account">{t.deletionLink}</a>
          </p>
        </div>
      )}
    </DataRegion>
  );
}
