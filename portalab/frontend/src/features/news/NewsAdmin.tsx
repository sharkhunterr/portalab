import { type FormEvent, useId, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, TextField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { MarkdownEditor } from "../content/MarkdownEditor";
import { type NewsEditor, useEditorial, useNewsActions } from "./api";

/**
 * Editorial back office (spec 011 T020): drafts with a live sanitized preview, publish now or at a time,
 * feature/unfeature, archive/restore. States are text; the server enforces every permission.
 */
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
          language: "en",
          ...(article ? { base_version: article.version } : {}),
        },
      },
      { onSuccess: onDone },
    );
  };
  return (
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
      <Button type="submit" disabled={save.isPending}>
        {t("news:save")}
      </Button>
      {save.isError ? <p role="alert">{t("news:saveFailed")}</p> : null}
    </form>
  );
}

export function NewsAdmin() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const editorial = useEditorial();
  const { publish, schedule, lifecycle, feature } = useNewsActions();
  const [editing, setEditing] = useState<NewsEditor | "new" | null>(null);
  const [when, setWhen] = useState("");
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("news:admin.title")}</h2>
      <Button onClick={() => setEditing("new")}>{t("news:admin.new")}</Button>
      {editing ? (
        <Editor article={editing === "new" ? null : editing} onDone={() => setEditing(null)} />
      ) : null}
      {editorial.isPending ? <FunctionalState state="loading" /> : null}
      {editorial.isError ? <FunctionalState state="unauthorized" /> : null}
      <ul className="news-list">
        {(editorial.data ?? []).map((a) => (
          <li key={a.id}>
            <strong>{a.title}</strong> · {t(`news:status.${a.status}`)}
            {a.publish_at ? ` · ${t("news:scheduledFor", { when: format.dateTime(a.publish_at) })}` : ""}
            {a.featured_from ? ` · ${t("news:isFeatured")}` : ""}
            <div className="ds-stack ds-stack--row">
              <Button variant="secondary" onClick={() => setEditing(a)}>
                {t("news:edit")}
                <span className="visually-hidden">: {a.title}</span>
              </Button>
              {a.status === "draft" || a.status === "scheduled" ? (
                <>
                  <Button variant="secondary" onClick={() => publish.mutate(a.id)}>
                    {t("news:publish")}
                  </Button>
                  <TextField
                    label={t("news:publishAt")}
                    type="datetime-local"
                    value={when}
                    onChange={(e) => setWhen(e.target.value)}
                  />
                  <Button
                    variant="secondary"
                    disabled={!when}
                    onClick={() => schedule.mutate({ id: a.id, at: new Date(when).toISOString() })}
                  >
                    {t("news:schedule")}
                  </Button>
                </>
              ) : null}
              {a.status === "published" ? (
                <>
                  <Button
                    variant="secondary"
                    onClick={() => feature.mutate({ id: a.id, on: !a.featured_from })}
                  >
                    {a.featured_from ? t("news:unfeature") : t("news:feature")}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => lifecycle.mutate({ id: a.id, action: "archive" })}
                  >
                    {t("news:archive")}
                  </Button>
                </>
              ) : null}
              {a.status === "archived" ? (
                <Button variant="secondary" onClick={() => lifecycle.mutate({ id: a.id, action: "restore" })}>
                  {t("news:restore")}
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default NewsAdmin;
