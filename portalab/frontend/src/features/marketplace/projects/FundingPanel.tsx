import { useId, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { type Project, useFund } from "../api";

/**
 * Funding panel (spec 015 T014): the frozen rules, public totals and the **non-guarantee notice**, which
 * must be acknowledged before Coins are reserved. Voting is elsewhere and independent.
 */
export function FundingPanel({ project }: { project: Project }) {
  const t = useT();
  const format = useFormat();
  const canFund = useHasPermission("marketplace.purchase");
  const fund = useFund(project.id);
  const [amount, setAmount] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const noticeId = useId();
  const rules = (project.funding_rules ?? {}) as {
    consume_at?: string | Array<{ state: string; percent: number }>;
    min_funding?: number;
    max_funding_per_user?: number;
  };
  const totals = project.totals;
  return (
    <section aria-labelledby="project-funding" className="ds-card ds-stack">
      <h2 id="project-funding">{t("marketplace:funding.title")}</h2>
      <p>
        {t("marketplace:funding.totals", {
          reserved: format.number(totals.reserved),
          consumed: format.number(totals.consumed),
          funders: totals.funders,
        })}
        {totals.goal_amount
          ? ` · ${t("marketplace:funding.goal", { goal: format.number(totals.goal_amount) })}`
          : ""}
      </p>
      {project.funding_rules ? (
        <ul>
          <li>{t("marketplace:funding.ruleRefund")}</li>
          <li>
            {typeof rules.consume_at === "string" || !rules.consume_at
              ? t("marketplace:funding.ruleConsumeAtRelease")
              : rules.consume_at
                  .map((m) =>
                    t("marketplace:funding.ruleMilestone", {
                      state: t(`marketplace:state.${m.state}`),
                      percent: m.percent,
                    }),
                  )
                  .join(" · ")}
          </li>
          <li>
            {t("marketplace:funding.ruleLimits", {
              min: rules.min_funding ?? 1,
              max: rules.max_funding_per_user ?? 0,
            })}
          </li>
        </ul>
      ) : null}
      {project.accepts_funding && canFund ? (
        <form
          className="ds-stack"
          onSubmit={(event) => {
            event.preventDefault();
            fund.mutate(
              { amount: Number(amount), requestKey },
              {
                onSuccess: () => {
                  setAmount("");
                  setAcknowledged(false);
                  setRequestKey(crypto.randomUUID());
                },
              },
            );
          }}
        >
          <p id={noticeId} className="project-notice">
            {t("marketplace:funding.notice")}
          </p>
          <TextField
            type="number"
            min={rules.min_funding ?? 1}
            label={t("marketplace:funding.amount")}
            value={amount}
            required
            onChange={(e) => setAmount(e.target.value)}
          />
          <CheckboxField
            label={t("marketplace:funding.acknowledge")}
            checked={acknowledged}
            aria-describedby={noticeId}
            onChange={(e) => setAcknowledged(e.target.checked)}
          />
          {fund.isError ? <p role="alert">{t("marketplace:funding.error")}</p> : null}
          {fund.isSuccess ? <p role="status">{t("marketplace:funding.done")}</p> : null}
          <Button type="submit" disabled={!acknowledged || !amount || fund.isPending}>
            {t("marketplace:funding.submit")}
          </Button>
        </form>
      ) : (
        <p>{t("marketplace:funding.closed")}</p>
      )}
    </section>
  );
}
