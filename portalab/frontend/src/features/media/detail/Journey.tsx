import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId } from "react";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";

interface Torrent {
  state: string;
  progress: number;
  speed: number;
  eta_s: number | null;
  seeds: number | null;
  peers: number | null;
}
interface DownloadItem {
  title: string;
  season: number | null;
  episode: number | null;
  status: string;
  progress: number;
  eta: string | null;
  client: string | null;
  release: string | null;
  attention: string | null;
  messages: string[];
  size: number | null;
  torrent: Torrent | null;
}
interface Step {
  key: string;
  status: "done" | "current" | "waiting" | "blocked" | "failed" | "upcoming";
  at?: string;
  detail?: string;
  by?: { me: boolean; name?: string | null };
  cinema?: string;
  digital?: string;
  physical?: string;
  first_aired?: string;
  next_airing?: string;
  manager?: string;
  progress?: number;
  items?: DownloadItem[];
  files?: number;
  expected?: number;
  quality?: string;
  size?: number;
  last_failure?: { at: string; detail?: string | null; release?: string | null };
}
interface Release {
  title: string;
  indexer: string | null;
  size: number | null;
  quality: string | null;
  seeders: number | null;
  approved: boolean;
  rejections: string[];
}
interface Journey {
  kind: string;
  available: boolean;
  request: { state: string; requested_at: string } | null;
  manager: { name: string; link: string | null; status: string | null } | null;
  steps: Step[];
  can_search: boolean;
  search: { at: string | null; releases: Release[] } | null;
}

const ICONS: Record<string, string> = {
  requested: "inbox",
  approved: "check",
  released: "clapperboard",
  searched: "search",
  downloading: "package",
  imported: "library",
  available: "play",
};

