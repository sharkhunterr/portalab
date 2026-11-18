import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, type PointerEvent, useId, useRef, useState } from "react";
import { Link } from "react-router";
import { api } from "../../../api/client";
import type { components } from "../../../api/generated/schema";
import { Icon } from "../../../design-system/components/Icon";
import { Dialog } from "../../../design-system/components/Overlays";
import { useT } from "../../../i18n/hooks/useT";
import { embeddable, YouTubePlayer } from "../../news/YouTube";
import "./extras.css";

export type MediaExtras = components["schemas"]["MediaExtrasOut"];
export type ExtraVideo = components["schemas"]["ExtraVideoOut"];
export type ExtraImage = components["schemas"]["ExtraImageOut"];

const SWIPE_PX = 48; // a swipe this long turns the picture

/** Issue 465: a title's videos and extra pictures, as the services that know them tell them. */
export function useExtras(objectId: string, enabled = true) {
  return useQuery({
    queryKey: ["media", objectId, "extras"],
    enabled,
    retry: false,
    staleTime: 30 * 60_000,
    queryFn: async (): Promise<MediaExtras> => {
      const { data } = await api.GET("/api/v1/media/{object_id}/extras", {
        params: { path: { object_id: objectId } },
      });
      return data ?? { videos: [], images: [] };
    },
  });
}

/**
 * Issue 465: on a title's page, its videos (trailers first, then featurettes, behind the scenes… a game's
 * gameplay) and its pictures (backdrops, stills, screenshots, artworks), when a service knows some.
 */
export function Extras({ objectId, title }: { objectId: string; title: string }) {
  return <ExtrasView extras={useExtras(objectId).data} title={title} />;
}

/** Issue 501: a game the library lacks — its videos and pictures by its id in the game database. */
export function GameExtras({ gameRef, title }: { gameRef: string; title: string }) {
  const extras = useQuery({
    queryKey: ["media", "game-extras", gameRef],
    retry: false,
    staleTime: 30 * 60_000,
    queryFn: async (): Promise<MediaExtras> => {
      const { data } = await api.GET("/api/v1/media/game-extras", { params: { query: { ref: gameRef } } });
      return data ?? { videos: [], images: [] };
    },
  });
  return <ExtrasView extras={extras.data} title={title} />;
}

function ExtrasView({ extras, title }: { extras: MediaExtras | undefined; title: string }) {
  if (!extras || (!extras.videos?.length && !extras.images?.length)) return null;
  return (
    <>
      {extras.videos?.length ? <Videos videos={extras.videos} title={title} /> : null}
      {extras.images?.length ? <Pictures images={extras.images} title={title} /> : null}
    </>
  );
}

