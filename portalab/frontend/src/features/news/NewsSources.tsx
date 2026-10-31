import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { api } from "../../api/client";
import type { components } from "../../api/generated/schema";
import { AdminSection, FormActions, FormGrid, StatusBadge } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { CheckboxField, SelectField, TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { Dialog } from "../../design-system/components/Overlays";
import { EmptyState } from "../../design-system/components/Placeholders";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { SourceCard } from "./ExternalNews";
import { useChannels } from "./NewsChannels";

/**
 * #299: the news sources — RSS or Atom feeds (a site's address will do: its feed is found), previewed before
 * they are added, read on their cadence; their latest items, to pin on « À la une » or hide.
 */
type Source = components["schemas"]["NewsSourceOut"];
type Preview = components["schemas"]["SourcePreviewOut"];

const KEY = ["admin", "news", "sources"] as const;
const CADENCES = [15, 30, 60, 180, 360, 720, 1440];

function useSources() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => (await api.GET("/api/v1/admin/news/sources")).data?.items ?? [],
  });
}

function problem(error: unknown): string | null {
  if (!error) return null;
  const detail = (error as { detail?: unknown }).detail;
  return typeof detail === "string" ? detail : String(error);
}

function words(text: string): string[] {
  return text
    .split(",")
    .map((w) => w.trim())
    .filter(Boolean);
}

