import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../api/client";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useT } from "../../i18n/hooks/useT";
import { useMeasures } from "../media/insights/api";
import { chooseProfile, type ScreenTime, useScreenTime } from "./api";

const BEAT_MS = 60_000;
const KEY = ["household", "screen", null] as const;

/** Whether a profile's screen time is over now: outside its spans, or its day's or its span's time spent. */
export function spent(screen: ScreenTime | null | undefined): boolean {
  if (!screen) return false;
  if (!screen.open) return true;
  if (screen.allowed !== null && screen.allowed !== undefined && screen.used >= screen.allowed) return true;
  const slot = screen.slot;
  return Boolean(slot?.allowed && slot.used >= slot.allowed);
}

/**
 * Issue 439: for a profile whose master counts all of Portalab as screen time — each minute on the portal
 * (its tab in view) is told to the server, and once the time is over (or outside its spans) the portal is
 * covered by a « screen time is over » screen, with « Switch profile » only.
 */
export function ScreenGuard({ profile }: { profile: boolean }) {
  const t = useT();
  const measures = useMeasures();
  const client = useQueryClient();
  const screen = useScreenTime(null, profile, true);
  const portal = screen.data?.scope === "portal";
  useEffect(() => {
    if (!portal) return;
    const beat = async () => {
      if (globalThis.document?.visibilityState !== "visible") return;
      const { data } = await api.POST("/api/v1/me/media/screen-time/beat");
      client.setQueryData(KEY, data ?? null);
    };
    void beat();
    const timer = setInterval(() => void beat(), BEAT_MS);
    return () => clearInterval(timer);
  }, [portal, client]);
  if (!portal || !spent(screen.data)) return null;
  const next = screen.data?.next;
  return (
    <div className="screen-guard" role="alertdialog" aria-modal="true" aria-labelledby="screen-guard-title">
      <div className="screen-guard__card">
        <Icon name="clock" size={40} />
        <h2 id="screen-guard-title">{t("household:guard.title")}</h2>
        <p>
          {next
            ? t("household:guard.next", { start: next.start, end: next.end })
            : t("household:guard.tomorrow")}
        </p>
        {screen.data?.allowed ? (
          <p className="screen-guard__used">
            {t("household:schedule.of", {
              used: measures.duration(screen.data.used * 60),
              allowed: measures.duration(screen.data.allowed * 60),
            })}
          </p>
        ) : null}
        <Button type="button" onClick={() => chooseProfile()}>
          <Icon name="users" size={16} />
          {t("household:guard.switch")}
        </Button>
      </div>
    </div>
  );
}
