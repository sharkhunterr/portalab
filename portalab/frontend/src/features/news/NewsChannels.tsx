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
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";

/**
 * Channels (027): the news desk's categories are channels — described, with an icon, and e-mailed to their
 * subscribers when « newsletter » is on (members unsubscribe per channel). Issue 325: the automatic
 * newsletters are in ``editions/AutomaticNewsletters``.
 */
export type Channel = components["schemas"]["NewsCategoryOut"];

const CHANNELS_KEY = ["admin", "news", "channels"] as const;
const ICONS = [
  "newspaper",
  "film",
  "tv",
  "book",
  "joystick",
  "music",
  "star",
  "sparkles",
  "megaphone",
  "calendar",
];

export function useChannels() {
  return useQuery({
    queryKey: CHANNELS_KEY,
    queryFn: async () => ((await api.GET("/api/v1/admin/news/categories")).data ?? []) as Channel[],
  });
}

function ChannelForm({ channel, onDone }: { channel?: Channel; onDone: () => void }) {
  const t = useT();
  const client = useQueryClient();
  const [key, setKey] = useState(channel?.key ?? "");
  const [name, setName] = useState(channel?.name ?? "");
  const [description, setDescription] = useState(channel?.description ?? "");
  const [icon, setIcon] = useState(channel?.icon ?? "newspaper");
  const [newsletter, setNewsletter] = useState(channel?.newsletter ?? true);
  const [enabled, setEnabled] = useState(channel?.enabled ?? true);
  const save = useMutation({
    mutationFn: async () =>
      api.PUT("/api/v1/admin/news/categories", {
        body: { key, name, description, icon, newsletter, enabled, position: channel?.position ?? 0 },
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: CHANNELS_KEY });
      onDone();
    },
  });
  return (
    <form
      className="admin-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <FormGrid>
        <TextField
          label={t("news:channels.name")}
          required
          maxLength={120}
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (!channel)
              setKey(
                e.target.value
                  .normalize("NFKD")
                  .replace(/[^\w\s-]/g, "")
                  .trim()
                  .toLowerCase()
                  .replace(/[\s_]+/g, "-")
                  .slice(0, 60),
              );
          }}
        />
        <SelectField label={t("news:channels.icon")} value={icon} onChange={(e) => setIcon(e.target.value)}>
          {ICONS.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t("news:channels.description")}
          maxLength={300}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </FormGrid>
      <CheckboxField
        label={t("news:channels.newsletter")}
        hint={t("news:channels.newsletterHint")}
        checked={newsletter}
        onChange={(e) => setNewsletter(e.target.checked)}
      />
      <CheckboxField
        label={t("news:channels.enabled")}
        checked={enabled}
        onChange={(e) => setEnabled(e.target.checked)}
      />
      {save.isError ? (
        <p role="alert" className="services-admin__ko">
          {save.error instanceof ApiError ? save.error.message : t("news:saveFailed")}
        </p>
      ) : null}
      <FormActions>
        <Button type="submit" disabled={save.isPending || !key}>
          <Icon name="check" size={16} />
          {t("news:save")}
        </Button>
      </FormActions>
    </form>
  );
}

export function ChannelsPanel() {
  const t = useT();
  const channels = useChannels();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <AdminSection
      title={t("news:channels.title")}
      description={t("news:channels.hint")}
      icon="megaphone"
      actions={
        <Dialog
          open={open === "new"}
          onOpenChange={(next) => setOpen(next ? "new" : null)}
          title={t("news:channels.new")}
          closeLabel={t("news:admin.close")}
          trigger={
            <Button>
              <Icon name="plus" size={16} />
              {t("news:channels.new")}
            </Button>
          }
        >
          <ChannelForm onDone={() => setOpen(null)} />
        </Dialog>
      }
    >
      {channels.data?.length === 0 ? (
        <EmptyState
          icon="megaphone"
          title={t("news:channels.empty")}
          action={{ label: t("news:channels.new"), onSelect: () => setOpen("new") }}
        />
      ) : null}
      <ul className="news-channels">
        {(channels.data ?? []).map((channel) => (
          <li key={channel.id} className="news-channel" data-disabled={!channel.enabled || undefined}>
            <span className="news-channel__icon" aria-hidden="true">
              <Icon name={channel.icon ?? "newspaper"} size={20} />
            </span>
            <span className="news-channel__text">
              <strong>{channel.name}</strong>
              <span className="admin-muted">{channel.description || channel.key}</span>
            </span>
            <span className="news-channel__badges">
              {channel.newsletter ? (
                <StatusBadge tone="ok">
                  <Icon name="mail" size={12} /> {t("news:channels.byEmail")}
                </StatusBadge>
              ) : (
                <StatusBadge tone="neutral">{t("news:channels.portalOnly")}</StatusBadge>
              )}
              {!channel.enabled ? <StatusBadge tone="warn">{t("news:channels.disabled")}</StatusBadge> : null}
            </span>
            <Dialog
              open={open === channel.id}
              onOpenChange={(next) => setOpen(next ? channel.id : null)}
              title={channel.name}
              closeLabel={t("news:admin.close")}
              trigger={
                <Button variant="ghost">
                  <Icon name="settings" size={16} />
                  {t("news:edit")}
                </Button>
              }
            >
              <ChannelForm channel={channel} onDone={() => setOpen(null)} />
            </Dialog>
          </li>
        ))}
      </ul>
    </AdminSection>
  );
}
