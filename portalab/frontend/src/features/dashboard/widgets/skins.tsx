import { type ComponentType, type CSSProperties, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { levelProgress } from "../../../design-system/components/Badges";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useLocaleContext } from "../../../i18n/provider/I18nProvider";
import { useProgression } from "../../gamification/api";
import { metadataImage } from "../../media/detail/Enrichment";
import { WidgetHeaderAction } from "../frame/actions";
import { TEMPLATES } from "../templates/Templates";
import { daysUntil } from "./layout";
import { useCountUp, useLively } from "./motion";
import { registerWidgetComponent, type WidgetProps, widgetComponent } from "./registry";
import "./skins.css";

/**
 * 027 (#31): the widgets' other looks. Each wraps the original component, which stays the « classic » look
 * (the default, always free); a member who bought a look in the shop picks it in the widget's settings
 * (``style``). Animations follow the motion budget (#29): only seen widgets move.
 */
type Card = {
  id?: string | null;
  title?: string;
  subtitle?: string | null;
  meta?: string | null;
  kind?: string;
  at?: string;
  route?: string | null;
  image_id?: string | null;
  poster_ref?: string | null;
};
type SkinProps = WidgetProps & { Original: ComponentType<WidgetProps> };

const art = (card: Card | undefined): string | null =>
  card?.image_id ? `/api/v1/media/images/${card.image_id}` : metadataImage(card?.poster_ref, "w342");
const itemsOf = (props: WidgetProps): Card[] =>
  ((props.payload.data ?? {}) as { items?: Card[] }).items ?? [];
const ISO = /^\d{4}-\d{2}-\d{2}(T|$)/;

// --- continue: « ambient » — the title's poster as a blurred light behind ----------------------------------
function Ambient({ Original, ...props }: SkinProps) {
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  const src = art(itemsOf(props).find((c) => c.image_id || c.poster_ref));
  return (
    <div
      ref={ref}
      className="skin skin-ambient"
      data-still={!lively || undefined}
      style={src ? ({ "--ambient-art": `url("${src}")` } as CSSProperties) : undefined}
    >
      <Original {...props} />
    </div>
  );
}

// --- services: « pulse » — a heartbeat per service, the light following the health ------------------------
function Pulse({ Original, ...props }: SkinProps) {
  return (
    <div className="skin skin-pulse">
      <Original {...props} />
    </div>
  );
}

