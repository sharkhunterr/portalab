import { useEffect, useRef, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import { useAction, useActionDecision } from "../api";

/**
 * Sensitive action proposed by the assistant (spec 018 T017): the **tool-generated** summary, an expiry
 * countdown and confirm / decline buttons. Nothing runs until the user confirms; after a decision the
 * outcome receives focus so screen-reader and keyboard users hear it.
 */
export function ConfirmationCard({
  actionId,
  now = () => Date.now(),
}: {
  actionId: string;
  now?: () => number;
}) {
  const t = useT();
  const action = useAction(actionId);
  const decide = useActionDecision(actionId);
  const outcome = useRef<HTMLParagraphElement>(null);
  const [tick, setTick] = useState(0);
  const status = decide.data?.status ?? action.data?.status;
  useEffect(() => {
    if (status !== "pending") return;
    const timer = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [status]);
  useEffect(() => {
    if (decide.data) outcome.current?.focus();
  }, [decide.data]);
  if (!action.data) return null;
  const remaining = Math.max(0, Math.round((new Date(action.data.expires_at).getTime() - now()) / 1000));
  const expired = status === "expired" || (status === "pending" && remaining === 0);
  return (
    <section className="ds-card ai-confirmation" aria-labelledby={`ai-confirm-${actionId}`} data-tick={tick}>
      <h4 id={`ai-confirm-${actionId}`}>{t("ai:confirm.title")}</h4>
      <p>{action.data.summary}</p>
      {status === "pending" && !expired ? (
        <>
          <p className="ai-meta">{t("ai:confirm.notice")}</p>
          <p className="ai-meta" aria-live="off">
            {t("ai:confirm.expiresIn", { seconds: remaining })}
          </p>
          <div className="ds-stack--row">
            <Button onClick={() => decide.mutate("confirm")} disabled={decide.isPending}>
              {t("ai:confirm.confirm")}
            </Button>
            <Button variant="secondary" onClick={() => decide.mutate("decline")} disabled={decide.isPending}>
              {t("ai:confirm.decline")}
            </Button>
          </div>
        </>
      ) : (
        <p ref={outcome} tabIndex={-1} role="status">
          {t(`ai:confirm.status.${expired ? "expired" : (status ?? "failed")}`)}
        </p>
      )}
      {decide.isError ? <p role="alert">{t("ai:confirm.status.expired")}</p> : null}
    </section>
  );
}
