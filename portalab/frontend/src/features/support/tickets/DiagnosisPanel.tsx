import { useState } from "react";
import { CSRF_COOKIE, CSRF_HEADER, readCookie } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";

/**
 * Assistant diagnosis (spec 016 T034, R11): streams the steps, each labelled **real data** or **assistant
 * interpretation**; the outcome is at most a draft the user reviews before submitting anything.
 */
interface Step {
  name: string;
  kind: "real" | "ai";
  status: string;
  data: Record<string, unknown>;
}

export function parseEvents(raw: string): Array<{ event: string; data: Record<string, unknown> }> {
  return raw
    .split("\n\n")
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const lines = block.split("\n");
      const event = (lines.find((l) => l.startsWith("event: ")) ?? "event: step").slice(7);
      const data = JSON.parse((lines.find((l) => l.startsWith("data: ")) ?? "data: {}").slice(6)) as Record<
        string,
        unknown
      >;
      return { event, data };
    });
}

export function DiagnosisPanel({
  problem,
  serviceId,
  onDraft,
}: {
  problem: string;
  serviceId?: string | undefined;
  onDraft: (draftId: string) => void;
}) {
  const t = useT();
  const [steps, setSteps] = useState<Step[]>([]);
  const [state, setState] = useState<"idle" | "running" | "done" | "unavailable">("idle");
  const start = async () => {
    setSteps([]);
    setState("running");
    const token = readCookie(CSRF_COOKIE);
    const response = await fetch("/api/v1/diagnosis/runs", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(token ? { [CSRF_HEADER]: token } : {}) },
      body: JSON.stringify({ problem, ...(serviceId ? { service_id: serviceId } : {}) }),
    });
    if (!response.ok || !response.body) {
      setState("unavailable");
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const cut = buffer.lastIndexOf("\n\n");
      if (cut < 0) continue;
      for (const { event, data } of parseEvents(buffer.slice(0, cut))) {
        if (event === "step") setSteps((current) => [...current, data as unknown as Step]);
        if (event === "error") setState("unavailable");
        if (event === "done") {
          setState("done");
          if (typeof data.draft === "string") onDraft(data.draft);
        }
      }
      buffer = buffer.slice(cut + 2);
    }
  };
  return (
    <section aria-label={t("support:diagnosis.title")} className="support-diagnosis">
      <Button
        variant="secondary"
        onClick={() => void start()}
        disabled={state === "running" || problem.trim().length < 3}
      >
        {t("support:diagnosis.start")}
      </Button>
      {state === "unavailable" ? (
        <FunctionalState state="unavailable" label={t("support:diagnosis.unavailable")} />
      ) : null}
      <ol aria-live="polite">
        {steps.map((step) => (
          <li key={step.name} data-kind={step.kind}>
            <strong>{step.kind === "ai" ? t("support:diagnosis.ai") : t("support:diagnosis.real")}</strong> ·{" "}
            {t(`support:diagnosis.step.${step.name}`)}
            {typeof step.data.summary === "string" ? <p>{step.data.summary}</p> : null}
            {typeof step.data.solution === "string" && step.data.solution ? (
              <p>{step.data.solution}</p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
