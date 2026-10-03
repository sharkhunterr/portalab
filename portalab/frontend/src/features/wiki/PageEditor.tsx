import { type FormEvent, useEffect, useId, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, TextField } from "../../design-system/components/Field";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import { MarkdownEditor } from "../content/MarkdownEditor";
import { type DiffSegment, usePage, useWikiActions } from "./api";
import { DiffView } from "./History";

/**
 * Wiki editor (spec 011 T012/T014): create or edit with the version the editor started from; a concurrent
 * save answers 409 with the changes made meanwhile — shown with textual markers — so the editor merges
 * consciously and saves again on the new version.
 */
export function PageEditor() {
  const t = useT();
  const navigate = useNavigate();
  const { slug } = useParams();
  const headingId = useId();
  const existing = usePage(slug ?? "");
  const { create, update } = useWikiActions();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [aiReadable, setAiReadable] = useState(false);
  const [base, setBase] = useState<number | null>(null);
  const [conflict, setConflict] = useState<{ version: number; lines: DiffSegment[] } | null>(null);
  useEffect(() => {
    if (existing.data && base === null) {
      setTitle(existing.data.title);
      setBody(existing.data.body_md);
      setAiReadable(existing.data.readable_by_ai);
      setBase(existing.data.version);
    }
  }, [existing.data, base]);
  if (slug && existing.isPending) return <FunctionalState state="loading" />;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const fields = {
      title,
      body_md: body,
      readable_by_ai: aiReadable,
      change_note: "",
      language: existing.data?.source_language ?? "en",
      publish: false,
    };
    if (!existing.data) {
      create.mutate(fields, { onSuccess: (page) => navigate(`/wiki/${page.slug}`) });
      return;
    }
    update.mutate(
      {
        id: existing.data.id,
        body: { ...fields, base_version: base ?? existing.data.version, tags: existing.data.tags },
      },
      {
        onSuccess: (page) => navigate(`/wiki/${page.slug}`),
        onError: (error) => {
          if (error instanceof ApiError && error.code === "wiki.version_conflict") {
            const diff = error.extensions.diff as { lines: DiffSegment[] } | undefined;
            setConflict({ version: Number(error.extensions.current_version), lines: diff?.lines ?? [] });
          }
        },
      },
    );
  };
  const failed = (create.error ?? update.error) as ApiError | null;
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>
        {existing.data ? t("wiki:editTitle", { title: existing.data.title }) : t("wiki:new")}
      </h2>
      {conflict ? (
        <div role="alert" className="wiki-conflict">
          <p>{t("wiki:conflict")}</p>
          <DiffView segments={conflict.lines} />
          <Button
            variant="secondary"
            onClick={() => {
              setBase(conflict.version);
              setConflict(null);
            }}
          >
            {t("wiki:conflictKeep")}
          </Button>
        </div>
      ) : null}
      <form onSubmit={submit}>
        <TextField
          label={t("wiki:pageTitle")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
        <MarkdownEditor
          label={t("wiki:body")}
          value={body}
          onChange={setBody}
          ownerRef={existing.data ? `portalab://wiki/${existing.data.id}` : undefined}
        />
        <CheckboxField
          label={t("wiki:aiReadable")}
          checked={aiReadable}
          onChange={(e) => setAiReadable(e.target.checked)}
        />
        <Button type="submit" disabled={create.isPending || update.isPending || Boolean(conflict)}>
          {t("wiki:save")}
        </Button>
        {failed && failed.code !== "wiki.version_conflict" ? (
          <p role="alert">{t("wiki:saveFailed")}</p>
        ) : null}
      </form>
    </section>
  );
}

export default PageEditor;
