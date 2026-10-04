import { useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { useAutomationAdmin, useTemplates } from "../api";

/** Preset templates (spec 019 T029): instantiating creates a draft to review before publishing. */
export function Gallery() {
  const t = useT();
  const templates = useTemplates();
  const { instantiate } = useAutomationAdmin();
  const [keys, setKeys] = useState<Record<string, string>>({});
  return (
    <AdminSection title={t("automations:templates.title")} icon="sparkles">
      <ul className="ds-stack">
        {(templates.data ?? []).map((template) => (
          <li key={template.key} className="ds-card ds-stack">
            <h3>{template.title}</h3>
            <p>{template.description}</p>
            {template.valid ? (
              <div className="ds-stack--row">
                <TextField
                  label={t("automations:identifier")}
                  value={keys[template.key] ?? template.key}
                  onChange={(e) => setKeys({ ...keys, [template.key]: e.target.value })}
                />
                <Button
                  onClick={() =>
                    instantiate.mutate({ template: template.key, key: keys[template.key] ?? template.key })
                  }
                >
                  {t("automations:templates.use")}
                </Button>
              </div>
            ) : (
              <p className="automation-meta">{t("automations:templates.invalid")}</p>
            )}
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
