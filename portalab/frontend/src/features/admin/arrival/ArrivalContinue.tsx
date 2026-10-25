import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { NAVIGATION_KEY } from "../../../shell/nav/NavigationProvider";
import { useSite } from "../../../shell/site/site";
import { EmailSettings } from "../communication/EmailSettings";
import { ServiceAccountsPanel } from "../members/ServiceAccountsPanel";
import { AddServiceWizard } from "../services/ServicesAdmin";
import { type Progress, type StepKey, useSetupProgress } from "../setup/progress";
import { CONFIGURE, useArrivalSlides, wayOf } from "./ArrivalWizard";
import { ALL_FEATURES } from "./features";
import { Launch, useTasks } from "./Launch";
import { Stage, StepCard } from "./Stage";
import "./arrival.css";

/**
 * Issue 249 — the arrival wizard, signed in: right after the account is created, at ``/setup``, still a page of
 * its own — the services (Plex, Jellyfin, Seerr…), the members' accounts on them, who may join, the e-mail —
 * each one skippable, where it is kept by the server (``admin.setup.progress.arrival``, so a reload resumes
 * it). Then the last checks behind the waiting screens, and the portal opens. Once finished, ``/setup`` is
 * the setup assistant's (``/admin/setup``) to come back to.
 */
type Configure = (typeof CONFIGURE)[number];
type Step = Configure | "open";
const ORDER: readonly Step[] = [...CONFIGURE, "open"];
// the setup assistant's steps each one of the wizard's covers
const COVERS: Record<Configure, StepKey> = {
  services: "services",
  members: "members",
  access: "access",
  email: "communication",
};
const ICONS: Record<Step, string> = {
  services: "server",
  members: "users",
  access: "key",
  email: "mail",
  open: "rocket",
};

interface Arrival {
  step?: Step;
  skipped?: Step[];
  finished_at?: string | null;
}

type WithArrival = Progress & { arrival?: Arrival };

interface Service {
  id: string;
  name: string;
  connector: string;
  health: string;
}

