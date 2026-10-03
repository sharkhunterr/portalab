import { useEffect, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { useLevelCurve, usePublishCurve, useVerify } from "../api";

/** Level curve (spec 013 T024) and ledger verification (T011). A new curve never emits level-ups. */
export function LevelCurve() {
  const t = useT();
  const curve = useLevelCurve();
  const publish = usePublishCurve();
  const verify = useVerify();
  const [base, setBase] = useState(100);
  const [exponent, setExponent] = useState(1.5);
  useEffect(() => {
    if (curve.data) {
      setBase(curve.data.definition.base);
      setExponent(curve.data.definition.exponent);
    }
  }, [curve.data]);
  return (
    <section aria-labelledby="gamification-curve">
      <h2 id="gamification-curve">{t("gamification:admin.curve")}</h2>
      <div className="ds-stack--row">
        <TextField
          label={t("gamification:admin.curve.base")}
          type="number"
          min={1}
          value={String(base)}
          onChange={(e) => setBase(Number(e.target.value))}
        />
        <TextField
          label={t("gamification:admin.curve.exponent")}
          type="number"
          step="0.1"
          min={1}
          max={3}
          value={String(exponent)}
          onChange={(e) => setExponent(Number(e.target.value))}
        />
      </div>
      <Button variant="secondary" onClick={() => publish.mutate({ kind: "power", base, exponent })}>
        {t("gamification:admin.curve.save")}
      </Button>
      <ol>
        {(curve.data?.preview ?? []).map((row) => (
          <li key={row.level}>
            {t("gamification:level", { level: row.level })}: {row.xp} {t("gamification:value.xp")}
          </li>
        ))}
      </ol>
      <Button variant="secondary" onClick={() => verify.mutate()}>
        {t("gamification:admin.verify")}
      </Button>
      {verify.data ? (
        <p role="status">
          {verify.data.ok
            ? t("gamification:admin.verify.ok")
            : t("gamification:admin.verify.drift", { count: verify.data.drifts.length })}
        </p>
      ) : null}
    </section>
  );
}