// --- my progression: « odometer » — the ring filling up, the figures counting -----------------------------
function Odometer({ payload }: SkinProps) {
  const t = useT();
  const format = useFormat();
  const ref = useRef<HTMLAnchorElement>(null);
  const lively = useLively(ref);
  const data = (payload.data ?? {}) as { level?: number; xp?: number; contribution?: number; coins?: number };
  const progression = useProgression().data;
  const level = progression?.level ?? data.level ?? 1;
  const next = progression?.next_level_at ?? null;
  const ratio = progression ? levelProgress(progression.xp, progression.level_floor, next) : 0;
  const xp = useCountUp(data.xp ?? 0, lively);
  const coins = useCountUp(data.coins ?? 0, lively);
  const contribution = useCountUp(data.contribution ?? 0, lively);
  const shownLevel = useCountUp(level, lively, 900);
  const shownRatio = useCountUp(ratio, lively, 1400); // the ring fills up
  return (
    <Link
      ref={ref}
      to="/progression"
      className="widget-level skin-odometer"
      data-near={ratio >= 0.75 || undefined}
      style={{ "--ratio": shownRatio } as CSSProperties}
    >
      <span
        className="widget-level__ring"
        role="progressbar"
        aria-label={t("gamification:level", { level })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <strong>{format.number(Math.round(shownLevel))}</strong>
        <span className="skin-odometer__sparks" aria-hidden="true">
          {[0, 1, 2, 3, 4, 5].map((n) => (
            <span key={n} style={{ "--n": n } as CSSProperties} />
          ))}
        </span>
      </span>
      <span className="widget-level__side">
        <span className="widget-level__name">{t("gamification:level", { level })}</span>
        {progression && next !== null ? (
          <span className="widget-level__next">
            <span className="widget-level__bar" aria-hidden="true">
              <span />
            </span>
            <small>
              {format.number(progression.xp - progression.level_floor)} /{" "}
              {format.number(next - progression.level_floor)} XP
            </small>
          </span>
        ) : null}
        <ul className="widget-level__values">
          {(
            [
              ["xp", xp, "sparkles"],
              ["coins", coins, "coins"],
              ["contribution", contribution, "heart"],
            ] as const
          ).map(([value, amount, icon]) => (
            <li key={value} data-value={value}>
              <Icon name={icon} size={14} />
              <strong className="skin-odometer__digits">{format.number(Math.round(amount))}</strong>
              <span>{t(`gamification:value.${value}`)}</span>
            </li>
          ))}
        </ul>
      </span>
    </Link>
  );
}

// --- daily objectives: « liquid » — gauges as liquid, a stamp on what is done -------------------------------
function Liquid({ Original, ...props }: SkinProps) {
  return (
    <div className="skin skin-liquid">
      <Original {...props} />
    </div>
  );
}

// --- poster rows: « deck » — a pile of cards shuffling ----------------------------------------------------
function Deck({ payload }: SkinProps) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  const cards = itemsOf({ payload } as WidgetProps)
    .filter((c) => art(c))
    .slice(0, 7);
  const [front, setFront] = useState(0);
  useEffect(() => {
    if (!lively || cards.length < 2) return;
    const timer = window.setInterval(() => setFront((n) => (n + 1) % cards.length), 4000);
    return () => window.clearInterval(timer);
  }, [lively, cards.length]);
  if (!cards.length) return null;
  const shown = cards[front % cards.length] as Card;
  return (
    <div ref={ref} className="skin-deck">
      <button
        type="button"
        className="skin-deck__pile"
        onClick={() => setFront((n) => (n + 1) % cards.length)}
        aria-label={t("dashboard:deck.next")}
      >
        {cards.map((card, index) => {
          const depth = (index - front + cards.length) % cards.length;
          return (
            <img
              // biome-ignore lint/suspicious/noArrayIndexKey: a title may come back in the deck
              key={`${card.id ?? card.title}-${index}`}
              src={art(card) ?? ""}
              alt=""
              data-depth={Math.min(depth, 4)}
              style={{ zIndex: cards.length - depth }}
            />
          );
        })}
      </button>
      <div className="skin-deck__text" key={shown.id ?? shown.title}>
        <strong>{shown.title}</strong>
        {shown.subtitle || shown.meta ? <span>{shown.subtitle ?? shown.meta}</span> : null}
        {shown.route ? (
          <Link className="ds-button ds-button--secondary" to={shown.route}>
            {t("dashboard:deck.open")}
          </Link>
        ) : null}
        <span className="skin-deck__dots" aria-hidden="true">
          {cards.map((card, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: one dot per card, in order
            <span key={`${card.id ?? card.title}-dot-${index}`} data-on={index === front || undefined} />
          ))}
        </span>
      </div>
    </div>
  );
}

// --- flip digits (upcoming, countdown) ---------------------------------------------------------------------
function FlipNumber({ value, label }: { value: number; label: string }) {
  const digits = String(Math.max(0, value)).padStart(2, "0").split("");
  return (
    <span className="skin-flip__group">
      <span className="skin-flip__digits">
        {digits.map((digit, index) => (
          // the key changes with the digit: the new one flips in
          // biome-ignore lint/suspicious/noArrayIndexKey: a digit's place is its identity
          <span key={`${index}-${digit}`} className="skin-flip__digit">
            {digit}
          </span>
        ))}
      </span>
      <small>{label}</small>
    </span>
  );
}

function useNow(lively: boolean, everyMs: number): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (!lively) return;
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), everyMs);
    return () => window.clearInterval(timer);
  }, [lively, everyMs]);
  return now;
}

function UpcomingFlip({ Original, ...props }: SkinProps) {
  const t = useT();
  const format = useFormat();
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  const now = useNow(lively, 30_000);
  const items = itemsOf(props);
  const startOf = (item: Card) => {
    const when = String(item.at ?? item.meta ?? "");
    return ISO.test(when) ? new Date(when.length === 10 ? `${when}T00:00:00` : when) : null;
  };
  // the first one still to come (one already under way has nothing left to count)
  const index = items.findIndex((item) => (startOf(item)?.getTime() ?? 0) > now.getTime());
  const next = items[index];
  const at = next ? startOf(next) : null;
  if (!next || !at) return <Original {...props} />;
  const left = Math.max(0, at.getTime() - now.getTime());
  const days = Math.floor(left / 86_400_000);
  const hours = Math.floor((left % 86_400_000) / 3_600_000);
  const minutes = Math.floor((left % 3_600_000) / 60_000);
  const List = TEMPLATES.list;
  return (
    <div ref={ref} className="skin-flip">
      <Link className="skin-flip__next" to={next.route ?? "/calendar"}>
        <span className="skin-flip__title">
          <strong>{next.title}</strong>
          <small>{format.dateTime(at)}</small>
        </span>
        <span
          className="skin-flip__board"
          role="timer"
          aria-label={t("dashboard:flip.left", { days, hours, minutes })}
        >
          <FlipNumber value={days} label={t("dashboard:flip.days")} />
          <FlipNumber value={hours} label={t("dashboard:flip.hours")} />
          <FlipNumber value={minutes} label={t("dashboard:flip.minutes")} />
        </span>
      </Link>
      {items.length > 1 ? (
        <List
          {...props}
          payload={{ ...props.payload, data: { items: items.filter((_, i) => i !== index) } } as never}
        />
      ) : null}
    </div>
  );
}

