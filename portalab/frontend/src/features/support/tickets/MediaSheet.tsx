import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../../api/client";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { formatBytes } from "../../admin/ControlCenter";
import { useMeasures } from "../../media/insights/api";

/**
 * Issue 354: the team's technical sheet of the media a ticket is about — asked of the services when opened:
 * each media server's files (path, size, container, length, bitrate) and their streams (the video, the
 * audio tracks, the subtitles), and the download manager's side (the release grabbed, its indexer, the
 * client and the torrent's hash, the quality and size).
 */
interface Stream {
  kind: "video" | "audio" | "subtitle";
  codec: string | null;
  language: string | null;
  title: string | null;
  channels: string | null;
  resolution: string | null;
  dynamic_range: string | null;
  bitrate: number | null;
  forced: boolean;
  default: boolean;
}
interface SheetFile {
  path: string | null;
  size: number | null;
  container: string | null;
  duration_s: number | null;
  bitrate: number | null;
  streams: Stream[];
}
interface Sheet {
  servers: Array<{ service: string; added_at: string | null; files: SheetFile[] }>;
  acquisition: {
    service: string;
    added_at: string | null;
    quality: string | null;
    size: number | null;
    files: number;
    expected: number;
    link: string | null;
    events: Array<{
      event: string;
      at: string;
      release: string | null;
      indexer: string | null;
      client: string | null;
      download_id: string | null;
    }>;
  } | null;
}

const KINDS = ["video", "audio", "subtitle"] as const;

function streamText(stream: Stream): string {
  const parts =
    stream.kind === "video"
      ? [stream.resolution, stream.codec?.toUpperCase(), stream.dynamic_range]
      : [stream.language, stream.codec?.toUpperCase(), stream.channels];
  const own = parts.filter(Boolean).join(" · ");
  return stream.title && !own.includes(stream.title)
    ? `${stream.title}${own ? ` — ${own}` : ""}`
    : own || "—";
}

function FileBlock({ file }: { file: SheetFile }) {
  const t = useT();
  const { locale } = useLocaleContext();
  const measures = useMeasures();
  const facts = [
    file.size ? formatBytes(file.size, locale) : null,
    file.container?.toUpperCase(),
    file.duration_s ? measures.duration(file.duration_s) : null,
    file.bitrate ? t("support:sheet.bitrate", { rate: Math.round(file.bitrate / 100) / 10 }) : null,
  ].filter(Boolean);
  return (
    <div className="media-sheet__file">
      {file.path ? <code className="media-sheet__path">{file.path}</code> : null}
      {facts.length ? <p className="media-sheet__facts">{facts.join(" · ")}</p> : null}
      <dl className="media-sheet__streams">
        {KINDS.map((kind) => {
          const streams = file.streams.filter((s) => s.kind === kind);
          return streams.length ? (
            <div key={kind}>
              <dt>{t(`support:sheet.kind.${kind}`, { count: streams.length })}</dt>
              <dd>
                <ul>
                  {streams.map((stream, index) => (
                    // biome-ignore lint/suspicious/noArrayIndexKey: a file's streams in their own order
                    <li key={index}>
                      {streamText(stream)}
                      {stream.default ? <span className="ds-badge">{t("support:sheet.default")}</span> : null}
                      {stream.forced ? <span className="ds-badge">{t("support:sheet.forced")}</span> : null}
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
          ) : null;
        })}
      </dl>
    </div>
  );
}

function SheetBody({ ticketId }: { ticketId: string }) {
  const t = useT();
  const format = useFormat();
  const { locale } = useLocaleContext();
  const sheet = useQuery({
    queryKey: ["support", "media-sheet", ticketId],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/tickets/{ticket_id}/media-sheet", {
        params: { path: { ticket_id: ticketId } },
      });
      if (error) throw error;
      return data as unknown as Sheet;
    },
  });
  if (sheet.isPending) return <FunctionalState state="loading" />;
  if (sheet.isError || !sheet.data)
    return <FunctionalState state="unavailable" onRetry={() => sheet.refetch()} />;
  const { servers, acquisition } = sheet.data;
  if (!servers.length && !acquisition) return <p className="admin-muted">{t("support:sheet.nothing")}</p>;
  return (
    <div className="media-sheet__body">
      {servers.map((server) => (
        <section key={server.service} className="media-sheet__server">
          <h4>
            <Icon name="server" size={16} />
            {server.service}
            {server.added_at ? (
              <span className="media-sheet__when">
                {t("support:sheet.added", { date: format.dateTime(server.added_at) })}
              </span>
            ) : null}
          </h4>
          {server.files.length ? (
            server.files.map((file, index) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: a title's files in the server's order
              <FileBlock key={index} file={file} />
            ))
          ) : (
            <p className="admin-muted">{t("support:sheet.noFile")}</p>
          )}
        </section>
      ))}
      {acquisition ? (
        <section className="media-sheet__server">
          <h4>
            <Icon name="download" size={16} />
            {acquisition.service}
            {acquisition.added_at ? (
              <span className="media-sheet__when">
                {t("support:sheet.followed", { date: format.dateTime(acquisition.added_at) })}
              </span>
            ) : null}
          </h4>
          <p className="media-sheet__facts">
            {[
              acquisition.quality,
              acquisition.size ? formatBytes(acquisition.size, locale) : null,
              acquisition.expected > 1
                ? t("support:sheet.files", { files: acquisition.files, expected: acquisition.expected })
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
            {acquisition.link ? (
              <>
                {" · "}
                <a href={acquisition.link} target="_blank" rel="noreferrer">
                  {t("support:sheet.open", { service: acquisition.service })}
                </a>
              </>
            ) : null}
          </p>
          {acquisition.events.length ? (
            <ol className="media-sheet__events">
              {acquisition.events.map((event) => (
                <li key={`${event.event}-${event.at}`}>
                  <span className="media-sheet__event">
                    <b>{t(`support:sheet.event.${event.event}`)}</b>
                    <time dateTime={event.at}>{format.dateTime(event.at)}</time>
                  </span>
                  {event.release ? <code className="media-sheet__path">{event.release}</code> : null}
                  <span className="media-sheet__facts">
                    {[
                      event.indexer ? t("support:sheet.indexer", { name: event.indexer }) : null,
                      event.client ? t("support:sheet.client", { name: event.client }) : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                  {event.download_id ? (
                    <span className="media-sheet__facts">
                      {t("support:sheet.hash")} <code>{event.download_id}</code>
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

/** Folded at first: the services are asked only when the team opens it. */
export function MediaSheet({ ticketId }: { ticketId: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <details className="media-sheet" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>
        <Icon name="wrench" size={16} />
        {t("support:sheet.title")}
      </summary>
      {open ? <SheetBody ticketId={ticketId} /> : null}
    </details>
  );
}
