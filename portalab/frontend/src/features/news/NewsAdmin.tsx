import { type FormEvent, useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../design-system/components/Button";
import { Card } from "../../design-system/components/Content";
import { CheckboxField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Popover } from "../../design-system/components/Overlays";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState } from "../../design-system/components/Placeholders";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { MarkdownEditor } from "../content/MarkdownEditor";
import { type NewsEditor, useEditorial, useNewsActions } from "./api";
import { Cover } from "./cover";
import "./news.css";

/**
 * Editorial back office (spec 011 T020, 027 T095): "New article" is the primary action; the editor opens
 * as a card above the list (live sanitized preview), articles are filtered by status with counts, and each
 * article is a row with its status in text, its dates and its actions (edit, publish now or at a time,
 * feature, archive/restore). The server enforces every permission.
 */
const STATUSES = ["draft", "scheduled", "published", "archived"] as const;

function documentLanguage(): string {
  return (typeof document !== "undefined" && document.documentElement.lang.split("-")[0]) || "en";
}

function Editor({ article, onDone }: { article: NewsEditor | null; onDone: () => void }) {
  const t = useT();
  const { save } = useNewsActions();
  const [title, setTitle] = useState(article?.title ?? "");
  const [summary, setSummary] = useState(article?.summary ?? "");
  const [body, setBody] = useState(article?.body_md ?? "");
  const [notify, setNotify] = useState(article?.notify_on_publish ?? false);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(
      {
        ...(article ? { id: article.id } : {}),
        body: {
          title,
          summary,
          body_md: body,
          notify_on_publish: notify,
          language: documentLanguage(),
          ...(article ? { base_version: article.version } : {}),
        },
      },
      { onSuccess: onDone },
    );
  };
  return (
    <Card
      className="news-editor-card"
      title={article ? t("news:admin.editTitle", { title: article.title }) : t("news:admin.editorTitle")}
      icon="newspaper"
      actions={
        <Button variant="ghost" size="icon" aria-label={t("news:admin.close")} onClick={onDone}>
          <Icon name="close" size={18} />
        </Button>
      }
    >
      <form onSubmit={submit} className="news-editor">
        <TextField
          label={t("news:field.title")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
        <TextField
          label={t("news:field.summary")}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <MarkdownEditor
          label={t("news:field.body")}
          value={body}
          onChange={setBody}
          ownerRef={article ? `portalab://news/${article.id}` : undefined}
        />
        <CheckboxField
          label={t("news:field.notify")}
          checked={notify}
          onChange={(e) => setNotify(e.target.checked)}
        />
        <div className="news-admin__actions">
          <Button type="submit" disabled={save.isPending}>
            <Icon name="check" size={16} />
            {t("news:save")}
          </Button>
        </div>
        {save.isError ? <p role="alert">{t("news:saveFailed")}</p> : null}
      </form>
    </Card>
  );
}

function ScheduleButton({ article }: { article: NewsEditor }) {
  const t = useT();
  const { schedule } = useNewsActions();
  const [when, setWhen] = useState("");
  return (
    <Popover
      label={t("news:admin.scheduleTitle")}
      trigger={
        <Button variant="ghost">
          <Icon name="calendar" size={16} />
          {t("news:schedule")}
          <span className="visually-hidden">: {article.title}</span>
        </Button>
      }
    >
      <div className="news-admin__schedule">
        <TextField
          label={t("news:publishAt")}
          type="datetime-local"
          value={when}
          onChange={(e) => setWhen(e.target.value)}
        />
        <Button
          disabled={!when || schedule.isPending}
          onClick={() => schedule.mutate({ id: article.id, at: new Date(when).toISOString() })}
        >
          {t("news:schedule")}
        </Button>
      </div>
    </Popover>
  );
}

