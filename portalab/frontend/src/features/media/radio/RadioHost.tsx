import { Link, useLocation } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { useT } from "../../../i18n/hooks/useT";
import { useRadio } from "./api";
import { stopRadio, useRadioPlayback } from "./store";
import "./radio.css";

/**
 * Issue 168: the radio keeps playing while browsing — a small pill in the corner says what plays and stops
 * it (not on the pages that already show the radio). Mounted once by the shell.
 */
export function RadioHost() {
  const t = useT();
  const location = useLocation();
  const playback = useRadioPlayback();
  const on = playback.playing || playback.loading;
  const radio = useRadio(on);
  if (!on || location.pathname === "/" || location.pathname.startsWith("/media/radio")) return null;
  const current = radio.data?.current;
  return (
    <section className="radio-pill" aria-label={t("media:radio.title")}>
      <Icon name="radio" size={14} />
      <Link to="/media/radio" className="radio-pill__text">
        {current
          ? `${current.title}${current.artist ? ` — ${current.artist}` : ""}`
          : (radio.data?.station ?? t("media:radio.title"))}
      </Link>
      <button
        type="button"
        onClick={stopRadio}
        aria-label={t("media:radio.stop")}
        title={t("media:radio.stop")}
      >
        <Icon name="pause" size={14} />
      </button>
    </section>
  );
}
