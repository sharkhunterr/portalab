import { useLocaleContext } from "../provider/I18nProvider";

/**
 * ``useFormat()`` (spec 026 T021): dates, times, numbers, percentages, relative times through ``Intl`` for
 * the user's *locale* and time zone, honouring the hour-cycle preference. Representation only.
 */
export function useFormat() {
  const ctx = useLocaleContext();
  const hour12 = ctx.hour_cycle === null ? undefined : ctx.hour_cycle === "h12";
  return {
    date: (value: Date | string, style: "short" | "medium" | "long" = "medium") =>
      new Intl.DateTimeFormat(ctx.locale, { dateStyle: style, timeZone: ctx.time_zone }).format(
        new Date(value),
      ),
    /** 027: a calendar leaf — the day and the short month apart (``{ day: "5", month: "oct." }``). */
    dayMonth: (value: Date | string) => {
      const parts = new Intl.DateTimeFormat(ctx.locale, {
        day: "numeric",
        month: "short",
        timeZone: ctx.time_zone,
      }).formatToParts(new Date(value));
      return {
        day: parts.find((p) => p.type === "day")?.value ?? "",
        month: parts.find((p) => p.type === "month")?.value ?? "",
      };
    },
    time: (value: Date | string) =>
      new Intl.DateTimeFormat(ctx.locale, {
        hour: "numeric",
        minute: "2-digit",
        timeZone: ctx.time_zone,
        ...(hour12 === undefined ? {} : { hour12 }),
      }).format(new Date(value)),
    dateTime: (value: Date | string) =>
      new Intl.DateTimeFormat(ctx.locale, {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: ctx.time_zone,
        ...(hour12 === undefined ? {} : { hour12 }),
      }).format(new Date(value)),
    number: (value: number) => new Intl.NumberFormat(ctx.locale).format(value),
    percent: (ratio: number) => new Intl.NumberFormat(ctx.locale, { style: "percent" }).format(ratio),
    relative: (seconds: number) => {
      const rtf = new Intl.RelativeTimeFormat(ctx.locale, { numeric: "auto" });
      const abs = Math.abs(seconds);
      if (abs < 60) return rtf.format(Math.round(seconds), "second");
      if (abs < 3600) return rtf.format(Math.round(seconds / 60), "minute");
      if (abs < 86400) return rtf.format(Math.round(seconds / 3600), "hour");
      return rtf.format(Math.round(seconds / 86400), "day");
    },
  };
}
