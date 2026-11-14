import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import type { Loading, StepKey } from "./loading";

/**
 * Issue 420: the game loading, step by step — the sitting, the emulator, its core, the console's BIOS, the
 * game, the save it resumes, the start — each done, under way (its progress) or still to come.
 */
export function LoadingSteps({
  steps,
  current,
  loading,
  core,
}: {
  steps: StepKey[];
  current: StepKey;
  loading: Loading | null;
  core: string;
}) {
  const t = useT();
  const at = steps.indexOf(current);
  return (
    <ol className="retro-steps" aria-label={t("retro:loading.title")}>
      {steps.map((step, index) => {
        const state = index < at ? "done" : index === at ? "active" : "todo";
        const progress = state === "active" && loading?.key === step ? loading : null;
        return (
          <li
            key={step}
            className="retro-step"
            data-state={state}
            aria-current={state === "active" ? "step" : undefined}
          >
            <span className="retro-step__mark" aria-hidden="true">
              {state === "done" ? (
                <Icon name="check" size={16} />
              ) : state === "active" ? (
                <span className="retro-step__spin" />
              ) : null}
            </span>
            <span className="retro-step__text">
              <strong>{t(`retro:loading.${step}`, { core })}</strong>
              {progress ? (
                <small>
                  {t(`retro:loading.action.${progress.action}`)}
                  {progress.percent !== null
                    ? ` · ${progress.percent} %`
                    : progress.megabytes !== null
                      ? ` · ${t("retro:loading.megabytes", { size: progress.megabytes.toFixed(1) })}`
                      : ""}
                </small>
              ) : null}
              {state === "active" ? (
                <span
                  className="retro-step__bar"
                  role="progressbar"
                  aria-label={t(`retro:loading.${step}`, { core })}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress?.percent ?? undefined}
                  data-indeterminate={progress?.percent == null || undefined}
                >
                  <span style={{ inlineSize: `${progress?.percent ?? 30}%` }} />
                </span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