/** A video's length as « 2:05 » (« 1:02:05 » past an hour). */
export function clock(seconds: number): string {
  const total = Math.round(seconds);
  const [h, m, s] = [Math.floor(total / 3600), Math.floor((total % 3600) / 60), total % 60];
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function kindsOf(videos: ExtraVideo[]): string[] {
  return [...new Set(videos.map((v) => v.kind))];
}

/** The videos in one scrolling row — by kind (« All », « Trailers »…) when there are several kinds. */
function Videos({ videos, title }: { videos: ExtraVideo[]; title: string }) {
  const t = useT();
  const headingId = useId();
  const [kind, setKind] = useState<string | null>(null);
  const [playing, setPlaying] = useState<ExtraVideo | null>(null);
  const kinds = kindsOf(videos);
  const shown = kind ? videos.filter((v) => v.kind === kind) : videos;
  return (
    <section aria-labelledby={headingId} className="media-row media-extras">
      <div className="media-row__head">
        <h3 id={headingId}>
          <Icon name="film" size={18} />
          {t("media:extras.videos")}
        </h3>
      </div>
      {kinds.length > 1 ? (
        <fieldset className="media-extras__kinds">
          <legend className="visually-hidden">{t("media:extras.kinds")}</legend>
          {[null, ...kinds].map((k) => (
            <button
              key={k ?? "all"}
              type="button"
              className="media-extras__kind"
              aria-pressed={kind === k}
              onClick={() => setKind(k)}
            >
              {k ? t(`media:extras.kind.${k}`) : t("media:extras.all")}
            </button>
          ))}
        </fieldset>
      ) : null}
      <ul className="media-extras__videos" aria-label={t("media:extras.videos")}>
        {shown.map((video) => (
          <li key={video.index}>
            <VideoCard video={video} onPlay={() => setPlaying(video)} />
          </li>
        ))}
      </ul>
      {playing?.youtube ? (
        <Dialog
          trigger={null}
          open
          onOpenChange={(open) => (open ? null : setPlaying(null))}
          title={playing.name || t(`media:extras.kind.${playing.kind}`)}
          description={title}
          closeLabel={t("media:extras.close")}
          size="lg"
        >
          <YouTubePlayer id={playing.youtube} title={playing.name || title} />
        </Dialog>
      ) : null}
    </section>
  );
}

/** One video: its picture, its kind, its name — played here (a media server's, YouTube's where the address
 * lets YouTube play), else opened on YouTube. */
function VideoCard({ video, onPlay }: { video: ExtraVideo; onPlay: () => void }) {
  const t = useT();
  const [broken, setBroken] = useState(false); // a picture the service no longer has: the icon instead
  const label = video.name || t(`media:extras.kind.${video.kind}`);
  const facts = [
    t(`media:extras.kind.${video.kind}`),
    video.language ? video.language.toUpperCase() : null,
    video.duration_s ? clock(video.duration_s) : null,
  ].filter(Boolean);
  const body = (
    <>
      <span className="media-extras__picture">
        {video.picture && !broken ? (
          <img src={video.picture} alt="" loading="lazy" onError={() => setBroken(true)} />
        ) : (
          <Icon name="film" size={28} />
        )}
        <span className="media-extras__play" aria-hidden="true">
          <Icon name={video.site === "youtube" && !embeddable() ? "external" : "play"} size={18} />
        </span>
      </span>
      <span className="media-extras__name">{label}</span>
      <span className="media-extras__facts">{facts.join(" · ")}</span>
    </>
  );
  if (video.play)
    return (
      <Link
        className="media-extras__video"
        to={video.play}
        aria-label={t("media:extras.play", { name: label })}
      >
        {body}
      </Link>
    );
  if (video.youtube && !embeddable())
    return (
      <a
        className="media-extras__video"
        href={`https://www.youtube.com/watch?v=${video.youtube}`}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={t("media:extras.onYouTube", { name: label })}
      >
        {body}
      </a>
    );
  return (
    <button
      type="button"
      className="media-extras__video"
      onClick={onPlay}
      aria-label={t("media:extras.play", { name: label })}
    >
      {body}
    </button>
  );
}

/** The pictures as a grid of small ones — each opening the viewer. */
function Pictures({ images, title }: { images: ExtraImage[]; title: string }) {
  const t = useT();
  const headingId = useId();
  const [open, setOpen] = useState<number | null>(null);
  const thumbs = useRef<(HTMLButtonElement | null)[]>([]);
  const close = () => {
    const last = open;
    setOpen(null);
    // the focus back on the picture last shown (the viewer gone at once, it cannot give it back itself)
    requestAnimationFrame(() => (last === null ? null : thumbs.current[last]?.focus()));
  };
  return (
    <section aria-labelledby={headingId} className="media-row media-extras">
      <div className="media-row__head">
        <h3 id={headingId}>
          <Icon name="image" size={18} />
          {t("media:extras.images")}
        </h3>
      </div>
      <ul className="media-extras__images" aria-label={t("media:extras.images")}>
        {images.map((image, at) => (
          <li key={image.index}>
            <button
              ref={(button) => {
                thumbs.current[at] = button;
              }}
              type="button"
              className="media-extras__image"
              onClick={() => setOpen(at)}
              aria-label={t("media:extras.open", { index: at + 1, total: images.length })}
            >
              <img src={image.preview} alt="" loading="lazy" />
            </button>
          </li>
        ))}
      </ul>
      {open !== null ? (
        <Viewer images={images} at={open} onMove={setOpen} onClose={close} title={title} />
      ) : null}
    </section>
  );
}

/**
 * The viewer: one picture over the whole screen — « Previous » and « Next », the arrow keys, a swipe on a
 * phone; Escape or « Close » leaves it, the focus going back to the picture opened.
 */
export function Viewer({
  images,
  at,
  onMove,
  onClose,
  title,
}: {
  images: ExtraImage[];
  at: number;
  onMove: (at: number) => void;
  onClose: () => void;
  title: string;
}) {
  const t = useT();
  const start = useRef<number | null>(null);
  const count = images.length;
  const move = (step: number) => onMove((at + step + count) % count);
  const image = images[at];
  if (!image) return null;
  const keys = (event: KeyboardEvent) => {
    if (event.key === "ArrowRight") move(1);
    else if (event.key === "ArrowLeft") move(-1);
    else return;
    event.preventDefault();
  };
  const down = (event: PointerEvent) => {
    start.current = event.clientX;
  };
  const up = (event: PointerEvent) => {
    if (start.current === null) return;
    const delta = event.clientX - start.current;
    start.current = null;
    if (Math.abs(delta) >= SWIPE_PX) move(delta < 0 ? 1 : -1);
  };
  return (
    <DialogPrimitive.Root open onOpenChange={(open) => (open ? null : onClose())}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="extras-viewer__overlay" />
        <DialogPrimitive.Content
          className="extras-viewer"
          onKeyDown={keys}
          aria-describedby={undefined} // the count below is read as it changes
          data-protected=""
        >
          <DialogPrimitive.Title className="visually-hidden">
            {t("media:extras.viewer", { title })}
          </DialogPrimitive.Title>
          <figure className="extras-viewer__stage" onPointerDown={down} onPointerUp={up}>
            <img key={image.index} src={image.full} alt="" draggable={false} />
          </figure>
          <p className="extras-viewer__count" aria-live="polite">
            {t("media:extras.position", { index: at + 1, total: count })}
          </p>
          {count > 1 ? (
            <>
              <button
                type="button"
                className="extras-viewer__button"
                data-side="start"
                onClick={() => move(-1)}
                aria-label={t("media:extras.previous")}
              >
                <Icon name="chevron-left" size={26} />
              </button>
              <button
                type="button"
                className="extras-viewer__button"
                data-side="end"
                onClick={() => move(1)}
                aria-label={t("media:extras.next")}
              >
                <Icon name="chevron-right" size={26} />
              </button>
            </>
          ) : null}
          <DialogPrimitive.Close
            className="extras-viewer__button"
            data-side="close"
            aria-label={t("media:extras.close")}
          >
            <Icon name="close" size={22} />
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
