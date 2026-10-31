import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useState } from "react";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { SourceCard } from "./ExternalNews";
import "./news.css";

const KEY = ["news", "sources", "mine"] as const;

function problem(error: unknown): string | null {
  if (!error) return null;
  const detail = (error as { detail?: unknown }).detail;
  return typeof detail === "string" ? detail : String(error);
}

/**
 * #299: my own sources in « Mon fil » — RSS or Atom feeds (a site's address will do) only I read, their
 * latest items, and my list as OPML to take to another reader or bring from one. Private.
 */
export function MySources() {
  const t = useT();
  const client = useQueryClient();
  const [url, setUrl] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const sources = useQuery({
    queryKey: [...KEY, "list"],
    queryFn: async () => (await api.GET("/api/v1/me/news/sources")).data?.items ?? [],
  });
  const items = useQuery({
    queryKey: [...KEY, "items"],
    queryFn: async () =>
      (await api.GET("/api/v1/me/news/sources/items", { params: { query: { limit: 20 } } })).data?.items ??
      [],
  });
  const settle = () => void client.invalidateQueries({ queryKey: KEY });
  const follow = useMutation({
    mutationFn: async () => {
      const { error } = await api.POST("/api/v1/me/news/sources", { body: { url } });
      if (error) throw error;
    },
    onSuccess: () => setUrl(""),
    onSettled: settle,
  });
  const unfollow = useMutation({
    mutationFn: async (id: string) => {
      await api.DELETE("/api/v1/me/news/sources/{source_id}", { params: { path: { source_id: id } } });
    },
    onSettled: settle,
  });
  const importing = useMutation({
    mutationFn: async (opml: string) => {
      const { data, error } = await api.POST("/api/v1/me/news/sources/opml", { body: { opml } });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: (data) => setNote(t("news:mine.imported", { added: data.added, skipped: data.skipped })),
    onSettled: settle,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (url.trim()) follow.mutate();
  };
  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) importing.mutate(await file.text());
  };
  const mine = sources.data ?? [];
  return (
    <section className="feed-section" aria-labelledby="feed-sources">
      <h2 id="feed-sources">
        <Icon name="rss" size={18} /> {t("news:mine.title")}
      </h2>
      <p className="admin-muted">{t("news:mine.hint")}</p>
      <form className="feed-add" onSubmit={submit}>
        <TextField
          label={t("news:mine.url")}
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={!url.trim() || follow.isPending}>
          <Icon name="plus" size={16} />
          {t("news:mine.add")}
        </Button>
      </form>
      {follow.isError ? <p role="alert">{problem(follow.error)}</p> : null}
      {mine.length ? (
        <ul className="feed-follows__list">
          {mine.map((source) => (
            <li
              key={source.id}
              className="feed-chip feed-chip--follow"
              data-failing={source.status === "error" || undefined}
            >
              <span>
                <Icon name="rss" size={14} />
                {source.name}
              </span>
              <button
                type="button"
                aria-label={t("news:mine.remove", { name: source.name })}
                onClick={() => unfollow.mutate(source.id)}
              >
                <Icon name="close" size={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : sources.isSuccess ? (
        <p className="admin-muted">{t("news:mine.empty")}</p>
      ) : null}
      <div className="news-source__actions">
        {mine.length ? (
          <a
            className="ds-button ds-button--ghost"
            href="/api/v1/me/news/sources/opml"
            download="portalab-sources.opml"
          >
            <Icon name="download" size={16} />
            {t("news:mine.export")}
          </a>
        ) : null}
        <label className="ds-button ds-button--ghost news-opml">
          <Icon name="upload" size={16} />
          {t("news:mine.import")}
          <input
            type="file"
            accept=".opml,.xml,text/xml,text/x-opml"
            className="visually-hidden"
            onChange={pick}
          />
        </label>
      </div>
      {note ? <p role="status">{note}</p> : null}
      {importing.isError ? <p role="alert">{problem(importing.error)}</p> : null}
      {items.data?.length ? (
        <>
          <h3 className="news-page__section">{t("news:mine.items")}</h3>
          <ul className="news-external__list">
            {items.data.map((item) => (
              <SourceCard key={item.id} item={item} />
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
