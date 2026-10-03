import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { usePluginDetail } from "../api";

/** Plugin diagnostics (spec 023 T033): contributions per point, conflicts, recent errors. */
export function Diagnostics({ pluginKey }: { pluginKey: string }) {
  const t = useT();
  const detail = usePluginDetail(pluginKey);
  if (detail.isError) return <FunctionalState state="unavailable" />;
  if (!detail.data) return null;
  const { diagnostics } = detail.data;
  const points = new Map<string, number>();
  for (const c of diagnostics.contributions) points.set(c.point, (points.get(c.point) ?? 0) + 1);
  return (
    <section aria-labelledby={`diag-${pluginKey}`} className="ds-stack">
      <h3 id={`diag-${pluginKey}`}>{t("plugins:diagnostics.title")}</h3>
      <ul className="community-values">
        {[...points.entries()].map(([point, count]) => (
          <li key={point}>
            {point}: {count}
          </li>
        ))}
      </ul>
      {diagnostics.conflicts.length ? (
        <FunctionalState
          state="partial"
          label={t("plugins:diagnostics.conflicts", { count: diagnostics.conflicts.length })}
        />
      ) : null}
      {diagnostics.errors.length ? (
        <ul>
          {diagnostics.errors.map((e) => (
            <li key={`${e.window_start}-${e.kind}`}>
              {e.kind}: {e.count} · {e.last}
            </li>
          ))}
        </ul>
      ) : (
        <p>{t("plugins:diagnostics.noErrors")}</p>
      )}
    </section>
  );
}
