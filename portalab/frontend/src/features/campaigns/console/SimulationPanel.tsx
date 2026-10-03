import { useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { useCampaignAdmin } from "../api";

/** Sample occurrence through the real resolver, audience and conditions (spec 014 R13) — writes nothing. */
export function SimulationPanel({ campaignId }: { campaignId: string }) {
  const t = useT();
  const { simulate } = useCampaignAdmin();
  const [eventType, setEventType] = useState("media.playback_finished");
  const [payload, setPayload] = useState("{}");
  const run = () => {
    try {
      simulate.mutate({
        id: campaignId,
        event_type: eventType,
        payload: JSON.parse(payload) as Record<string, unknown>,
      });
    } catch {
      /* invalid JSON: nothing to simulate */
    }
  };
  return (
    <section className="ds-stack">
      <TextField
        label={t("campaigns:admin.simulate.event")}
        value={eventType}
        onChange={(e) => setEventType(e.target.value)}
      />
      <label htmlFor={`campaign-payload-${campaignId}`}>{t("campaigns:admin.simulate.payload")}</label>
      <textarea
        id={`campaign-payload-${campaignId}`}
        rows={3}
        value={payload}
        onChange={(e) => setPayload(e.target.value)}
      />
      <Button variant="secondary" onClick={run}>
        {t("campaigns:admin.simulate")}
      </Button>
      {simulate.data ? (
        <ul aria-live="polite">
          {simulate.data.map((row) => (
            <li key={row.modifier} data-verdict={row.verdict}>
              {row.modifier} · {row.value} ×{row.factor} — {t(`campaigns:admin.verdict.${row.verdict}`)}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
