import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { AdminPage } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { installElements, uninstallScope } from "../../design-system/visuals/registry";
import { useT } from "../../i18n/hooks/useT";
import { nextStep, type Outcome, STEPS, type StepKey, useVersionDetail, type VersionDetail } from "./api";
import { nameOf, OUTCOME_ICON } from "./parts";
import { AnalysisStep } from "./steps/AnalysisStep";
import { ImportStep } from "./steps/ImportStep";
import { ReviewStep } from "./steps/ReviewStep";
import { SecurityStep } from "./steps/SecurityStep";
import { TestStep } from "./steps/TestStep";
import { ValidationStep } from "./steps/ValidationStep";
import "./visuals.css";

/**
 * 028: one version of a pack, through its six visible steps — Import (read and stored under its
 * fingerprint), Analysis (what it holds), Security (what its files would try and what Portalab refuses),
 * Test (every element drawn for real, measured in this browser), Review (the economy decided per element, the
 * confirmations) and Validation (published, or refused). Each step says its state and what comes next; a step
 * can be visited again until the version is published. The version's elements are shown to this
 * administrator only while the page is open (they win over the live ones).
 */

export function outcomeOf(detail: VersionDetail, step: StepKey): Outcome | "todo" {
  const o = detail.outcomes;
  switch (step) {
    case "import":
      return o.import ?? "done";
    case "analysis":
      return o.analysis ?? "todo";
    case "security":
      return o.security ?? "todo";
    case "test":
      return o.test ?? "todo";
    case "review":
      return o.review ?? (detail.step === "published" ? "done" : "todo");
    case "validation":
      return detail.step === "published" || detail.step === "superseded"
        ? "done"
        : detail.step === "refused"
          ? "blocking"
          : "todo";
  }
}

export default function VersionWorkflow() {
  const t = useT();
  const { pack, version } = useParams();
  const [search, setSearch] = useSearchParams();
  const detail = useVersionDetail(pack, version);
  const data = detail.data;

  // this version's elements, for this page only (the Test step draws them; they win over the live ones)
  useEffect(() => {
    if (!data) return;
    void installElements(data.elements, "preview");
    return () => uninstallScope("preview");
  }, [data]);

  if (detail.isError) return <FunctionalState state="error" label={t("admin:visuals.notFound")} />;
  if (!data) return <FunctionalState state="loading" label={t("admin:visuals.loading")} />;
  const wanted = search.get("step") as StepKey | null;
  const step: StepKey = wanted && STEPS.includes(wanted) ? wanted : nextStep(data);
  const index = STEPS.indexOf(step);
  const go = (next: StepKey) => setSearch({ step: next });
  const name = nameOf(data.names, data.pack);
  return (
    <AdminPage
      icon="package"
      title={t("admin:visuals.version", { pack: name, version: data.version })}
      description={t(`admin:visuals.stepHelp.${step}`)}
      secondary={
        <Button asChild variant="ghost">
          <Link to="/admin/visuals">
            <Icon name="back" size={16} /> {t("admin:visuals.back")}
          </Link>
        </Button>
      }
      wide
    >
      <nav aria-label={t("admin:visuals.stepper")} className="visuals-stepper">
        <ol>
          {STEPS.map((key, position) => {
            const outcome = outcomeOf(data, key);
            return (
              <li key={key} data-outcome={outcome} data-current={key === step || undefined}>
                <Link to={`?step=${key}`} aria-current={key === step ? "step" : undefined}>
                  <span className="visuals-stepper__number" aria-hidden="true">
                    {outcome === "todo" ? position + 1 : <Icon name={OUTCOME_ICON[outcome]} size={14} />}
                  </span>
                  <span className="visuals-stepper__name">{t(`admin:visuals.step.${key}`)}</span>
                  <span className="visually-hidden">{t(`admin:visuals.outcome.${outcome}`)}</span>
                </Link>
              </li>
            );
          })}
        </ol>
      </nav>
      <div className="visuals-step">
        {step === "import" ? <ImportStep detail={data} /> : null}
        {step === "analysis" ? <AnalysisStep detail={data} /> : null}
        {step === "security" ? <SecurityStep detail={data} /> : null}
        {step === "test" ? <TestStep detail={data} /> : null}
        {step === "review" ? <ReviewStep detail={data} onSaved={() => go("validation")} /> : null}
        {step === "validation" ? <ValidationStep detail={data} /> : null}
      </div>
      <div className="visuals-step__nav">
        {index > 0 ? (
          <Button variant="secondary" onClick={() => go(STEPS[index - 1] as StepKey)}>
            <Icon name="back" size={16} /> {t(`admin:visuals.step.${STEPS[index - 1]}`)}
          </Button>
        ) : (
          <span />
        )}
        {index < STEPS.length - 1 && step !== "review" ? (
          <Button onClick={() => go(STEPS[index + 1] as StepKey)}>
            {t("admin:visuals.continue", { step: t(`admin:visuals.step.${STEPS[index + 1]}`) })}
          </Button>
        ) : null}
      </div>
    </AdminPage>
  );
}
