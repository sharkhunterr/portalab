import { type FormEvent, useId, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { CoinBadge } from "../../design-system/components/Badges";
import { Button } from "../../design-system/components/Button";
import { Card } from "../../design-system/components/Content";
import { SelectField, TextAreaField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { type Asked, OPEN, useAskActions, useAskOptions, useMyAsks } from "./api";
import "./requests.css";

/**
 * Issue 363: asking the team for a title no service asks for — a book, an audiobook, a game… —, my requests
 * and where they stand (issue 375: in « My requests »), and the other members' open requests to say « me
 * too » to. A title the library has,
 * or another member asked for already, is told at once (the latter becomes a « me too »). Reached from the
 * menu and from a title told absent (its kind, title and author filled in).
 */
const TONE: Record<string, string> = {
  new: "stale",
  accepted: "partial",
  in_progress: "partial",
  available: "available",
  refused: "error",
  cancelled: "empty",
};

function words(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function AskStatusBadge({ status }: { status: string }) {
  const t = useT();
  return (
    <span className="asks-status" data-tone={TONE[status] ?? "empty"}>
      {t(`media:ask.status.${status}`)}
    </span>
  );
}

function Problem({ error, onSupport }: { error: unknown; onSupport: (id: string) => void }) {
  const t = useT();
  if (!(error instanceof ApiError)) return <p role="alert">{t("media:ask.error.failed")}</p>;
  const route = typeof error.extensions.route === "string" ? error.extensions.route : null;
  const twin = typeof error.extensions.request_id === "string" ? error.extensions.request_id : null;
  switch (error.code) {
    case "requests.in_library":
      return (
        <p role="alert" className="asks-problem">
          {t("media:ask.error.inLibrary")} {route ? <Link to={route}>{t("media:ask.error.see")}</Link> : null}
        </p>
      );
    case "requests.already_asked":
      return (
        <p role="alert" className="asks-problem">
          {t("media:ask.error.alreadyAsked")}{" "}
          {twin ? (
            <Button variant="secondary" onClick={() => onSupport(twin)}>
              <Icon name="heart" size={14} />
              {t("media:ask.meToo")}
            </Button>
          ) : null}
        </p>
      );
    case "requests.quota_reached":
      return (
        <p role="alert" className="asks-problem">
          {t("media:ask.error.quota", {
            limit: Number(error.extensions.limit ?? 0),
            days: Number(error.extensions.days ?? 0),
          })}
        </p>
      );
    case "economy.insufficient_coins":
      return (
        <p role="alert" className="asks-problem">
          {t("media:ask.error.coins", { currency: t("gamification:value.coins") })}
        </p>
      );
    default:
      return (
        <p role="alert" className="asks-problem">
          {error.message || t("media:ask.error.failed")}
        </p>
      );
  }
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
  price,
  left,
  start = {},
  bare = false,
}: {
  kinds: string[];
  price: number;
  left: Record<string, number | null>;
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
  const ids = start.ids ?? {};
  const [note, setNote] = useState("");
  const { ask, support } = useAskActions();
  const remaining = left[kind];
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !kind) return;
    const details: Record<string, string> = {};
    if (language.trim()) details.language = language.trim();
    if (edition.trim()) details.edition = edition.trim();
    ask.mutate({
      kind,
      title: title.trim(),
      creators: words(creators),
      year: /^\d{1,4}$/.test(year.trim()) ? Number(year.trim()) : null,
      details,
      ids,
      note: note.trim() || null,
    });
  };
  return bare ? (
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
        {price > 0 ? <CoinBadge amount={price} label={t("gamification:value.coins")} /> : null}
        {remaining !== null && remaining !== undefined ? (
          <span className="asks-muted">{t("media:ask.form.left", { count: remaining })}</span>
        ) : null}
        <Button type="submit" disabled={ask.isPending || !title.trim() || remaining === 0}>
          {t("media:ask.form.send")}
        </Button>
      </div>
      {ask.isSuccess ? (
        <p role="status" className="asks-done">
          {t("media:ask.form.sent", { title: ask.data?.title ?? "" })}
        </p>
      ) : null}
      {support.isSuccess ? (
        <p role="status" className="asks-done">
          {t("media:ask.supported", {
            title: support.data?.title ?? "",
            count: support.data?.supporters ?? 1,
          })}
        </p>
      ) : null}
      {ask.isError && !support.isSuccess ? (
        <Problem error={ask.error} onSupport={(id) => support.mutate(id)} />
      ) : null}
    </form>
  ) : (
    <Card title={t("media:ask.form.title")} icon="plus" level={2}>
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
          {price > 0 ? <CoinBadge amount={price} label={t("gamification:value.coins")} /> : null}
          {remaining !== null && remaining !== undefined ? (
            <span className="asks-muted">{t("media:ask.form.left", { count: remaining })}</span>
          ) : null}
          <Button type="submit" disabled={ask.isPending || !title.trim() || remaining === 0}>
            {t("media:ask.form.send")}
          </Button>
        </div>
        {ask.isSuccess ? (
          <p role="status" className="asks-done">
            {t("media:ask.form.sent", { title: ask.data?.title ?? "" })}
          </p>
        ) : null}
        {support.isSuccess ? (
          <p role="status" className="asks-done">
            {t("media:ask.supported", {
              title: support.data?.title ?? "",
              count: support.data?.supporters ?? 1,
            })}
          </p>
        ) : null}
        {ask.isError && !support.isSuccess ? (
          <Problem error={ask.error} onSupport={(id) => support.mutate(id)} />
        ) : null}
      </form>
    </Card>
  );
}

function AskRow({ item, open }: { item: Asked; open: boolean }) {
  const t = useT();
  const format = useFormat();
  const { support, withdraw } = useAskActions();
  const facts = [
    t(`media:kind.${item.kind}`),
    item.creators.join(", "),
    item.year,
    ...Object.values(item.details),
  ].filter(Boolean);
  return (
    <li className="asks-row">
      <div className="asks-row__main">
        <strong className="asks-row__title">
          {item.route ? <Link to={item.route}>{item.title}</Link> : item.title}
        </strong>
        <span className="asks-muted">{facts.join(" · ")}</span>
        {item.status === "refused" && item.reason ? (
          <span className="asks-row__reason">{t("media:ask.reason", { reason: item.reason })}</span>
        ) : null}
      </div>
      <div className="asks-row__side">
        <AskStatusBadge status={item.status} />
        <span className="asks-muted">
          <Icon name="heart" size={13} /> {t("media:ask.wanted", { count: item.supporters })}
        </span>
        <span className="asks-muted">{format.date(new Date(item.updated_at), "medium")}</span>
        {open && !item.mine ? (
          <Button variant="secondary" onClick={() => support.mutate(item.id)} disabled={support.isPending}>
            <Icon name="heart" size={14} />
            {t("media:ask.meToo")}
          </Button>
        ) : null}
        {item.mine && OPEN.includes(item.status) ? (
          <Button variant="ghost" onClick={() => withdraw.mutate(item.id)} disabled={withdraw.isPending}>
            {t("media:ask.withdraw")}
          </Button>
        ) : null}
      </div>
    </li>
  );
}

/**
 * Issue 375: my requests to the team and the other members' open ones (« me too ») — shown in « My
 * requests », beside the request service's; nothing while the module is switched off.
 */
export function AskLists() {
  const t = useT();
  const options = useAskOptions();
  const lists = useMyAsks();
  if (!options.data || !lists.data) return null;
  const others = lists.data.open.filter((item) => !item.mine);
  return (
    <>
      <Card title={t("media:ask.mine")} icon="inbox" level={2}>
        {lists.data.mine.length ? (
          <ul className="asks-list" aria-label={t("media:ask.mine")}>
            {lists.data.mine.map((item) => (
              <AskRow key={item.id} item={item} open={false} />
            ))}
          </ul>
        ) : (
          <p className="asks-muted">
            {t("media:ask.mineEmpty")} <Link to="/requests">{t("media:ask.page.title")}</Link>
          </p>
        )}
      </Card>
      {others.length ? (
        <Card title={t("media:ask.others")} icon="heart" level={2}>
          <ul className="asks-list" aria-label={t("media:ask.others")}>
            {others.map((item) => (
              <AskRow key={item.id} item={item} open />
            ))}
          </ul>
        </Card>
      ) : null}
    </>
  );
}

/** Issue 375: asking the team — the form alone, reached from « Ask for a title » and a title's sheet; the
 * requests themselves are in « My requests ». */
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
        <AskForm
          kinds={options.data.kinds}
          price={options.data.price}
          left={options.data.left}
          start={startOf(params)}
        />
      ) : (
        <p className="ds-panel">{t("media:ask.page.closed")}</p>
      )}
    </section>
  );
}

export default RequestsPage;
