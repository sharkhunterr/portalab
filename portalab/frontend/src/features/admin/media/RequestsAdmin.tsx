import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import {
  AdminEmpty,
  AdminPage,
  AdminTabs,
  StatusBadge,
  type Tone,
} from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { metadataImage } from "../../media/detail/Enrichment";
import { Poster } from "../../media/MediaGrid";
import "../admin.css";

interface QueueItem {
  id: string;
  object_id: string | null;
  title: string;
  kind: string;
  state: string;
  requested_at: string;
  seasons: number[] | null;
  is4k: boolean;
  requester: { id: string; name: string | null } | null;
  decidable: boolean;
  decision: { approved: boolean; reason: string | null; at: string } | null;
  image_id: string | null;
  poster_ref?: string | null;
}

const TABS = ["pending", "open", "all"] as const;
const TONES: Record<string, Tone> = {
  pending: "warn",
  approved: "info",
  processing: "info",
  available: "ok",
  declined: "bad",
  failed: "bad",
  cancelled: "neutral",
};

function Decline({ item, onDecline }: { item: QueueItem; onDecline: (reason: string) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setReason("");
      }}
      trigger={
        <Button variant="secondary">
          <Icon name="close" size={16} />
          {t("media:moderation.decline")}
        </Button>
      }
      title={t("media:moderation.declineTitle", { title: item.title })}
      description={t("media:moderation.declineHint")}
      closeLabel={t("media:discover.cancel")}
      footer={
        <Button
          onClick={() => {
            onDecline(reason);
            setOpen(false);
          }}
        >
          {t("media:moderation.decline")}
        </Button>
      }
    >
      <TextField
        label={t("media:moderation.reason")}
        value={reason}
        maxLength={500}
        onChange={(event) => setReason(event.target.value)}
      />
    </Dialog>
  );
}

/**
 * #4: members' requests to decide — the pending ones first, each with its poster, who asked and when, the
 * seasons and 4K asked for; « Approve » sends it on (the request service passes it to the download
 * manager), « Decline » with a reason the member reads (a bought request comes back to them).
 */
export default function RequestsAdmin() {
  const t = useT();
  const [tab, setTab] = useState<(typeof TABS)[number]>("pending");
  return (
    <AdminPage
      icon="inbox"
      title={t("media:moderation.title")}
      description={t("media:moderation.pitch")}
      tabs={
        <AdminTabs
          label={t("media:moderation.title")}
          current={tab}
          onChange={(next) => setTab(next as (typeof TABS)[number])}
          tabs={TABS.map((key) => ({ key, label: t(`media:moderation.tab.${key}`) }))}
        />
      }
    >
      <MediaRequestsList tab={tab} />
    </AdminPage>
  );
}

/** The requests of one tab — everyone's, or one member's (``userId``, their admin card). */
export function MediaRequestsList({ tab, userId }: { tab: (typeof TABS)[number]; userId?: string }) {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const queue = useQuery({
    queryKey: ["admin", "media", "requests", tab, userId ?? null],
    queryFn: async () =>
      (
        await api.GET("/api/v1/admin/media/requests", {
          params: { query: { state: tab, ...(userId ? { user_id: userId } : {}) } },
        })
      ).data as unknown as {
        items: QueueItem[];
      },
  });
  const decide = useMutation({
    mutationFn: async ({ id, approve, reason }: { id: string; approve: boolean; reason?: string }) => {
      const path = approve
        ? "/api/v1/admin/media/requests/{request_id}/approve"
        : "/api/v1/admin/media/requests/{request_id}/decline";
      const { error } = await api.POST(path, {
        params: { path: { request_id: id } },
        body: { reason: reason?.trim() || null },
      });
      if (error) throw error;
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["admin", "media", "requests"] }),
  });
  const items = queue.data?.items ?? [];
  return (
    <>
      {decide.isError ? (
        <p role="alert" className="quota-admin__error">
          {t("media:moderation.failed")}
        </p>
      ) : null}
      {queue.isPending ? <FunctionalState state="loading" /> : null}
      {queue.isError ? <FunctionalState state="error" onRetry={() => queue.refetch()} /> : null}
      {queue.data && !items.length ? (
        <AdminEmpty icon="check" title={t(`media:moderation.none.${tab}`)} />
      ) : null}
      <ul className="moderation-list">
        {items.map((item) => (
          <li key={item.id} className="moderation-item" data-state={item.state}>
            <span className="moderation-item__poster">
              <Poster
                src={
                  item.image_id
                    ? `/api/v1/media/images/${item.image_id}`
                    : metadataImage(item.poster_ref, "w185")
                }
                kind={item.kind}
              />
            </span>
            <div className="moderation-item__body">
              <div className="moderation-item__head">
                {item.object_id ? (
                  <Link to={`/media/${item.object_id}`}>
                    <strong>{item.title}</strong>
                  </Link>
                ) : (
                  <strong>{item.title}</strong>
                )}
                <StatusBadge tone={TONES[item.state] ?? "neutral"}>
                  {t(`media:requests.state.${item.state}`)}
                </StatusBadge>
              </div>
              <p className="moderation-item__facts">
                {[
                  t(`media:kind.${item.kind}`),
                  item.seasons?.length
                    ? t("media:moderation.seasons", { list: item.seasons.join(", ") })
                    : item.kind === "series"
                      ? t("media:moderation.allSeasons")
                      : null,
                  item.is4k ? "4K" : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <p className="moderation-item__who">
                {t("media:moderation.by", {
                  name: item.requester?.name ?? t("media:moderation.someone"),
                  when: format.relative((Date.parse(item.requested_at) - Date.now()) / 1000),
                })}
              </p>
              {item.decision?.reason ? (
                <p className="moderation-item__reason">« {item.decision.reason} »</p>
              ) : null}
            </div>
            {item.decidable ? (
              <div className="moderation-item__actions">
                <Button
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: item.id, approve: true })}
                >
                  <Icon name="check" size={16} />
                  {t("media:moderation.approve")}
                </Button>
                <Decline
                  item={item}
                  onDecline={(reason) => decide.mutate({ id: item.id, approve: false, reason })}
                />
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </>
  );
}