function useServices() {
  return useQuery({
    queryKey: ["admin", "services"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/services")).data as unknown as { items: Service[] }).items ?? [],
  });
}

export function ArrivalContinue() {
  const { settings, progress, save } = useSetupProgress();
  const state = progress as WithArrival;
  const going = useRef(false); // once on its way, the wizard ends itself (its last step finishes it)
  if (settings.isPending) return <FunctionalState state="loading" detail="Portalab" />;
  if (settings.isError) return <Navigate to="/" replace />; // not the portal's administrator
  if (!going.current && (!state.arrival || state.arrival.finished_at))
    return <Navigate to="/admin/setup" replace />;
  going.current = true;
  return <Way initial={state} save={(next) => save.mutateAsync(next)} />;
}

function Way({ initial, save }: { initial: WithArrival; save: (next: WithArrival) => Promise<void> }) {
  const t = useT();
  const site = useSite();
  const titleId = useId();
  const [progress, setProgress] = useState<WithArrival>(initial); // shown at once, kept by the server
  const keep = async (next: WithArrival) => {
    setProgress(next);
    await save(next);
  };
  const arrival = progress.arrival ?? {};
  const step: Step = ORDER.includes(arrival.step as Step) ? (arrival.step as Step) : "services";
  const index = ORDER.indexOf(step);
  const prepare = ["welcome", "identity", "features", "admin", "recap"];
  const way = wayOf(step, "new", prepare).map((s) =>
    arrival.skipped?.includes(s.key as Step) && s.state === "done" ? { ...s, state: "skipped" as const } : s,
  );
  const move = (to: Step, mark: "done" | "skipped" | null) => {
    const covered = step === "open" ? null : COVERS[step];
    const done = new Set(progress.done ?? []);
    const skipped = new Set(arrival.skipped ?? []);
    if (mark === "done" && covered) done.add(covered);
    if (mark === "skipped") skipped.add(step);
    if (mark === "done") skipped.delete(step);
    keep({ ...progress, done: [...done], arrival: { ...arrival, step: to, skipped: [...skipped] } }).catch(
      () => undefined, // kept the next time
    );
  };
  const next = ORDER[index + 1];
  const previous = ORDER[index - 1];
  const footer =
    step === "open" ? null : (
      <>
        {previous ? (
          <Button variant="ghost" onClick={() => move(previous, null)}>
            <Icon name="back" size={16} />
            {t("account:arrival.previous")}
          </Button>
        ) : (
          <span />
        )}
        {next ? (
          <span className="arrival__forward">
            <Button variant="ghost" onClick={() => move(next, "skipped")}>
              {t("account:arrival.skip")}
            </Button>
            <Button onClick={() => move(next, "done")}>
              {t("account:arrival.next")}
              <Icon name="chevron-right" size={16} />
            </Button>
          </span>
        ) : null}
      </>
    );
  return (
    <Stage steps={way} name={site.name}>
      {step === "open" ? (
        <Open progress={progress} save={keep} onBack={() => move("email", null)} />
      ) : (
        <StepCard
          id={titleId}
          stepKey={step}
          icon={ICONS[step]}
          title={t(`account:arrival.${step}.title`)}
          lead={t(`account:arrival.${step}.lead`)}
          footer={footer}
        >
          {step === "services" ? <ServicesStep /> : null}
          {step === "members" ? <ServiceAccountsPanel /> : null}
          {step === "access" ? <AccessStep /> : null}
          {step === "email" ? <EmailSettings /> : null}
        </StepCard>
      )}
    </Stage>
  );
}

function ServicesStep() {
  const t = useT();
  const services = useServices();
  const list = services.data ?? [];
  return (
    <>
      {list.length ? (
        <ul
          className="arrival__chips arrival__chips--services"
          aria-label={t("account:arrival.services.connected")}
        >
          {list.map((s) => (
            <li key={s.id} data-health={s.health}>
              <Icon name="check" size={14} />
              {s.name}
            </li>
          ))}
        </ul>
      ) : (
        <p className="arrival__note">
          <Icon name="info" size={16} />
          {t("account:arrival.services.none")}
        </p>
      )}
      <AddServiceWizard />
    </>
  );
}

const REGISTRATION = "identity.registrationMode";

function AccessStep() {
  const t = useT();
  const client = useQueryClient();
  const { settings } = useSetupProgress();
  const current = (settings.data?.find((s) => s.key === REGISTRATION)?.value as string) ?? "invite_only";
  const set = useMutation({
    mutationFn: async (value: string) =>
      api.PUT("/api/v1/admin/config", {
        body: {
          changes: [{ key: REGISTRATION, value, scope: "global", scope_ref: "", unset: false }],
          reason: "arrival wizard",
        } as never,
      }),
    onSettled: () => client.invalidateQueries({ queryKey: ["admin", "config"] }),
  });
  return (
    <div className="arrival__choices">
      {(["invite_only", "open"] as const).map((value) => (
        <button
          key={value}
          type="button"
          className="arrival__choice"
          aria-pressed={current === value}
          disabled={set.isPending}
          onClick={() => set.mutate(value)}
        >
          <span className="arrival__choice-icon" aria-hidden="true">
            <Icon name={value === "open" ? "users" : "lock"} size={22} />
          </span>
          <strong>{t(`account:arrival.access.${value}`)}</strong>
          <span>{t(`account:arrival.access.${value}Hint`)}</span>
        </button>
      ))}
      {set.isError ? <p role="alert">{t("account:arrival.error")}</p> : null}
    </div>
  );
}

const OPEN_TASKS = ["save", "navigation", "services", "home"] as const;

/** What is ready, then the last checks behind the waiting screens, and the portal opens. */
function Open({
  progress,
  save,
  onBack,
}: {
  progress: WithArrival;
  save: (next: WithArrival) => Promise<void>;
  onBack: () => void;
}) {
  const t = useT();
  const site = useSite();
  const navigate = useNavigate();
  const client = useQueryClient();
  const titleId = useId();
  const services = useServices();
  const { states, percent, run, finished } = useTasks(OPEN_TASKS);
  const slides = useArrivalSlides(ALL_FEATURES);
  const opened = useRef(false);
  const open = useMutation({
    mutationFn: async () => {
      opened.current = true;
      await run("save", async () => {
        const now = new Date().toISOString();
        await save({
          ...progress,
          step: "summary",
          finished_at: now,
          arrival: { ...progress.arrival, step: "open", finished_at: now },
        });
      });
      await run("navigation", async () => {
        await client.invalidateQueries({ queryKey: NAVIGATION_KEY });
      });
      await run("services", async () => {
        await api.GET("/api/v1/services/health").catch(() => undefined);
      });
      await run("home", async () => {
        await client.invalidateQueries();
      });
    },
  });
  useEffect(() => {
    if (!finished) return;
    const timer = setTimeout(() => navigate("/", { replace: true }), 1600);
    return () => clearTimeout(timer);
  }, [finished, navigate]);
  if (opened.current || open.isPending || open.isSuccess) {
    return (
      <section className="arrival-card arrival-card--launch" aria-label={t("account:arrival.open.launching")}>
        <Launch
          title={
            finished
              ? t("account:arrival.open.welcome", { name: site.name })
              : t("account:arrival.open.launching")
          }
          tasks={OPEN_TASKS.map((key) => ({
            key,
            label: t(`account:arrival.open.task.${key}`),
            state: states[key] ?? "waiting",
          }))}
          percent={percent}
          slides={slides}
          failed={open.isError}
          done={finished}
        >
          {open.isError ? (
            <div className="launch__error">
              <p role="alert">{t("account:arrival.error")}</p>
              <Button onClick={() => open.mutate()}>
                <Icon name="retry" size={16} />
                {t("account:arrival.retry")}
              </Button>
            </div>
          ) : finished ? (
            <p>
              <Button onClick={() => navigate("/", { replace: true })}>
                {t("account:arrival.open.enter")}
                <Icon name="chevron-right" size={16} />
              </Button>
            </p>
          ) : null}
        </Launch>
      </section>
    );
  }
  const skipped = progress.arrival?.skipped ?? [];
  const facts: Array<[Step, string]> = [
    ["services", t("account:arrival.open.services", { count: services.data?.length ?? 0 })],
    [
      "members",
      skipped.includes("members") ? t("account:arrival.open.later") : t("account:arrival.open.ready"),
    ],
    [
      "access",
      skipped.includes("access") ? t("account:arrival.open.later") : t("account:arrival.open.ready"),
    ],
    ["email", skipped.includes("email") ? t("account:arrival.open.later") : t("account:arrival.open.ready")],
  ];
  return (
    <StepCard
      id={titleId}
      stepKey="open"
      icon="rocket"
      title={t("account:arrival.open.title")}
      lead={t("account:arrival.open.lead")}
      footer={
        <>
          <Button variant="ghost" onClick={onBack}>
            <Icon name="back" size={16} />
            {t("account:arrival.previous")}
          </Button>
          <Button onClick={() => open.mutate()}>
            <Icon name="rocket" size={16} />
            {t("account:arrival.open.go")}
          </Button>
        </>
      }
    >
      <ul className="arrival__ready">
        {facts.map(([key, text]) => (
          <li key={key} data-later={skipped.includes(key) || undefined}>
            <span className="arrival-card__icon" aria-hidden="true">
              <Icon name={ICONS[key]} size={18} />
            </span>
            <span>
              <strong>{t(`account:arrival.step.${key}`)}</strong>
              <span>{text}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="arrival__note">
        <Icon name="info" size={16} />
        {t("account:arrival.open.again")}
      </p>
    </StepCard>
  );
}

export default ArrivalContinue;