function size(bytes: number | null | undefined): string {
  if (!bytes) return "";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function useJourney(objectId: string) {
  return useQuery({
    queryKey: ["media", "journey", objectId],
    queryFn: async () =>
      (await api.GET("/api/v1/media/{object_id}/journey", { params: { path: { object_id: objectId } } }))
        .data as unknown as Journey,
    refetchInterval: (query) =>
      (query.state.data as Journey | undefined)?.steps?.some(
        (s) => s.key === "downloading" && s.status === "current",
      )
        ? 15_000
        : false,
  });
}

/** One transfer: the manager's view (progress, release, client) and the torrent's (state, speed, peers). */
function Transfer({ item }: { item: DownloadItem }) {
  const t = useT();
  const format = useFormat();
  const percent = Math.round((item.torrent?.progress ?? item.progress) * 100);
  const label =
    item.season !== null && item.episode !== null
      ? `S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")} · ${item.title}`
      : item.title;
  return (
    <li className="journey-transfer" data-state={item.torrent?.state ?? item.status}>
      <span className="journey-transfer__head">
        <strong>{label}</strong>
        <span>{percent} %</span>
      </span>
      <span
        className="journey-transfer__bar"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <span style={{ inlineSize: `${percent}%` }} />
      </span>
      <span className="journey-transfer__facts">
        {item.torrent ? <span>{t(`media:journey.torrent.${item.torrent.state}`)}</span> : null}
        {item.torrent && item.torrent.speed ? <span>{size(item.torrent.speed)}/s</span> : null}
        {item.torrent && item.torrent.peers !== null ? (
          <span>
            {t("media:journey.peers", { seeds: item.torrent.seeds ?? 0, peers: item.torrent.peers })}
          </span>
        ) : null}
        {item.eta ? (
          <span>
            {t("media:journey.eta", { when: format.relative((Date.parse(item.eta) - Date.now()) / 1000) })}
          </span>
        ) : null}
        {item.client ? <span>{item.client}</span> : null}
        {item.size ? <span>{size(item.size)}</span> : null}
      </span>
      {item.release ? <span className="journey-transfer__release">{item.release}</span> : null}
      {item.messages.length ? (
        <ul className="journey-messages">
          {item.messages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function StepText({ step }: { step: Step }) {
  const t = useT();
  const format = useFormat();
  const date = (iso?: string) => (iso ? format.date(iso, "medium") : "");
  switch (step.key) {
    case "requested":
      return (
        <>
          {step.by?.me
            ? t("media:journey.requestedByMe")
            : step.by?.name
              ? t("media:journey.requestedBy", { name: step.by.name })
              : t("media:journey.requestedBySomeone")}
          {step.at ? ` · ${date(step.at)}` : ""}
        </>
      );
    case "approved":
      return <>{t(`media:journey.approved.${step.detail ?? step.status}`)}</>;
    case "released": {
      const facts = [
        step.cinema ? t("media:journey.cinema", { date: date(step.cinema) }) : null,
        step.digital ? t("media:journey.digital", { date: date(step.digital) }) : null,
        step.physical ? t("media:journey.physical", { date: date(step.physical) }) : null,
        step.first_aired ? t("media:journey.firstAired", { date: date(step.first_aired) }) : null,
        step.next_airing ? t("media:journey.nextAiring", { date: date(step.next_airing) }) : null,
      ].filter(Boolean);
      return (
        <>
          {t(`media:journey.released.${step.detail ?? step.status}`)}
          {facts.length ? <span className="journey-step__facts">{facts.join(" · ")}</span> : null}
        </>
      );
    }
    case "searched":
      return (
        <>
          {t(`media:journey.searched.${step.detail ?? step.status}`, { manager: step.manager ?? "" })}
          {step.last_failure ? (
            <span className="journey-step__facts">
              {t("media:journey.lastFailure", { date: date(step.last_failure.at) })}
              {step.last_failure.detail ? ` · ${step.last_failure.detail}` : ""}
            </span>
          ) : null}
        </>
      );
    case "downloading":
      return (
        <>
          {step.status === "current" || step.status === "blocked"
            ? t("media:journey.downloading.now", { percent: Math.round((step.progress ?? 0) * 100) })
            : t(`media:journey.downloading.${step.status}`)}
          {step.at ? ` · ${date(step.at)}` : ""}
        </>
      );
    case "imported":
      return <>{t(`media:journey.imported.${step.detail ?? step.status}`)}</>;
    case "available":
      return (
        <>
          {step.status === "done"
            ? t("media:journey.available.done", { date: date(step.at) })
            : t("media:journey.available.upcoming")}
          {step.quality || step.size || (step.expected && step.files !== undefined) ? (
            <span className="journey-step__facts">
              {[
                step.expected
                  ? t("media:journey.episodes", { files: step.files ?? 0, expected: step.expected })
                  : null,
                step.quality,
                step.size ? size(step.size) : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          ) : null}
        </>
      );
    default:
      return null;
  }
}

/**
 * A title's request journey (027): a horizontal timeline from the request to the library — each step
 * done, in progress, waiting, blocked (someone must act) or failed, with what explains it: release dates,
 * what the download manager says, the transfers (torrent state, speed, peers, time left), a manual import
 * to confirm, errors; and, on demand, what the indexers offer.
 */
export function RequestJourney({ objectId }: { objectId: string }) {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const client = useQueryClient();
  const journey = useJourney(objectId);
  const search = useMutation({
    mutationFn: async () =>
      (
        await api.POST("/api/v1/media/{object_id}/journey/search", {
          params: { path: { object_id: objectId } },
        })
      ).data as unknown as { at: string | null; releases: Release[] },
    onSuccess: () => client.invalidateQueries({ queryKey: ["media", "journey", objectId] }),
  });
  const data = journey.data;
  if (!data || !Array.isArray(data.steps) || !data.steps.length) return null;
  const releases = search.data?.releases ?? data.search?.releases ?? null;
  const active = data.steps.find((s) => ["current", "blocked", "failed", "waiting"].includes(s.status));
  const transfers = data.steps.flatMap((s) =>
    s.key === "downloading" || s.key === "imported" ? (s.items ?? []) : [],
  );
  return (
    <section className="media-journey" aria-labelledby={headingId}>
      <header className="media-journey__head">
        <h3 id={headingId}>
          <Icon name="activity" size={18} /> {t("media:journey.title")}
        </h3>
        {data.manager?.link ? (
          <a
            className="ds-button ds-button--ghost"
            href={data.manager.link}
            target="_blank"
            rel="noopener noreferrer external"
          >
            {t("media:journey.openIn", { manager: data.manager.name })} <Icon name="link" size={14} />
          </a>
        ) : null}
      </header>
      <ol className="journey-steps">
        {data.steps.map((step) => (
          <li key={step.key} className="journey-step" data-status={step.status}>
            <span className="journey-step__dot" aria-hidden="true">
              <Icon
                name={
                  step.status === "failed"
                    ? "close"
                    : step.status === "blocked"
                      ? "alert"
                      : step.status === "waiting"
                        ? "hourglass"
                        : (ICONS[step.key] ?? "check")
                }
                size={14}
              />
            </span>
            <span className="journey-step__name">{t(`media:journey.step.${step.key}`)}</span>
            <span className="visually-hidden">{t(`media:journey.status.${step.status}`)}</span>
          </li>
        ))}
      </ol>
      {active ? (
        <div className="journey-now" data-status={active.status}>
          <strong>{t(`media:journey.step.${active.key}`)}</strong>
          <p>
            <StepText step={active} />
          </p>
        </div>
      ) : null}
      {transfers.length ? (
        <ul className="journey-transfers" aria-label={t("media:journey.transfers")}>
          {transfers.map((item) => (
            <Transfer
              key={`${item.title}-${item.season ?? ""}-${item.episode ?? ""}-${item.release ?? ""}`}
              item={item}
            />
          ))}
        </ul>
      ) : null}
      <details className="journey-details">
        <summary>{t("media:journey.details")}</summary>
        <ul className="journey-list">
          {data.steps.map((step) => (
            <li key={step.key} data-status={step.status}>
              <strong>{t(`media:journey.step.${step.key}`)}</strong> — <StepText step={step} />
            </li>
          ))}
        </ul>
      </details>
      {data.can_search ? (
        <div className="journey-search">
          <Button variant="secondary" disabled={search.isPending} onClick={() => search.mutate()}>
            <Icon name={search.isPending ? "spinner" : "search"} size={16} />
            {search.isPending ? t("media:journey.searching") : t("media:journey.search")}
          </Button>
          <span className="admin-muted">{t("media:journey.searchHint")}</span>
          {releases ? (
            releases.length ? (
              <table className="admin-table journey-releases">
                <caption className="visually-hidden">{t("media:journey.results")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("media:journey.release")}</th>
                    <th scope="col">{t("media:journey.quality")}</th>
                    <th scope="col" data-align="end">
                      {t("media:journey.seeders")}
                    </th>
                    <th scope="col">{t("media:journey.verdict")}</th>
                  </tr>
                </thead>
                <tbody>
                  {releases.map((r) => (
                    <tr key={`${r.title}-${r.indexer ?? ""}`} data-approved={r.approved || undefined}>
                      <td>
                        {r.title}
                        <span className="admin-muted">
                          {" "}
                          {[r.indexer, size(r.size)].filter(Boolean).join(" · ")}
                        </span>
                      </td>
                      <td>{r.quality ?? "—"}</td>
                      <td data-align="end">{r.seeders ?? "—"}</td>
                      <td>
                        {r.approved
                          ? t("media:journey.accepted")
                          : r.rejections.join(" · ") || t("media:journey.rejected")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="journey-now" data-status="waiting">
                {t("media:journey.noResults")}
              </p>
            )
          ) : null}
          {search.data?.at || data.search?.at ? (
            <span className="admin-muted">
              {t("media:journey.searchedAt", {
                when: format.dateTime(String(search.data?.at ?? data.search?.at)),
              })}
            </span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
