import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { useRuleAdmin, useRules } from "../api";
import { SimulationPanel } from "./SimulationPanel";

const EXAMPLE = JSON.stringify(
  {
    event_type: "media.playback_finished",
    grants: [
      { value: "xp", amount: 20 },
      { value: "coins", amount: 5 },
    ],
  },
  null,
  2,
);

/**
 * Reward rules (spec 013 T014): every save is a **new draft version**; publishing makes it effective now;
 * older versions are never edited. Definitions are closed JSON records validated by the server.
 */
export function RuleEditor() {
  const t = useT();
  const rules = useRules();
  const admin = useRuleAdmin();
  const [key, setKey] = useState("");
  const [text, setText] = useState(EXAMPLE);
  const [invalid, setInvalid] = useState(false);
  const parsed = (): Record<string, unknown> | null => {
    try {
      return JSON.parse(text) as Record<string, unknown>;
    } catch {
      return null;
    }
  };
  const save = () => {
    const definition = parsed();
    setInvalid(definition === null);
    if (definition && key) admin.save.mutate({ key, definition }, { onError: () => setInvalid(true) });
  };
  return (
    <section aria-labelledby="gamification-rules" className="gamification-admin">
      <h2 id="gamification-rules">{t("gamification:admin.rules")}</h2>
      <ul className="gamification-table">
        {(rules.data ?? []).map((rule) => (
          <li key={rule.key}>
            <strong>{rule.key}</strong> ·{" "}
            {t("gamification:admin.rule.status", { version: rule.version, status: rule.status })}{" "}
            {rule.status === "draft" ? (
              <Button
                variant="secondary"
                onClick={() => admin.publish.mutate({ key: rule.key, version: rule.version })}
              >
                {t("gamification:admin.rule.publish", { version: rule.version })}
              </Button>
            ) : null}
            {rule.status === "active" ? (
              <Button variant="secondary" onClick={() => admin.retire.mutate(rule.key)}>
                {t("gamification:admin.rule.retire")}
              </Button>
            ) : null}
            <Button
              variant="secondary"
              onClick={() => {
                setKey(rule.key);
                setText(JSON.stringify(rule.definition, null, 2));
              }}
            >
              {rule.key}
            </Button>
          </li>
        ))}
      </ul>
      <TextField
        label={t("gamification:admin.rule.key")}
        value={key}
        onChange={(e) => setKey(e.target.value)}
      />
      <label htmlFor="gamification-rule-definition">{t("gamification:admin.rule.definition")}</label>
      <textarea
        id="gamification-rule-definition"
        rows={10}
        value={text}
        aria-invalid={invalid || undefined}
        onChange={(e) => setText(e.target.value)}
      />
      {invalid ? <p role="alert">{t("gamification:admin.rule.invalid")}</p> : null}
      <Button onClick={save} disabled={!key || admin.save.isPending}>
        {t("gamification:admin.rule.save")}
      </Button>
      <SimulationPanel ruleKey={key} definition={parsed()} />
    </section>
  );
}
