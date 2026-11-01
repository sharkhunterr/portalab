import { useId, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { CheckboxField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { CurrencyShort } from "../../../design-system/site/SiteLook";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useHasPermission } from "../../authz/useMyPermissions";
import { type Project, useFund } from "../api";

type Rules = {
  consume_at?: string | Array<{ state: string; percent: number }>;
  min_funding?: number;
  max_funding_per_user?: number;
};

/** issue 304: where the funding stands — gathered, toward which goal, what is left to gather, by how many,
 * and what I gave. */
export function FundingProgress({ project, mine }: { project: Project; mine: number }) {
  const t = useT();
  const format = useFormat();
  const totals = project.totals;
  const gathered = totals.reserved + totals.consumed;
  const goal = totals.goal_amount ?? null;
  const left = goal ? Math.max(goal - gathered, 0) : null;
  return (
    <section aria-labelledby="project-raised" className="project-raised">
      <h2 id="project-raised" className="visually-hidden">
        {t("marketplace:funding.title")}
      </h2>
      <p className="project-raised__amount">
        <Icon name="coins" size={22} />
        <strong>{format.number(gathered)}</strong>
        <CurrencyShort />
        <span>
          {goal
            ? t(
                project.rules_frozen_at ? "marketplace:funding.ofGoal" : "marketplace:funding.ofProposedGoal",
                {
                  goal: format.number(goal),
                },
              )
            : null}
        </span>
      </p>
      {goal ? <progress className="project-raised__bar" value={Math.min(gathered, goal)} max={goal} /> : null}
      <p className="project-raised__left" data-reached={left === 0 || undefined}>
        {left === null
          ? t("marketplace:funding.noGoal")
          : left === 0
            ? t("marketplace:funding.reached")
            : t("marketplace:funding.remaining", { amount: format.number(left) })}
      </p>
      <dl className="project-raised__facts">
        <div>
          <dt>{t("marketplace:funding.backers")}</dt>
          <dd>{format.number(totals.funders)}</dd>
        </div>
        <div>
          <dt>{t("marketplace:funding.reserved")}</dt>
          <dd>{format.number(totals.reserved)}</dd>
        </div>
        <div>
          <dt>{t("marketplace:funding.used")}</dt>
          <dd>{format.number(totals.consumed)}</dd>
        </div>
        <div>
          <dt>{t("marketplace:funding.mine")}</dt>
          <dd>{format.number(mine)}</dd>
        </div>
      </dl>
    </section>
  );
}

/**
 * Funding panel (spec 015 T014; issue 304 redesign): how much to reserve — quick amounts up to what I may
 * still give — the **non-guarantee notice**, which must be acknowledged before Coins are reserved, and the
 * frozen rules folded below. Voting is elsewhere and independent.
 */
export function FundingPanel({ project, mine }: { project: Project; mine: number }) {
  const t = useT();
  const format = useFormat();
  const canFund = useHasPermission("marketplace.purchase");
  const fund = useFund(project.id);
  const [amount, setAmount] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const noticeId = useId();
  const rules = (project.funding_rules ?? {}) as Rules;
  const min = rules.min_funding ?? 1;
  const cap = rules.max_funding_per_user ?? 0;
  const room = cap ? Math.max(cap - mine, 0) : 0;
  const quick = [...new Set([50, 100, 250, room].filter((n) => n >= min && n <= room))].sort((a, b) => a - b);
  return (
    <section aria-labelledby="project-fund" className="project-fund">
      <h2 id="project-fund">
        <Icon name="heart" size={18} /> {t("marketplace:funding.contribute")}
      </h2>
      {project.accepts_funding && canFund && room > 0 ? (
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
          {quick.length ? (
            <fieldset className="project-fund__quick" aria-label={t("marketplace:funding.quick")}>
              {quick.map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-pressed={amount === String(n)}
                  onClick={() => setAmount(String(n))}
                >
                  {n === room ? t("marketplace:funding.max", { amount: format.number(n) }) : format.number(n)}
                </button>
              ))}
            </fieldset>
          ) : null}
          <TextField
            type="number"
            min={min}
            max={room}
            label={t("marketplace:funding.amount")}
            hint={t("marketplace:funding.room", { min: format.number(min), max: format.number(room) })}
            value={amount}
            required
            onChange={(e) => setAmount(e.target.value)}
          />
          <p id={noticeId} className="project-notice">
            {t("marketplace:funding.notice")}
          </p>
          <CheckboxField
            label={t("marketplace:funding.acknowledge")}
            checked={acknowledged}
            aria-describedby={noticeId}
            onChange={(e) => setAcknowledged(e.target.checked)}
          />
          {fund.isError ? <p role="alert">{t("marketplace:funding.error")}</p> : null}
          {fund.isSuccess ? <p role="status">{t("marketplace:funding.done")}</p> : null}
          <Button type="submit" disabled={!acknowledged || !amount || fund.isPending}>
            <Icon name="coins" size={16} />
            {t("marketplace:funding.submit")}
          </Button>
        </form>
      ) : (
        <p className="project-fund__closed">
          {project.accepts_funding && canFund
            ? t("marketplace:funding.capped")
            : t("marketplace:funding.closed")}
        </p>
      )}
      {project.funding_rules ? (
        <details className="project-fund__rules">
          <summary>
            <Icon name="info" size={16} /> {t("marketplace:funding.rules")}
          </summary>
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
            <li>{t("marketplace:funding.ruleLimits", { min, max: cap })}</li>
          </ul>
        </details>
      ) : null}
    </section>
  );
}
