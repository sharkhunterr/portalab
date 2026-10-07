import { Link } from "react-router";
import { StatusBadge } from "../../../design-system/admin/AdminKit";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useTemplates } from "../api";
import { FlowView } from "../flow/FlowView";

/**
 * Templates (spec 019 T029; 027 redesign): each one as a card with its flow, « Use » opens the builder
 * filled with it — to adjust, then save as a draft and publish. A template this portal cannot run (a
 * missing action or event) says so.
 */
export function Gallery() {
  const t = useT();
  const templates = useTemplates();
  return (
    <ul className="automation-templates">
      {(templates.data ?? []).map((template) => (
        <li key={template.key} className="automation-template ds-card">
          <header>
            <h3>{template.title}</h3>
            {template.valid ? null : (
              <StatusBadge tone="warn">{t("automations:templates.invalid")}</StatusBadge>
            )}
          </header>
          <p className="automation-meta">{template.description}</p>
          {template.definition ? <FlowView definition={template.definition} compact /> : null}
          {template.valid ? (
            <Link
              className="ds-button ds-button--primary"
              to={`/admin/automations/new?template=${encodeURIComponent(template.key)}`}
            >
              <Icon name="sparkles" size={16} />
              {t("automations:templates.use")}
            </Link>
          ) : (
            <ul className="automation-meta">
              {template.errors.slice(0, 3).map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}
