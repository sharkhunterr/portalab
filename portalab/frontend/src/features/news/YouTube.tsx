import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import "./youtube.css";

const ID = /^[\w-]{11}$/;

/** issue 315: a YouTube video's id from its address (a watch page, a short link, a short, a live, an embed),
 * else null. */
export function youtubeId(link: string | null | undefined): string | null {
  if (!link) return null;
  try {
    const url = new URL(link);
    const host = url.hostname.replace(/^(www|m|music)\./, "");
    let id: string | null | undefined = null;
    if (host === "youtu.be") id = url.pathname.split("/")[1];
    else if (host === "youtube.com" || host === "youtube-nocookie.com")
      id =
        url.pathname === "/watch"
          ? url.searchParams.get("v")
          : /^\/(?:shorts|live|embed|v)\/([^/]+)/.exec(url.pathname)?.[1];
    return id && ID.test(id) ? id : null;
  } catch {
    return null;
  }
}

/** issue 315: YouTube refuses to play in a page reached by an IP address (« video unavailable »), or with no
 * referrer at all (error 153): there, a video opens on YouTube instead. Any host name will do. */
export function embeddable(host: string = window.location.hostname): boolean {
  return !/^(\d{1,3}(\.\d{1,3}){3}|\[[\da-f:]+\]|[\da-f]*:[\da-f:]+)$/i.test(host);
}

/**
 * issue 315: a YouTube video played in place — YouTube's privacy-enhanced player (no cookie before playing),
 * only once the member asked for it (nothing is loaded from YouTube before). It is confined: no navigation of
 * the page, its own links open apart. YouTube needs to know which site embeds it: this frame sends the
 * portal's origin, never the page's address.
 */
export function YouTubePlayer({ id, title }: { id: string; title: string }) {
  return (
    <div className="youtube-player">
      <iframe
        src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&playsinline=1`}
        title={title}
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
        referrerPolicy="strict-origin"
        sandbox="allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox"
      />
    </div>
  );
}

/** issue 315: a video's picture as its play button (pressed while it plays) — or, where YouTube would not
 * play it here, its way to YouTube. */
export function PlayCover({
  picture,
  title,
  link,
  playing,
  onToggle,
  className,
}: {
  picture: string | null | undefined;
  title: string;
  link: string;
  playing: boolean;
  onToggle: () => void;
  className?: string;
}) {
  const t = useT();
  if (!embeddable())
    return (
      <a
        href={link}
        target="_blank"
        rel="noopener noreferrer"
        className={`youtube-cover ${className ?? ""}`}
        aria-label={t("news:video.onYouTube", { title })}
      >
        {/* the picture alone: an icon over it would hide it (one only when there is no picture) */}
        {picture ? <img src={picture} alt="" loading="lazy" /> : <Icon name="external" size={18} />}
      </a>
    );
  return (
    <button
      type="button"
      className={`youtube-cover ${className ?? ""}`}
      aria-pressed={playing}
      aria-label={t(playing ? "news:video.close" : "news:video.play", { title })}
      onClick={onToggle}
    >
      {picture ? <img src={picture} alt="" loading="lazy" /> : null}
      <span className="youtube-cover__button" aria-hidden="true">
        <Icon name={playing ? "close" : "play"} size={18} />
      </span>
    </button>
  );
}
