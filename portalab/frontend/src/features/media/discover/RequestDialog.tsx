import { useQueryClient } from "@tanstack/react-query";
import { type ReactElement, useId, useState } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { MediaError, useRequestActions } from "../api";
import { QuotaLine } from "../requests/QuotaSummary";
import { type RequestableSeason, requestsLeft, useRequestQuota } from "./api";

export interface RequestTarget {
  tmdb_id: string;
  kind: "movie" | "series";
  title: string;
  ids?: Record<string, string>;
  seasons?: RequestableSeason[];
  /** the request service has a 4K server for this kind */
  four_k?: boolean;
}

/** A season one can still ask for: neither in the library nor asked for already. */
const askable = (season: RequestableSeason) => season.status === "unknown";

/**
 * #4: asking for a film or a series — like Seerr's own form: a series' seasons (those still missing, all
 * by default), 4K when wanted, what it takes of my quota (#3) — then a confirmation, and the request joins
 * « My requests ». A title someone already asked for says so instead.
 */
export function RequestDialog({
  target,
  trigger,
  onDone,
}: {
  target: RequestTarget;
  trigger: ReactElement;
  /** #92: told once the request is sent (a person's page shows the title asked for) */
  onDone?: () => void;
}) {
  const t = useT();
  const formId = useId();
  const client = useQueryClient();
  const { submit } = useRequestActions();
  const quota = useRequestQuota();
  const missing = (target.seasons ?? []).filter(askable).map((s) => s.number);
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<number[]>(missing);
  const [is4k, setIs4k] = useState(false);
  const [key, setKey] = useState(() => `ask-${target.kind}-${target.tmdb_id}-${Date.now()}`);
  const left = requestsLeft(quota.data, target.kind);
  const blocked = left !== null && left <= 0;
  const series = target.kind === "series" && (target.seasons?.length ?? 0) > 0;
  const error = submit.error instanceof MediaError ? submit.error : null;
  const send = () =>
    submit.mutate(
      {
        ids: target.ids && Object.keys(target.ids).length ? target.ids : { tmdb: target.tmdb_id },
        kind: target.kind,
        title: target.title,
        idempotency_key: key,
        ...(series ? { seasons: chosen.length === missing.length ? null : chosen } : {}),
        is4k,
      },
      {
        onSettled: () => {
          void client.invalidateQueries({ queryKey: ["media", "quota"] });
          void client.invalidateQueries({ queryKey: ["media", "discover"] });
          onDone?.();
        },
      },
    );
  const toggle = (number: number) =>
    setChosen((current) =>
      current.includes(number)
        ? current.filter((n) => n !== number)
        : [...current, number].sort((a, b) => a - b),
    );
  return (
    <Dialog
      trigger={trigger}
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          submit.reset();
          setChosen(missing);
          setKey(`ask-${target.kind}-${target.tmdb_id}-${Date.now()}`);
        }
      }}
      title={t("media:discover.askTitle", { title: target.title })}
      closeLabel={submit.isSuccess ? t("media:discover.close") : t("media:discover.cancel")}
      footer={
        submit.isSuccess ? (
          <Link className="ds-button ds-button--primary" to="/media/requests?tab=list">
            <Icon name="inbox" size={16} />
            {t("media:discover.seeRequests")}
          </Link>
        ) : (
          <Button
            type="submit"
            form={formId}
            disabled={submit.isPending || blocked || (series && chosen.length === 0)}
          >
            <Icon name="plus" size={16} />
            {t("media:discover.ask")}
          </Button>
        )
      }
    >
      {submit.isSuccess ? (
        <p className="request-dialog__done" role="status">
          <Icon name="check" size={18} />
          {t("media:discover.asked")}
        </p>
      ) : (
        <form
          id={formId}
          className="request-dialog"
          onSubmit={(event) => {
            event.preventDefault();
            send();
          }}
        >
          {series ? (
            <fieldset className="request-dialog__seasons">
              <legend>{t("media:discover.seasons")}</legend>
              <label className="request-dialog__all">
                <input
                  type="checkbox"
                  checked={chosen.length === missing.length && missing.length > 0}
                  onChange={(e) => setChosen(e.target.checked ? missing : [])}
                  disabled={!missing.length}
                />
                {t("media:discover.allSeasons")}
              </label>
              <ul>
                {(target.seasons ?? []).map((season) => (
                  <li key={season.number} data-status={season.status}>
                    <label>
                      <input
                        type="checkbox"
                        checked={chosen.includes(season.number)}
                        disabled={!askable(season)}
                        onChange={() => toggle(season.number)}
                      />
                      <span>{season.name ?? t("media:discover.season", { number: season.number })}</span>
                      {season.episodes ? (
                        <small>{t("media:discover.episodes", { count: season.episodes })}</small>
                      ) : null}
                      {!askable(season) ? (
                        <span className="request-dialog__state">
                          {t(`media:discover.status.${season.status}`)}
                        </span>
                      ) : null}
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
          ) : null}
          {target.four_k ? (
            <label className="request-dialog__4k">
              <input type="checkbox" checked={is4k} onChange={(e) => setIs4k(e.target.checked)} />
              {t("media:discover.in4k")}
            </label>
          ) : null}
          <QuotaLine kind={target.kind} />
          {error ? (
            <p className="request-dialog__error" role="alert">
              {error.code === "media.request_duplicate"
                ? t("media:discover.duplicate")
                : error.code === "media.request_quota_exceeded"
                  ? t("media:requests.quotaExceeded")
                  : error.code === "media.request_refused"
                    ? t("media:discover.refused")
                    : t("media:requests.failed")}
            </p>
          ) : null}
        </form>
      )}
    </Dialog>
  );
}