function CountdownFlip({ payload }: SkinProps) {
  const t = useT();
  const format = useFormat();
  const ctx = useLocaleContext();
  const data = (payload.data ?? {}) as { label?: string; date?: string };
  const date = String(data.date ?? "");
  const days = daysUntil(date, new Date(), ctx.time_zone ?? undefined);
  return (
    <div className="skin-flip skin-flip--countdown" data-past={days < 0 || undefined}>
      <span className="skin-flip__board">
        <FlipNumber value={Math.abs(days)} label={t("dashboard:flip.days")} />
      </span>
      <span className="skin-flip__what">
        <Icon name="hourglass" size={14} />
        {String(data.label ?? "").trim() || format.date(`${date}T12:00:00`, "medium")}
      </span>
    </div>
  );
}

// --- my statistics: « countup » — the figures counting up -------------------------------------------------
const NUMBER = /\d(?:[\d.,\u202f\u00a0 ]*\d)?/g;

/** ``token`` (« 1,234 », « 12.5 ») shown at ``share`` of its value, its separators kept in place. */
export function partOf(token: string, share: number): string {
  const digits = token.replace(/\D/g, "");
  const scaled = String(Math.round(Number(digits) * share)).padStart(digits.length, "0");
  let at = 0;
  const filled = token.replace(/\d/g, () => scaled[at++] ?? "0");
  return filled.replace(/^[0.,\u202f\u00a0 ]+(?=\d)/, "") || "0";
}

function CountUp({ Original, ...props }: SkinProps) {
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  useEffect(() => {
    const box = ref.current;
    if (!box || !lively) return;
    // only the text nodes change (the icons stay); each gets its final text back at the end
    const nodes: Array<{ node: Text; text: string; shown: string }> = [];
    for (const figure of box.querySelectorAll(".widget-media-stats__figures strong")) {
      const walker = document.createTreeWalker(figure, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (/\d/.test(node.nodeValue ?? ""))
          nodes.push({ node: node as Text, text: node.nodeValue ?? "", shown: "" });
      }
    }
    if (!nodes.length) return;
    const start = performance.now();
    let frame = 0;
    const step = (time: number) => {
      const done = Math.min(1, (time - start) / 1100);
      const eased = 1 - (1 - done) ** 3;
      for (const entry of nodes) {
        // React re-rendered it meanwhile: its text is the new one, leave it
        if (entry.shown && entry.node.nodeValue !== entry.shown) continue;
        entry.shown = done >= 1 ? entry.text : entry.text.replace(NUMBER, (token) => partOf(token, eased));
        entry.node.nodeValue = entry.shown;
      }
      if (done < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(frame);
      for (const { node, text, shown } of nodes) if (node.nodeValue === shown) node.nodeValue = text;
    };
  }, [lively]);
  return (
    <div ref={ref} className="skin skin-countup">
      <Original {...props} />
    </div>
  );
}

// --- poster wall: « kenburns » — a slow travelling over the mosaic ----------------------------------------
function KenBurns({ Original, ...props }: SkinProps) {
  return (
    <div className="skin skin-kenburns" data-nofit>
      <Original {...props} />
    </div>
  );
}

// --- latest news: « ticker » — the headlines running across, the list below -------------------------------
function Ticker({ Original, ...props }: SkinProps) {
  const t = useT();
  const items = itemsOf(props).filter((c) => c.title);
  if (!items.length) return <Original {...props} />;
  const lane = [...items, ...items];
  return (
    <div className="skin-ticker">
      <div className="skin-ticker__band" style={{ "--ticker-items": items.length } as CSSProperties}>
        <span className="skin-ticker__label">
          <Icon name="newspaper" size={14} />
          {t("dashboard:ticker.label")}
        </span>
        <div className="skin-ticker__lane">
          <div className="skin-ticker__track">
            {lane.map((item, index) => (
              <span
                // biome-ignore lint/suspicious/noArrayIndexKey: the lane repeats itself to loop
                key={`${item.title}-${index}`}
                className="skin-ticker__item"
                aria-hidden={index >= items.length || undefined}
              >
                {item.route ? (
                  <Link to={item.route} tabIndex={index >= items.length ? -1 : undefined}>
                    {item.title}
                  </Link>
                ) : (
                  item.title
                )}
              </span>
            ))}
          </div>
        </div>
      </div>
      <Original {...props} />
    </div>
  );
}

// --- clock: « analog » ---------------------------------------------------------------------------------------
function zoned(now: Date, timeZone: string | undefined): { h: number; m: number; s: number } {
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    ...(timeZone ? { timeZone } : {}),
  }).formatToParts(now);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return { h: get("hour") % 12, m: get("minute"), s: get("second") };
}

