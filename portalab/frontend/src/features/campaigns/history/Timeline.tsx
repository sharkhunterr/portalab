import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useHistory } from "../api";

/** Campaign history (spec 014 T027): versions, activation intervals, overrides — never rewritten. */
export function Timeline({ campaignId }: { campaignId: string }) {
  const t = useT();
  const format = useFormat();
  const history = useHistory(campaignId);
  if (!history.data) return null;
  const data = history.data;
  return (
    <section aria-label={t("campaigns:admin.history")}>
      <h3>{t("campaigns:history.versions")}</h3>
      <ol className="campaign-timeline">
        {data.versions.map((v) => (
          <li key={v.version}>
            v{v.version} · {format.dateTime(v.effective_from)}
          </li>
        ))}
      </ol>
      <h3>{t("campaigns:history.intervals")}</h3>
      <ol className="campaign-timeline">
        {data.intervals.map((i) => (
          <li key={`${i.opened_at}-${i.cause}`}>
            {i.opened_at ? format.dateTime(i.opened_at) : "?"} –{" "}
            {i.closed_at ? format.dateTime(i.closed_at) : t("campaigns:history.open")} · {i.cause} · v
            {i.version}
            {i.reason ? ` · ${i.reason}` : ""}
          </li>
        ))}
      </ol>
      <h3>{t("campaigns:history.overrides")}</h3>
      <ol className="campaign-timeline">
        {data.overrides.map((o) => (
          <li key={o.from_at}>
            {o.kind} · {format.dateTime(o.from_at)}
            {o.until_at ? ` → ${format.dateTime(o.until_at)}` : ""} · {o.reason}
          </li>
        ))}
      </ol>
    </section>
  );
}
