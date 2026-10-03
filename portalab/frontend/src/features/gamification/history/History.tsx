import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { SelectField } from "../../../design-system/components/Field";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useTransactions, type Value } from "../api";

/** Transaction history (spec 013 T010): every grant, spend, refund, correction is its own row (append-only). */
export function History() {
  const t = useT();
  const format = useFormat();
  const [value, setValue] = useState<Value | null>(null);
  const history = useTransactions(value);
  const items = history.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section aria-labelledby="gamification-history">
      <h2 id="gamification-history">{t("gamification:history.title")}</h2>
      <SelectField
        label={t("gamification:history.filter")}
        value={value ?? ""}
        onChange={(event) => setValue((event.target.value || null) as Value | null)}
      >
        <option value="">{t("gamification:history.all")}</option>
        {(["xp", "contribution", "coins"] as const).map((v) => (
          <option key={v} value={v}>
            {t(`gamification:value.${v}`)}
          </option>
        ))}
      </SelectField>
      {items.length === 0 && !history.isLoading ? <p>{t("gamification:history.empty")}</p> : null}
      <table className="gamification-table">
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{format.dateTime(item.occurred_at)}</td>
              <td>{t(`gamification:kind.${item.kind}`)}</td>
              <td className="gamification-delta" data-sign={item.delta < 0 ? "minus" : "plus"}>
                {item.delta > 0 ? "+" : ""}
                {format.number(item.delta)} {t(`gamification:value.${item.value}`)}
              </td>
              <td>{item.reason ?? item.rule_key ?? item.source_kind}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {history.hasNextPage ? (
        <Button variant="secondary" onClick={() => void history.fetchNextPage()}>
          {t("gamification:history.more")}
        </Button>
      ) : null}
    </section>
  );
}
