import { useId, useState } from "react";
import { useParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type DiffSegment, fetchCompare, usePage, useRevisions, useWikiActions } from "./api";
import "../content/content.css";

/** Changes as text with "+"/"−" markers and labels (never color alone, spec 011 T014). */
export function DiffView({ segments }: { segments: DiffSegment[] }) {
  const t = useT();
  return (
    <ol className="content-diff" aria-label={t("wiki:changes")}>
      {segments.map((segment, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: diff lines are positional by nature
        <li key={index} data-op={segment.op}>
          <span aria-hidden="true">
            {segment.op === "insert" ? "+ " : segment.op === "delete" ? "− " : "  "}
          </span>
          {segment.op !== "equal" ? (
            <span className="visually-hidden">{t(`wiki:op.${segment.op}`)}: </span>
          ) : null}
          {segment.text}
        </li>
      ))}
    </ol>
  );
}

export function History() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const { slug = "" } = useParams();
  const page = usePage(slug);
  const revisions = useRevisions(page.data?.id ?? "", Boolean(page.data));
  const { restore } = useWikiActions();
  const [diff, setDiff] = useState<DiffSegment[] | null>(null);
  if (page.isPending || revisions.isPending) return <FunctionalState state="loading" />;
  if (revisions.isError) return <FunctionalState state="unauthorized" label={t("wiki:historyForbidden")} />;
  const rows = revisions.data ?? [];
  const pageId = page.data?.id ?? "";
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("wiki:historyOf", { title: page.data?.title ?? "" })}</h2>
      <ol className="wiki-revisions">
        {rows.map((r, index) => (
          <li key={r.version}>
            {t("wiki:version", { version: r.version })} · {format.dateTime(r.created_at)}
            {r.change_note ? ` · ${r.change_note}` : ""}
            {r.restored_from_version
              ? ` · ${t("wiki:restoredFrom", { version: r.restored_from_version })}`
              : ""}{" "}
            {index + 1 < rows.length ? (
              <Button
                variant="secondary"
                onClick={async () =>
                  setDiff((await fetchCompare(pageId, rows[index + 1]?.version ?? 1, r.version)).lines)
                }
              >
                {t("wiki:compare")}
              </Button>
            ) : null}{" "}
            {index > 0 ? (
              <Button variant="secondary" onClick={() => restore.mutate({ id: pageId, version: r.version })}>
                {t("wiki:restore")}
              </Button>
            ) : null}
          </li>
        ))}
      </ol>
      {diff ? <DiffView segments={diff} /> : null}
    </section>
  );
}

export default History;
