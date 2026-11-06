import { type FormEvent, useId, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Card } from "../../design-system/components/Content";
import { SelectField, TextAreaField, TextField } from "../../design-system/components/Field";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { useAsk, useAskOptions } from "./api";
import "./requests.css";

/**
 * Issue 363, issue 378: asking for a book, an audiobook, a game… — a request of the portal's, as a film's: it
 * is in « My requests », the administrators' queue and the figures with the others. A title the library has,
 * or another member asked for already, is told at once (as a film's). The form opens in a dialog from a
 * sheet, a title told absent, the words searched (issue 377); this page holds it too.
 */
function words(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function Problem({ error }: { error: unknown }) {
  const t = useT();
  if (!(error instanceof ApiError)) return <p role="alert">{t("media:ask.error.failed")}</p>;
  const route = typeof error.extensions.route === "string" ? error.extensions.route : null;
  const text =
    error.code === "media.request_in_library"
      ? t("media:ask.error.inLibrary")
      : error.code === "media.request_duplicate"
        ? t("media:ask.error.alreadyAsked")
        : error.code === "media.request_quota_exceeded"
          ? t("media:requests.quotaExceeded")
          : error.code === "media.service_unavailable"
            ? t("media:ask.error.noService")
            : t("media:ask.error.failed");
  return (
    <p role="alert" className="asks-problem">
      {text} {route ? <Link to={route}>{t("media:ask.error.see")}</Link> : null}
      {error.code === "media.request_duplicate" ? (
        <Link to="/media/requests">{t("media:ask.seeMine")}</Link>
      ) : null}
    </p>
  );
}

/** What a request begins with — from a sheet, a title told absent, the words searched (issue 377). */
export interface AskStart {
  kind?: string | undefined;
  title?: string | undefined;
  creator?: string | undefined;
  year?: number | null | undefined;
  language?: string | null | undefined;
  edition?: string | null | undefined;
  ids?: Record<string, string[]> | undefined;
  /** issue 378: the cover and the sheet of the database that knows it (the portal's own addresses) */
  cover?: string | null | undefined;
  sheet?: string | null | undefined;
}

/** The form's start read from an address (``id.<scheme>=<value>`` for each identifier, issue 367). */
function startOf(params: URLSearchParams): AskStart {
  const ids: Record<string, string[]> = {};
  for (const [key, value] of params) {
    if (key.startsWith("id.") && value) ids[key.slice(3)] = [...(ids[key.slice(3)] ?? []), value];
  }
  const year = params.get("year");
  return {
    kind: params.get("kind") ?? undefined,
    title: params.get("title") ?? undefined,
    creator: params.get("creator") ?? undefined,
    year: year && /^\d{1,4}$/.test(year) ? Number(year) : null,
    language: params.get("language"),
    edition: params.get("edition"),
    ids,
  };
}

export function AskForm({
  kinds,
  start = {},
  bare = false,
}: {
  kinds: string[];
  start?: AskStart;
  /** issue 377: inside a dialog — no card around it */
  bare?: boolean;
}) {
  const t = useT();
  const [kind, setKind] = useState(start.kind && kinds.includes(start.kind) ? start.kind : (kinds[0] ?? ""));
  const [title, setTitle] = useState(start.title ?? "");
  const [creators, setCreators] = useState(start.creator ?? "");
  const [year, setYear] = useState(start.year ? String(start.year) : "");
  const [language, setLanguage] = useState(start.language ?? "");
  const [edition, setEdition] = useState(start.edition ?? "");
  const [note, setNote] = useState("");
  const ask = useAsk();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !kind) return;
    const details: Record<string, string> = {};
    if (language.trim()) details.language = language.trim();
    if (edition.trim()) details.edition = edition.trim();
    // one identifier per scheme, as every request carries them
    const ids = Object.fromEntries(
      Object.entries(start.ids ?? {})
        .filter(([, values]) => values.length)
        .map(([scheme, values]) => [scheme, values[0] as string]),
    );
    ask.mutate({
      kind,
      title: title.trim(),
      creators: words(creators),
      year: /^\d{1,4}$/.test(year.trim()) ? Number(year.trim()) : null,
      details,
      ids,
      note: note.trim() || null,
      cover: start.cover ?? null,
      sheet: start.sheet ?? null,
    });
  };
  const form = (
    <form className="asks-form" onSubmit={submit}>
      <SelectField label={t("media:ask.form.kind")} value={kind} onChange={(e) => setKind(e.target.value)}>
        {kinds.map((k) => (
          <option key={k} value={k}>
            {t(`media:kind.${k}`)}
          </option>
        ))}
      </SelectField>
      <TextField
        label={t("media:ask.form.titleField")}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={300}
        required
      />
      <TextField
        label={t("media:ask.form.creators")}
        hint={t("media:ask.form.creatorsHint")}
        value={creators}
        onChange={(e) => setCreators(e.target.value)}
        maxLength={600}
      />
      <TextField
        label={t("media:ask.form.year")}
        value={year}
        inputMode="numeric"
        onChange={(e) => setYear(e.target.value)}
        maxLength={4}
      />
      <TextField
        label={t("media:ask.form.language")}
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
        maxLength={120}
      />
      <TextField
        label={t("media:ask.form.edition")}
        hint={t("media:ask.form.editionHint")}
        value={edition}
        onChange={(e) => setEdition(e.target.value)}
        maxLength={120}
      />
      <TextAreaField
        label={t("media:ask.form.note")}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={1000}
        rows={3}
      />
      <div className="asks-form__actions">
        <Button type="submit" disabled={ask.isPending || ask.isSuccess || !title.trim()}>
          {t("media:ask.form.send")}
        </Button>
      </div>
      {ask.isSuccess ? (
        <p role="status" className="asks-done">
          {t("media:ask.form.sent", { title: ask.data?.title ?? title })}{" "}
          <Link to="/media/requests">{t("media:ask.seeMine")}</Link>
        </p>
      ) : null}
      {ask.isError ? <Problem error={ask.error} /> : null}
    </form>
  );
  return bare ? (
    form
  ) : (
    <Card title={t("media:ask.form.title")} icon="plus" level={2}>
      {form}
    </Card>
  );
}

/** Issue 375: asking the team — the form alone, reached from « Ask for a title »; the requests themselves
 * are in « My requests ». */
export function RequestsPage() {
  const t = useT();
  const headingId = useId();
  const [params] = useSearchParams();
  const options = useAskOptions();
  if (options.isPending) return <FunctionalState state="loading" />;
  if (!options.data) {
    return (
      <section aria-labelledby={headingId} className="asks-page">
        <PageHeader titleId={headingId} level={2} icon="inbox" title={t("media:ask.page.title")} />
        <FunctionalState state="unavailable" onRetry={() => options.refetch()} />
      </section>
    );
  }
  return (
    <section aria-labelledby={headingId} className="asks-page">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="inbox"
        title={t("media:ask.page.title")}
        context={t("media:ask.page.context")}
        secondary={
          <Link className="ds-button ds-button--secondary" to="/media/requests">
            {t("media:ask.seeMine")}
          </Link>
        }
      />
      {options.data.kinds.length ? (
        <AskForm kinds={options.data.kinds} start={startOf(params)} />
      ) : (
        <p className="ds-panel">{t("media:ask.page.closed")}</p>
      )}
    </section>
  );
}

export default RequestsPage;
