import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type Template, templateAbout, templateName, useTemplates } from "./api";

/** A template's colours: its background, surface, accent and text. */
export function Swatches({ template }: { template: Template }) {
  const p = template.definition.palette;
  return (
    <span className="edition-swatches" aria-hidden="true">
      {[p.background, p.surface, p.accent, p.text].map((color, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: four fixed swatches
        <span key={index} style={{ background: color }} />
      ))}
    </span>
  );
}

/**
 * issue 329: the template of one automatic newsletter, chosen by sight — each template as a card (its
 * colours, its name, what it shows), the chosen one marked.
 */
export function TemplatePicker({ value, onChange }: { value: string; onChange: (key: string) => void }) {
  const t = useT();
  const templates = useTemplates();
  return (
    <div className="template-picker" role="radiogroup" aria-label={t("news:edition.admin.template")}>
      {(templates.data ?? []).map((template) => {
        const chosen = template.key === value;
        return (
          <label key={template.key} className="template-pick" data-chosen={chosen || undefined}>
            <input
              type="radio"
              name="newsletter-template"
              value={template.key}
              checked={chosen}
              onChange={() => onChange(template.key)}
            />
            <Swatches template={template} />
            <span className="template-pick__text">
              <strong>{templateName(t, template)}</strong>
              <small>{templateAbout(t, template)}</small>
            </span>
            {chosen ? <Icon name="check" size={18} /> : null}
          </label>
        );
      })}
    </div>
  );
}
