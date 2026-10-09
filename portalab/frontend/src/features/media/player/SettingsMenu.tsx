import { type ReactNode, useEffect, useRef, useState } from "react";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { type PlayerInfo, type PlayerTrack, playerImage, type StreamStarted } from "./api";
import type { PlayerPrefs } from "./prefs";
import { bitrateLabel, clock, QUALITY_INFO, trackById } from "./quality";

/**
 * The player's settings (027, #2), as Plex's player offers them: quality, version, audio track, subtitles
 * (drawn or burnt in) and their size, audio boost — plus speed, chapters, next-episode autoplay and what
 * the server decided (direct stream or conversion). A main list, each entry opening its choices.
 */
type Panel =
  | "main"
  | "quality"
  | "version"
  | "audio"
  | "subtitles"
  | "size"
  | "boost"
  | "speed"
  | "chapters"
  | "info";

const SIZES = [75, 100, 125, 150, 200];
const BOOSTS = [100, 150, 200, 300];
const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2];

export interface SettingsMenuProps {
  info: PlayerInfo;
  stream: StreamStarted | null;
  versionIndex: number;
  quality: string;
  qualities: string[];
  audio: string | null;
  subtitle: string | null;
  prefs: PlayerPrefs;
  onVersion: (index: number) => void;
  onQuality: (key: string) => void;
  onAudio: (id: string) => void;
  onSubtitle: (id: string | null) => void;
  onPrefs: (patch: Partial<PlayerPrefs>) => void;
  onSeek: (to: number) => void;
  onClose: () => void;
}

function Choice({
  selected,
  onSelect,
  children,
  hint,
}: {
  selected: boolean;
  onSelect: () => void;
  children: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <li>
      <button type="button" className="player-choice" aria-pressed={selected} onClick={onSelect}>
        <Icon name={selected ? "check" : "minus"} size={16} />
        <span>{children}</span>
        {hint ? <small>{hint}</small> : null}
      </button>
    </li>
  );
}

