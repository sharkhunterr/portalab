import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useServiceNames } from "../../support/incidents/maintenance";
import { type Definition, useCatalog } from "../api";
import {
  ACTION_ICONS,
  actionLabel,
  conditionLabel,
  flatConditions,
  paramLabel,
  paramValue,
  readable,
  serviceNames,
  TRIGGER_ICONS,
  triggerSummary,
} from "../labels";

/**
 * An automation as a flow (027): WHEN (its trigger), IF (its conditions, how they combine), THEN (its
 * steps in order, with what each is given) — the same shape in the overview, the detail page and the
 * templates, so an administrator reads any rule at a glance.
 */
export function FlowView({ definition, compact = false }: { definition: Definition; compact?: boolean }) {
  const t = useT();
  const names = useServiceNames().data;
  if (names) serviceNames.current = names;
  const format = useFormat();
  const catalog = useCatalog().data;
  const conditions = flatConditions(definition.conditions);
  return (
    <ol className="automation-flow" data-compact={compact || undefined}>
      <li className="automation-flow__node" data-part="when">
        <span className="automation-flow__badge">
          <Icon name={TRIGGER_ICONS[definition.trigger.kind] ?? "zap"} size={16} />
          {t("automations:flow.when")}
        </span>
        <p className="automation-flow__text">{triggerSummary(t, definition.trigger, catalog, format)}</p>
      </li>
      {conditions === null || conditions.leaves.length ? (
        <li className="automation-flow__node" data-part="if">
          <span className="automation-flow__badge">
            <Icon name="list" size={16} />
            {t("automations:flow.if")}
            {conditions && conditions.leaves.length > 1 ? (
              <span className="automation-flow__mode">{t(`automations:flow.mode.${conditions.mode}`)}</span>
            ) : null}
          </span>
          {conditions === null ? (
            <pre className="automation-flow__raw">{JSON.stringify(definition.conditions, null, 2)}</pre>
          ) : (
            <ul className="automation-flow__list">
              {conditions.leaves.map((leaf, index) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: conditions are positional
                <li key={index}>
                  <strong>{conditionLabel(t, leaf.leaf, catalog)}</strong>
                  {compact ? null : <Params params={leaf.params} />}
                </li>
              ))}
            </ul>
          )}
        </li>
      ) : null}
      {definition.steps.map((step, index) => (
        <li key={step.id} className="automation-flow__node" data-part="then">
          <span className="automation-flow__badge">
            <Icon name={ACTION_ICONS[step.action] ?? "play"} size={16} />
            {index === 0 ? t("automations:flow.then") : t("automations:flow.next")}
            <span className="automation-flow__index">{index + 1}</span>
          </span>
          <p className="automation-flow__text">
            <strong>{actionLabel(t, step.action, catalog)}</strong>
            {step.on_error === "continue" ? (
              <span className="automation-flow__mode">{t("automations:flow.continues")}</span>
            ) : null}
          </p>
          {compact ? null : <Params params={step.params} />}
        </li>
      ))}
    </ol>
  );
}

function Params({ params }: { params: Record<string, unknown> }) {
  const t = useT();
  const entries = Object.entries(params ?? {}).filter(([, v]) => paramValue(v) !== "");
  if (!entries.length) return null;
  return (
    <dl className="automation-flow__params">
      {entries.map(([name, value]) => (
        <div key={name}>
          <dt>{paramLabel(t, name)}</dt>
          <dd>{name.startsWith("service") ? readable(value) : paramValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}
