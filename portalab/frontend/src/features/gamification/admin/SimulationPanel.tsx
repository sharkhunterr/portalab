import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import { useRuleAdmin } from "../api";

/** Dry run of a rule against sample events (spec 013 R14): shows grants, factors and caps — writes nothing. */
export function SimulationPanel({
  ruleKey,
  definition,
}: {
  ruleKey: string;
  definition: Record<string, unknown> | null;
}) {
  const t = useT();
  const { simulate } = useRuleAdmin();
  const [samples, setSamples] = useState('[{"payload": {}}]');
  const run = () => {
    let parsed: Array<Record<string, unknown>> = [];
    try {
      parsed = JSON.parse(samples) as Array<Record<string, unknown>>;
    } catch {
      return;
    }
    if (definition && ruleKey) simulate.mutate({ key: ruleKey, definition, samples: parsed });
  };
  return (
    <div className="ds-stack">
      <label htmlFor="gamification-samples">{t("gamification:admin.simulate.samples")}</label>
      <textarea
        id="gamification-samples"
        rows={4}
        value={samples}
        onChange={(e) => setSamples(e.target.value)}
      />
      <Button variant="secondary" onClick={run} disabled={!definition || !ruleKey}>
        {t("gamification:admin.simulate")}
      </Button>
      {simulate.data ? (
        <section aria-label={t("gamification:admin.simulate.result")}>
          <h3>{t("gamification:admin.simulate.result")}</h3>
          <ol>
            {simulate.data.map((result) => (
              <li key={result.sample}>
                {result.grants.length
                  ? result.grants
                      .map(
                        (g) =>
                          `${g.amount} ${t(`gamification:value.${g.value}`)} (×${g.factor}${g.capped ? ", cap" : ""})`,
                      )
                      .join(" · ")
                  : t("gamification:admin.simulate.none")}
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}