export function SettingsMenu(props: SettingsMenuProps) {
  const t = useT();
  const { info, stream, prefs } = props;
  const item = info.item;
  const version = item.versions[props.versionIndex] ?? item.versions[0];
  const [panel, setPanel] = useState<Panel>("main");
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.querySelector<HTMLButtonElement>("button")?.focus();
  }, []);
  useEffect(() => {
    void panel;
    box.current?.querySelector<HTMLButtonElement>("button")?.focus();
  }, [panel]);

  const qualityLabel = (key: string) => {
    const cap = QUALITY_INFO[key];
    if (!cap) {
      const source = version?.bitrate_kbps ? ` · ${bitrateLabel(version.bitrate_kbps)}` : "";
      return `${t("media:player.quality.original")}${source}`;
    }
    return `${bitrateLabel(cap.kbps)} · ${cap.height}p`;
  };
  const trackLabel = (track: PlayerTrack | undefined) => track?.label ?? t("media:player.none");
  const subtitleLabel = (id: string | null) => {
    const track = trackById(version?.subtitles, id);
    if (!track) return t("media:player.none");
    return !track.text || prefs.burn ? `${track.label} · ${t("media:player.burnt")}` : track.label;
  };
  const decision = stream
    ? stream.video === "copy"
      ? t("media:player.info.direct")
      : t("media:player.info.transcode")
    : t("media:player.loading");

  const rows: { panel: Panel; label: string; value: string; show: boolean }[] = [
    {
      panel: "quality",
      label: t("media:player.quality.title"),
      value: qualityLabel(props.quality),
      show: true,
    },
    {
      panel: "version",
      label: t("media:player.version"),
      value: version?.label ?? "",
      show: item.versions.length > 1,
    },
    {
      panel: "audio",
      label: t("media:player.audio"),
      value: trackLabel(trackById(version?.audio, props.audio)),
      show: (version?.audio.length ?? 0) > 0,
    },
    {
      panel: "subtitles",
      label: t("media:player.subtitles"),
      value: subtitleLabel(props.subtitle),
      show: (version?.subtitles.length ?? 0) > 0,
    },
    {
      panel: "size",
      label: t("media:player.subtitleSize"),
      value: `${prefs.subtitleSize} %`,
      show: (version?.subtitles.length ?? 0) > 0,
    },
    {
      panel: "boost",
      label: t("media:player.boost.title"),
      value: t(`media:player.boost.${prefs.boost}`),
      show: true,
    },
    { panel: "speed", label: t("media:player.speed"), value: `${prefs.rate}×`, show: true },
    {
      panel: "chapters",
      label: t("media:player.chapters"),
      value: String(item.chapters.length),
      show: item.chapters.length > 1,
    },
    { panel: "info", label: t("media:player.info.title"), value: decision, show: true },
  ];

  const back = (
    <button type="button" className="player-menu-back" onClick={() => setPanel("main")}>
      <Icon name="chevron-left" size={18} />
      {rows.find((r) => r.panel === panel)?.label}
    </button>
  );
  const pick = (action: () => void) => () => {
    action();
    setPanel("main");
  };

  return (
    <div
      ref={box}
      className="player-menu"
      role="dialog"
      aria-label={t("media:player.settings")}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          if (panel === "main") props.onClose();
          else setPanel("main");
        }
      }}
    >
      {panel === "main" ? (
        <ul>
          {rows
            .filter((r) => r.show)
            .map((row) => (
              <li key={row.panel}>
                <button type="button" className="player-row" onClick={() => setPanel(row.panel)}>
                  <span>{row.label}</span>
                  <small>{row.value}</small>
                  <Icon name="chevron-right" size={16} />
                </button>
              </li>
            ))}
          {item.next_id ? (
            <li>
              <label className="player-row">
                <span>{t("media:player.autoplayNext")}</span>
                <input
                  type="checkbox"
                  checked={prefs.autoplayNext}
                  onChange={(event) => props.onPrefs({ autoplayNext: event.target.checked })}
                />
              </label>
            </li>
          ) : null}
        </ul>
      ) : null}

      {panel === "quality" ? (
        <>
          {back}
          <ul>
            {props.qualities.map((key) => (
              <Choice key={key} selected={key === props.quality} onSelect={pick(() => props.onQuality(key))}>
                {qualityLabel(key)}
              </Choice>
            ))}
          </ul>
          <p className="player-menu-note">{t("media:player.quality.note")}</p>
        </>
      ) : null}

      {panel === "version" ? (
        <>
          {back}
          <ul>
            {item.versions.map((v) => (
              <Choice
                key={v.index}
                selected={v.index === props.versionIndex}
                onSelect={pick(() => props.onVersion(v.index))}
                hint={v.bitrate_kbps ? bitrateLabel(v.bitrate_kbps) : undefined}
              >
                {v.label}
              </Choice>
            ))}
          </ul>
        </>
      ) : null}

      {panel === "audio" ? (
        <>
          {back}
          <ul>
            {(version?.audio ?? []).map((track) => (
              <Choice
                key={track.id}
                selected={track.id === props.audio}
                onSelect={pick(() => props.onAudio(track.id))}
              >
                {track.label}
              </Choice>
            ))}
          </ul>
        </>
      ) : null}

      {panel === "subtitles" ? (
        <>
          {back}
          <ul>
            <Choice selected={props.subtitle === null} onSelect={pick(() => props.onSubtitle(null))}>
              {t("media:player.none")}
            </Choice>
            {(version?.subtitles ?? []).map((track) => (
              <Choice
                key={track.id}
                selected={track.id === props.subtitle}
                onSelect={pick(() => props.onSubtitle(track.id))}
                hint={
                  !track.text ? t("media:player.burnt") : track.forced ? t("media:player.forced") : undefined
                }
              >
                {track.label}
              </Choice>
            ))}
          </ul>
          <label className="player-row">
            <span>{t("media:player.burn")}</span>
            <input
              type="checkbox"
              checked={prefs.burn}
              onChange={(event) => props.onPrefs({ burn: event.target.checked })}
            />
          </label>
          <p className="player-menu-note">{t("media:player.burnNote")}</p>
        </>
      ) : null}

      {panel === "size" ? (
        <>
          {back}
          <ul>
            {SIZES.map((size) => (
              <Choice
                key={size}
                selected={prefs.subtitleSize === size}
                onSelect={pick(() => props.onPrefs({ subtitleSize: size }))}
              >
                {t(`media:player.size.${size}`)}
              </Choice>
            ))}
          </ul>
        </>
      ) : null}

      {panel === "boost" ? (
        <>
          {back}
          <ul>
            {BOOSTS.map((boost) => (
              <Choice
                key={boost}
                selected={prefs.boost === boost}
                onSelect={pick(() => props.onPrefs({ boost }))}
              >
                {t(`media:player.boost.${boost}`)}
              </Choice>
            ))}
          </ul>
        </>
      ) : null}

      {panel === "speed" ? (
        <>
          {back}
          <ul>
            {SPEEDS.map((rate) => (
              <Choice
                key={rate}
                selected={prefs.rate === rate}
                onSelect={pick(() => props.onPrefs({ rate }))}
              >
                {rate === 1 ? t("media:player.normalSpeed") : `${rate}×`}
              </Choice>
            ))}
          </ul>
        </>
      ) : null}

      {panel === "chapters" ? (
        <>
          {back}
          <ul>
            {item.chapters.map((chapter, index) => (
              <Choice
                key={chapter.start_s}
                selected={false}
                onSelect={pick(() => props.onSeek(chapter.start_s))}
                hint={clock(chapter.start_s)}
              >
                {chapter.image && stream ? (
                  <img
                    className="player-chapter-thumb"
                    src={playerImage(stream.ticket, chapter.image)}
                    alt=""
                    loading="lazy"
                  />
                ) : null}
                {chapter.label ?? t("media:player.chapter", { number: index + 1 })}
              </Choice>
            ))}
          </ul>
        </>
      ) : null}

      {panel === "info" ? (
        <>
          {back}
          <dl className="player-info">
            <dt>{t("media:player.info.server")}</dt>
            <dd>
              {info.service_name ?? "—"}
              {info.linked ? "" : ` · ${t("media:player.info.sharedAccount")}`}
            </dd>
            <dt>{t("media:player.info.video")}</dt>
            <dd>
              {stream
                ? `${stream.video === "copy" ? t("media:player.info.direct") : t("media:player.info.transcode")}${
                    stream.height ? ` · ${stream.height}p` : ""
                  }${stream.video_codec ? ` · ${stream.video_codec.toUpperCase()}` : ""}`
                : "—"}
            </dd>
            <dt>{t("media:player.info.audio")}</dt>
            <dd>
              {stream
                ? `${stream.audio === "copy" ? t("media:player.info.copied") : t("media:player.info.converted")}${
                    stream.audio_codec ? ` · ${stream.audio_codec.toUpperCase()}` : ""
                  }`
                : "—"}
            </dd>
            <dt>{t("media:player.info.bitrate")}</dt>
            <dd>{stream?.bitrate_kbps ? bitrateLabel(stream.bitrate_kbps) : "—"}</dd>
            <dt>{t("media:player.info.file")}</dt>
            <dd>{version?.label ?? "—"}</dd>
          </dl>
        </>
      ) : null}
    </div>
  );
}
