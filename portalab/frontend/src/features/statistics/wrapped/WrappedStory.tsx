import { useId, useState } from "react";
import { useParams } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useCatalog, useMyWrapped } from "../api";

/**
 * Wrapped recap (spec 017 T030): one statistic per step, navigated with buttons (no auto-advance, no
 * motion required — reduced-motion users see the same content); text first.
 */
export function WrappedStory() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { snapshotId } = useParams();
  const wrapped = useMyWrapped();
  const catalog = useCatalog();
  const titles = new Map((catalog.data ?? []).map((entry) => [entry.key, entry.title_key]));
  const [step, setStep] = useState(0);
  if (wrapped.isPending) return <FunctionalState state="loading" />;
  const snapshot = (wrapped.data ?? []).find((s) => !snapshotId || s.id === snapshotId);
  if (!snapshot) return <FunctionalState state="no-data" label={t("statistics:wrapped.none")} />;
  const stats = snapshot.payload.stats;
  const current = stats[Math.min(step, stats.length - 1)];
  return (
    <section aria-labelledby={headingId} className="wrapped">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="sparkles"
        title={t("statistics:wrapped.title", {
          start: format.date(snapshot.period_start),
          end: format.date(snapshot.period_end),
        })}
      />
      {current ? (
        <p className="wrapped__value" aria-live="polite">
          {titles.has(current.key) ? t(titles.get(current.key) as string) : current.key} :{" "}
          {current.value === null ? "—" : format.number(current.value)}
        </p>
      ) : null}
      <div className="ds-stack ds-stack--row">
        <Button variant="secondary" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          {t("statistics:wrapped.previous")}
        </Button>
        <span>
          {Math.min(step, stats.length - 1) + 1} / {stats.length}
        </span>
        <Button variant="secondary" disabled={step >= stats.length - 1} onClick={() => setStep((s) => s + 1)}>
          {t("statistics:wrapped.next")}
        </Button>
      </div>
    </section>
  );
}

export default WrappedStory;
