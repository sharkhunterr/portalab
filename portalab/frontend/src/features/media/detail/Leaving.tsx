import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useNotify } from "../../../design-system/components/Notification";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useSlots } from "../../../shell/slots/providers";

interface LeavingEntry {
  kind: string;
  title: string;
  collection: string;
  added_at: string;
  delete_at: string | null;
  size: number | null;
}
interface LeavingStatus {
  configured: boolean;
  leaving: LeavingEntry[];
  delete_at: string | null;
  saved: { at: string; me: boolean } | null;
  credits: number;
}

/** #57: the shop's rescue products (the cheaper first). */
const RESCUE_SHOP = "/marketplace?type=media_rescue";

/**
 * « Leaving soon » (#57): when the library's cleanup (Maintainerr) will delete this title — or some of its
 * seasons — and, with a rescue bought in the shop, « Save this title » (for everyone). Once saved, a line
 * says so; « Ask the assistant » asks why it goes, when, and how to keep it. Nothing when the cleanup tool is
 * not connected or the title is not on its list.
 */
export function LeavingNotice({ objectId, title }: { objectId: string; title?: string | undefined }) {
  const t = useT();
  const { ai } = useSlots();
  const location = useLocation();
  const format = useFormat();
  const notify = useNotify();
  const client = useQueryClient();
  const status = useQuery({
    queryKey: ["media", "leaving", objectId],
    retry: false,
    staleTime: 60_000,
    queryFn: async () =>
      (
        await api.GET("/api/v1/media/{object_id}/leaving", {
          params: { path: { object_id: objectId } },
        })
      ).data as unknown as LeavingStatus,
  });
  const keep = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/media/{object_id}/leaving/keep", {
        params: { path: { object_id: objectId } },
      });
      if (error) throw error;
      return data as unknown as LeavingStatus;
    },
    onSuccess: (data) => {
      client.setQueryData(["media", "leaving", objectId], data);
      void client.invalidateQueries({ queryKey: ["widget", "media.leaving"] });
      notify({ severity: "success", title: t("media:leaving.done") });
    },
    onError: () => notify({ severity: "warning", title: t("media:leaving.failed") }),
  });
  const data = status.data;
  if (!data?.configured) return null;
  const when = (iso: string) => format.relative((Date.parse(iso) - Date.now()) / 1000);
  if (data.saved && !data.leaving.length) {
    return (
      <p className="media-leaving" data-state="saved">
        <Icon name="shield" size={16} />
        {t(data.saved.me ? "media:leaving.saved_me" : "media:leaving.saved", { when: when(data.saved.at) })}
      </p>
    );
  }
  if (!data.leaving.length) return null;
  const seasons = data.leaving.filter((entry) => entry.kind === "season").length;
  const whole = data.leaving.some((entry) => entry.kind !== "season");
  const message = data.delete_at
    ? whole || !seasons
      ? t("media:leaving.when", { when: when(data.delete_at) })
      : t("media:leaving.seasons", { count: seasons, when: when(data.delete_at) })
    : t("media:leaving.undated");
  const rules = [...new Set(data.leaving.map((entry) => entry.collection).filter(Boolean))];
  return (
    <section className="media-leaving" data-state="leaving" aria-label={t("media:leaving.title")}>
      <Icon name="trash" size={18} />
      <div className="media-leaving__text">
        <strong>{t("media:leaving.title")}</strong>
        <p>{message}</p>
        {rules.length ? (
          <small>{rules.map((name) => t("media:leaving.collection", { name })).join(" · ")}</small>
        ) : null}
      </div>
      <div className="media-leaving__actions">
        <div className="media-leaving__rescue">
          {data.credits > 0 ? (
            <Button variant="primary" onClick={() => keep.mutate()} disabled={keep.isPending}>
              <Icon name="shield" size={16} />
              {t("media:leaving.save")}
            </Button>
          ) : (
            <Link className="ds-button ds-button--secondary" to={RESCUE_SHOP}>
              <Icon name="shop" size={16} />
              {t("media:leaving.buy")}
            </Link>
          )}
          <small>{t("media:leaving.credits", { count: data.credits })}</small>
        </div>
        {ai?.available && title ? (
          <button
            type="button"
            className="ds-button ds-button--quiet"
            onClick={() => ai.open({ route: location.pathname, question: t("media:leaving.ask", { title }) })}
          >
            <Icon name="sparkles" size={16} /> {t("media:journey.askButton")}
          </button>
        ) : null}
      </div>
    </section>
  );
}