function SourceForm({ source, onDone }: { source?: Source; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const channels = useChannels();
  const [url, setUrl] = useState(source?.url ?? "");
  const [name, setName] = useState(source?.name ?? "");
  const [channel, setChannel] = useState(source?.category_id ?? "");
  const [cadence, setCadence] = useState(source?.refresh_minutes ?? 60);
  const [include, setInclude] = useState((source?.include_words ?? []).join(", "));
  const [exclude, setExclude] = useState((source?.exclude_words ?? []).join(", "));
  const [enabled, setEnabled] = useState(source?.enabled ?? true);
  const [preview, setPreview] = useState<Preview | null>(null);
  const look = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/admin/news/sources/preview", { body: { url } });
      if (error || !data) throw error;
      return data;
    },
    onSuccess: (data) => {
      setPreview(data);
      setUrl(data.url);
      if (!name.trim()) setName(data.title);
    },
  });
  const save = useMutation({
    mutationFn: async () => {
      const body = {
        ...(source ? { id: source.id } : {}),
        name,
        url,
        category_id: channel || null,
        enabled,
        include_words: words(include),
        exclude_words: words(exclude),
        refresh_minutes: cadence,
      };
      const { error } = await api.PUT("/api/v1/admin/news/sources", { body });
      if (error) throw error;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["news", "sources"] });
      onDone();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <form className="admin-form" onSubmit={submit}>
      <div className="news-source-form__look">
        <TextField
          label={t("news:sources.url")}
          hint={t("news:sources.urlHint")}
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button
          variant="secondary"
          type="button"
          disabled={!url || look.isPending}
          onClick={() => look.mutate()}
        >
          <Icon name="eye" size={16} />
          {t("news:sources.preview")}
        </Button>
      </div>
      {look.isError ? <p role="alert">{problem(look.error)}</p> : null}
      {preview ? (
        <div className="news-source-form__preview">
          <p className="admin-muted">
            {t("news:sources.found", { title: preview.title, count: preview.items.length })}
          </p>
          <ul>
            {preview.items.slice(0, 5).map((item) => (
              <li key={item.link}>
                <strong>{item.title}</strong>
                {item.mentions.length ? (
                  <span className="news-source-card__mentions">
                    {item.mentions.map((m) => (
                      <span key={`${m.kind}:${m.ref}`} className="feed-chip">
                        <Icon name={m.kind === "person" ? "user" : "film"} size={12} />
                        {m.label}
                      </span>
                    ))}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <FormGrid>
        <TextField
          label={t("news:sources.name")}
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <SelectField
          label={t("news:sources.channel")}
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
        >
          <option value="">{t("news:sources.noChannel")}</option>
          {(channels.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </SelectField>
        <SelectField
          label={t("news:sources.cadence")}
          value={String(cadence)}
          onChange={(e) => setCadence(Number(e.target.value))}
        >
          {CADENCES.map((minutes) => (
            <option key={minutes} value={minutes}>
              {t("news:sources.every", { minutes })}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("news:sources.include")}
          hint={t("news:sources.wordsHint")}
          value={include}
          onChange={(e) => setInclude(e.target.value)}
        />
        <TextField
          label={t("news:sources.exclude")}
          hint={t("news:sources.wordsHint")}
          value={exclude}
          onChange={(e) => setExclude(e.target.value)}
        />
      </FormGrid>
      <CheckboxField
        label={t("news:sources.enabled")}
        checked={enabled}
        onChange={(e) => setEnabled(e.target.checked)}
      />
      {save.isError ? <p role="alert">{problem(save.error)}</p> : null}
      <FormActions>
        <Button type="submit" disabled={save.isPending || !name.trim() || !url}>
          {save.isPending ? t("news:sources.reading") : t("news:sources.save")}
        </Button>
      </FormActions>
    </form>
  );
}

function SourceRow({ source }: { source: Source }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [sure, setSure] = useState(false);
  const refresh = useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/admin/news/sources/{source_id}/refresh", {
        params: { path: { source_id: source.id } },
      });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["news", "sources"] });
    },
  });
  const remove = useMutation({
    mutationFn: async () => {
      await api.DELETE("/api/v1/admin/news/sources/{source_id}", {
        params: { path: { source_id: source.id } },
      });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ["news", "sources"] });
    },
  });
  const when = source.last_run_at
    ? format.relative((Date.parse(source.last_run_at) - Date.now()) / 1000)
    : null;
  return (
    <li className="news-channel" data-disabled={!source.enabled || undefined}>
      <span className="news-channel__icon" aria-hidden="true">
        <Icon name="rss" size={20} />
      </span>
      <span className="news-channel__text">
        <strong>{source.name}</strong>
        <span className="admin-muted">{source.url}</span>
        {source.status === "error" && source.last_error ? (
          <span className="admin-muted">{source.last_error}</span>
        ) : null}
      </span>
      <span className="news-channel__badges">
        {source.status === "ok" ? (
          <StatusBadge tone="ok">{t("news:sources.read", { when: when ?? "" })}</StatusBadge>
        ) : source.status === "error" ? (
          <StatusBadge tone="warn">{t("news:sources.failing")}</StatusBadge>
        ) : (
          <StatusBadge tone="neutral">{t("news:sources.never")}</StatusBadge>
        )}
        <StatusBadge tone="neutral">{t("news:sources.items", { count: source.items })}</StatusBadge>
        {!source.enabled ? <StatusBadge tone="warn">{t("news:channels.disabled")}</StatusBadge> : null}
      </span>
      <span className="news-source__actions">
        <Button variant="ghost" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          <Icon name="sync" size={16} />
          {t("news:sources.now")}
        </Button>
        <Dialog
          open={editing}
          onOpenChange={setEditing}
          title={source.name}
          closeLabel={t("news:admin.close")}
          trigger={
            <Button variant="ghost">
              <Icon name="settings" size={16} />
              {t("news:edit")}
            </Button>
          }
        >
          <SourceForm source={source} onDone={() => setEditing(false)} />
        </Dialog>
        <Button
          variant="ghost"
          onClick={() => (sure ? remove.mutate() : setSure(true))}
          disabled={remove.isPending}
          aria-label={t("news:sources.remove", { name: source.name })}
        >
          <Icon name="trash" size={16} />
          {sure ? t("news:sources.sure") : null}
        </Button>
      </span>
    </li>
  );
}

/** The latest items of every source, the hidden ones too: pin one on « À la une », hide one, or bring it back. */
function LatestItems() {
  const t = useT();
  const client = useQueryClient();
  const items = useQuery({
    queryKey: [...KEY, "items"],
    queryFn: async () =>
      (await api.GET("/api/v1/admin/news/sources/items", { params: { query: { limit: 30 } } })).data?.items ??
      [],
  });
  const mark = useMutation({
    mutationFn: async ({ id, pinned, hidden }: { id: string; pinned?: boolean; hidden?: boolean }) => {
      await api.PUT("/api/v1/admin/news/sources/items/{item_id}", {
        params: { path: { item_id: id } },
        body: { pinned: pinned ?? null, hidden: hidden ?? null },
      });
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: [...KEY, "items"] });
      void client.invalidateQueries({ queryKey: ["news", "sources"] });
    },
  });
  if (!items.data?.length) return null;
  return (
    <AdminSection
      title={t("news:sources.latest")}
      description={t("news:sources.latestHint")}
      icon="newspaper"
    >
      <ul className="news-external__list">
        {items.data.map((item) => (
          <SourceCard
            key={item.id}
            item={item}
            actions={
              <>
                <Button variant="ghost" onClick={() => mark.mutate({ id: item.id, pinned: !item.pinned })}>
                  <Icon name="pin" size={16} />
                  {item.pinned ? t("news:sources.unpin") : t("news:sources.pin")}
                </Button>
                <Button variant="ghost" onClick={() => mark.mutate({ id: item.id, hidden: !item.hidden })}>
                  <Icon name={item.hidden ? "eye" : "hide"} size={16} />
                  {item.hidden ? t("news:sources.show") : t("news:sources.hide")}
                </Button>
              </>
            }
          />
        ))}
      </ul>
    </AdminSection>
  );
}

export function SourcesPanel() {
  const t = useT();
  const sources = useSources();
  const [adding, setAdding] = useState(false);
  return (
    <>
      <AdminSection
        title={t("news:sources.title")}
        description={t("news:sources.hint")}
        icon="rss"
        actions={
          <Dialog
            open={adding}
            onOpenChange={setAdding}
            title={t("news:sources.new")}
            closeLabel={t("news:admin.close")}
            trigger={
              <Button>
                <Icon name="plus" size={16} />
                {t("news:sources.new")}
              </Button>
            }
          >
            <SourceForm onDone={() => setAdding(false)} />
          </Dialog>
        }
      >
        {sources.data?.length === 0 ? (
          <EmptyState
            icon="rss"
            title={t("news:sources.empty")}
            action={{ label: t("news:sources.new"), onSelect: () => setAdding(true) }}
          />
        ) : null}
        <ul className="news-channels">
          {(sources.data ?? []).map((source) => (
            <SourceRow key={source.id} source={source} />
          ))}
        </ul>
      </AdminSection>
      <LatestItems />
    </>
  );
}