function ArticleRow({ article, onEdit }: { article: NewsEditor; onEdit: () => void }) {
  const t = useT();
  const format = useFormat();
  const { publish, lifecycle, feature } = useNewsActions();
  const featured = Boolean(article.featured_from);
  const dates = [
    article.published_at ? format.dateTime(article.published_at) : null,
    article.publish_at ? t("news:scheduledFor", { when: format.dateTime(article.publish_at) }) : null,
  ].filter(Boolean);
  return (
    <li className="news-admin__row" data-status={article.status}>
      <Cover seed={article.category_id ?? article.slug} />
      <div className="news-admin__main">
        <span className="news-admin__title">
          <strong>{article.title}</strong>
          {featured ? (
            <span className="ds-badge news-admin__featured">
              <Icon name="star" size={12} />
              {t("news:isFeatured")}
            </span>
          ) : null}
        </span>
        <span className="news-meta">
          <span className="ds-badge news-admin__status">{t(`news:status.${article.status}`)}</span>
          {dates.length ? ` ${dates.join(" · ")}` : null}
        </span>
      </div>
      <div className="news-admin__actions">
        <Button variant="secondary" onClick={onEdit}>
          <Icon name="settings" size={16} />
          {t("news:edit")}
          <span className="visually-hidden">: {article.title}</span>
        </Button>
        {article.status === "draft" || article.status === "scheduled" ? (
          <>
            <Button onClick={() => publish.mutate(article.id)}>{t("news:publish")}</Button>
            <ScheduleButton article={article} />
          </>
        ) : null}
        {article.status === "published" ? (
          <>
            <Link className="ds-button ds-button--ghost" to={`/news/${article.slug}`}>
              {t("news:admin.view")}
              <span className="visually-hidden">: {article.title}</span>
            </Link>
            <Button variant="ghost" onClick={() => feature.mutate({ id: article.id, on: !featured })}>
              <Icon name="star" size={16} />
              {featured ? t("news:unfeature") : t("news:feature")}
            </Button>
            <Button variant="ghost" onClick={() => lifecycle.mutate({ id: article.id, action: "archive" })}>
              {t("news:archive")}
            </Button>
          </>
        ) : null}
        {article.status === "archived" ? (
          <Button variant="ghost" onClick={() => lifecycle.mutate({ id: article.id, action: "restore" })}>
            {t("news:restore")}
          </Button>
        ) : null}
      </div>
    </li>
  );
}

export function NewsAdmin() {
  const t = useT();
  const headingId = useId();
  const editorial = useEditorial();
  const [editing, setEditing] = useState<NewsEditor | "new" | null>(null);
  const [status, setStatus] = useState<string>("");
  const articles = editorial.data ?? [];
  const shown = articles.filter((a) => !status || a.status === status);
  const count = (s: string) => articles.filter((a) => a.status === s).length;
  return (
    <section aria-labelledby={headingId} className="news-admin">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="newspaper"
        title={t("news:admin.title")}
        context={t("news:admin.subtitle")}
        primary={{ label: t("news:admin.new"), icon: "plus", onSelect: () => setEditing("new") }}
      />
      {editing ? (
        <Editor
          key={editing === "new" ? "new" : editing.id}
          article={editing === "new" ? null : editing}
          onDone={() => setEditing(null)}
        />
      ) : null}
      {editorial.isPending ? <FunctionalState state="loading" /> : null}
      {editorial.isError ? <FunctionalState state="unauthorized" /> : null}
      {editorial.data ? (
        <fieldset className="ds-subnav" aria-label={t("news:admin.title")}>
          <button type="button" aria-pressed={!status} onClick={() => setStatus("")}>
            {t("news:admin.filter.all")} · {articles.length}
          </button>
          {STATUSES.map((s) => (
            <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)}>
              {t(`news:status.${s}`)} · {count(s)}
            </button>
          ))}
        </fieldset>
      ) : null}
      {editorial.data && shown.length === 0 ? (
        <EmptyState
          icon="newspaper"
          title={t("news:admin.empty")}
          action={{ label: t("news:admin.new"), onSelect: () => setEditing("new") }}
        />
      ) : null}
      {shown.length ? (
        <ul className="news-admin__list">
          {shown.map((a) => (
            <ArticleRow key={a.id} article={a} onEdit={() => setEditing(a)} />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export default NewsAdmin;