function AnalogClock({ payload }: SkinProps) {
  const ctx = useLocaleContext();
  const ref = useRef<HTMLDivElement>(null);
  const lively = useLively(ref);
  const data = (payload.data ?? {}) as { seconds?: boolean; date?: boolean };
  const now = useNow(lively, data.seconds ? 1000 : 15_000);
  const { h, m, s } = zoned(now, ctx.time_zone ?? undefined);
  const date = new Intl.DateTimeFormat(ctx.locale, {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: ctx.time_zone,
  }).format(now);
  const hand = (turn: number) => ({ transform: `rotate(${turn * 360}deg)` });
  return (
    <div ref={ref} className="skin-analog">
      <svg viewBox="0 0 100 100" role="img" aria-label={now.toLocaleTimeString(ctx.locale)}>
        <circle className="skin-analog__face" cx="50" cy="50" r="47" />
        {Array.from({ length: 12 }, (_, i) => (
          <line
            // biome-ignore lint/suspicious/noArrayIndexKey: the twelve hours
            key={i}
            className="skin-analog__tick"
            data-major={i % 3 === 0 || undefined}
            x1="50"
            y1="6"
            x2="50"
            y2={i % 3 === 0 ? 13 : 10}
            transform={`rotate(${i * 30} 50 50)`}
          />
        ))}
        <line className="skin-analog__hour" x1="50" y1="50" x2="50" y2="27" style={hand((h + m / 60) / 12)} />
        <line
          className="skin-analog__minute"
          x1="50"
          y1="50"
          x2="50"
          y2="16"
          style={hand((m + s / 60) / 60)}
        />
        {data.seconds ? (
          <line className="skin-analog__second" x1="50" y1="56" x2="50" y2="12" style={hand(s / 60)} />
        ) : null}
        <circle className="skin-analog__pin" cx="50" cy="50" r="2.4" />
      </svg>
      {data.date !== false ? <span className="skin-analog__date">{date}</span> : null}
    </div>
  );
}

// --- community activity: « live » — entries sliding in, a « live » light ----------------------------------
function Live({ Original, ...props }: SkinProps) {
  const t = useT();
  return (
    <div className="skin skin-live">
      <WidgetHeaderAction>
        <span className="skin-live__badge">
          <span aria-hidden="true" />
          {t("dashboard:live")}
        </span>
      </WidgetHeaderAction>
      <Original {...props} />
    </div>
  );
}

// --- registration ------------------------------------------------------------------------------------------
function skin(
  id: string,
  looks: Record<string, ComponentType<SkinProps>>,
  template?: keyof typeof TEMPLATES,
): void {
  const found = widgetComponent(id) ?? (template ? TEMPLATES[template] : undefined);
  if (!found) return;
  const Original: ComponentType<WidgetProps> = found;
  function Skinned(props: WidgetProps) {
    const Look = looks[String((props.config ?? {}).style ?? "classic")];
    return Look ? <Look {...props} Original={Original} /> : <Original {...props} />;
  }
  registerWidgetComponent(id, Skinned);
}

skin("media.continue", { ambient: Ambient });
skin("health.services_summary", { pulse: Pulse });
skin("gamification.progress", { odometer: Odometer });
skin("gamification.daily_objectives", { liquid: Liquid });
skin("media.posters", { deck: Deck });
skin("calendar.upcoming", { flip: UpcomingFlip }, "list");
skin("media.stats", { countup: CountUp });
skin("media.wall", { kenburns: KenBurns });
skin("news.latest", { ticker: Ticker }, "list");
skin("dashboard.clock", { analog: AnalogClock });
skin("dashboard.countdown", { flip: CountdownFlip });
skin("community.activity", { live: Live });
