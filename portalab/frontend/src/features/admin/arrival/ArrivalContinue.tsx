import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { api } from "../../../api/client";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/FunctionalState";
import { DEFAULT_FAMILY } from "../../../design-system/themes/builtin";
import type { ThemeDefinition } from "../../../design-system/themes/schema";
import { useTheme } from "../../../design-system/themes/ThemeProvider";
import { useT } from "../../../i18n/hooks/useT";
import { NAVIGATION_KEY } from "../../../shell/nav/NavigationProvider";
import { useSite } from "../../../shell/site/site";
import { ModelSettings } from "../../ai/admin/AiSettings";
import { ThemeMiniature } from "../../appearance/AppearanceSettings";
import { SettingCard } from "../ConfigEditor";
import { EmailSettings } from "../communication/EmailSettings";
import { RequestQuotaDefaults } from "../media/RequestQuotasAdmin";
import { ServiceAccountsPanel } from "../members/ServiceAccountsPanel";
import { AddServiceWizard } from "../services/ServicesAdmin";
import { type Progress, type StepKey, useSetupProgress } from "../setup/progress";
import { type Configure, configureWay, useArrivalSlides, wayOf } from "./ArrivalWizard";
import { useCurrentFeatures } from "./FeaturesPicker";
import { ALL_FEATURES, type Selection } from "./features";
import { applyGame, GAME_TASKS, type GameChoice, GameStep, notApplied } from "./GameStep";
import { Launch, useTasks } from "./Launch";
import { Stage, StepCard } from "./Stage";
import "../../ai/ai.css";
import "./arrival.css";

/**
 * Issue 249 — the arrival wizard, signed in: right after the account is created, at ``/setup``, still a page of
 * its own — the services (Plex, Jellyfin, Seerr…), the members' accounts on them, who may join, the e-mail,
 * the portal's look, play and the shop, the AI assistant (the last two only when their feature is kept) —
 * each one skippable, where it is kept by the server (``admin.setup.progress.arrival``, so a reload resumes
 * it). Then the last checks behind the waiting screens — and the recommended install, put in place there rather
 * than at the game step: its game and shop part after part (unless adjusted, then already in place), its visual
 * packs a few at a time — and the portal opens. Once finished, ``/setup`` is the setup assistant's
 * (``/admin/setup``) to come back to.
 */
type Step = Configure | "open";
// the setup assistant's steps each one of the wizard's covers
const COVERS: Record<Configure, StepKey> = {
  services: "services",
  quotas: "media",
  members: "members",
  access: "access",
  email: "communication",
  appearance: "appearance",
  play: "play",
  ai: "ai",
};
const ICONS: Record<Step, string> = {
  services: "server",
  quotas: "coins",
  members: "users",
  access: "key",
  email: "mail",
  appearance: "palette",
  play: "trophy",
  ai: "bot",
  open: "rocket",
};

interface Arrival {
  step?: Step;
  skipped?: Step[];
  finished_at?: string | null;
  game?: GameChoice; // issue 253: the LAN's game, adjusted, or set by hand
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
  const features = useCurrentFeatures();
  const services = useServices();
  const state = progress as WithArrival;
  const going = useRef(false); // once on its way, the wizard ends itself (its last step finishes it)
  // the services first: whether Seerr is connected decides if the request quotas are on the way
  if (settings.isPending || features.isPending || services.isPending)
    return <FunctionalState state="loading" detail="Portalab" />;
  if (settings.isError) return <Navigate to="/" replace />; // not the portal's administrator
  if (!going.current && (!state.arrival || state.arrival.finished_at))
    return <Navigate to="/admin/setup" replace />;
  going.current = true;
  return (
    <Way
      initial={state}
      features={features.data ?? ALL_FEATURES}
      seerr={(services.data ?? []).some((s) => s.connector === "seerr")}
      save={(next) => save.mutateAsync(next)}
    />
  );
}

function Way({
  initial,
  features,
  seerr,
  save,
}: {
  initial: WithArrival;
  features: Selection;
  seerr: boolean;
  save: (next: WithArrival) => Promise<void>;
}) {
  const t = useT();
  const site = useSite();
  const titleId = useId();
  const [progress, setProgress] = useState<WithArrival>(initial); // shown at once, kept by the server
  const keep = async (next: WithArrival) => {
    setProgress(next);
    await save(next);
  };
  const arrival = progress.arrival ?? {};
  const order: readonly Step[] = [...configureWay(features, seerr), "open"];
  const step: Step = order.includes(arrival.step as Step) ? (arrival.step as Step) : "services";
  const index = order.indexOf(step);
  const prepare = ["welcome", "identity", "features", "admin", "recap"];
  const way = wayOf(step, "new", prepare, features, seerr).map((s) =>
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
  const next = order[index + 1];
  const previous = order[index - 1];
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
        <Open
          progress={progress}
          steps={order.filter((s): s is Configure => s !== "open")}
          save={keep}
          onBack={() => move(order[index - 1] ?? "services", null)}
        />
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
          {step === "quotas" ? <RequestQuotaDefaults /> : null}
          {step === "members" ? <ServiceAccountsPanel /> : null}
          {step === "access" ? <AccessStep /> : null}
          {step === "email" ? <EmailSettings /> : null}
          {step === "appearance" ? <AppearanceStep /> : null}
          {step === "play" ? (
            <GameStep
              choice={arrival.game}
              onChoose={(game) => {
                const { game: _former, ...rest } = arrival;
                keep({ ...progress, arrival: game ? { ...rest, game } : rest }).catch(() => undefined);
              }}
              settings={<Settings keys={PLAY} />}
            />
          ) : null}
          {step === "ai" ? <ModelSettings /> : null}
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

/** One global setting written as the wizard's choice (validated and audited like any other). */
function useSetting(key: string) {
  const client = useQueryClient();
  const { settings } = useSetupProgress();
  const set = useMutation({
    mutationFn: async (value: unknown) =>
      api.PUT("/api/v1/admin/config", {
        body: {
          changes: [{ key, value, scope: "global", scope_ref: "", unset: false }],
          reason: "arrival wizard",
        } as never,
      }),
    onSettled: () => client.invalidateQueries({ queryKey: ["admin", "config"] }),
  });
  return { value: settings.data?.find((s) => s.key === key)?.value, set };
}

/** The real settings of a step, each one a card that saves itself. */
function Settings({ keys }: { keys: readonly string[] }) {
  const { settings } = useSetupProgress();
  const items = keys.flatMap((key) => settings.data?.find((s) => s.key === key) ?? []);
  if (!items.length) return null;
  return (
    <ul className="setting-cards">
      {items.map((item) => (
        <SettingCard key={`${item.key}:${JSON.stringify(item.value)}`} item={item} />
      ))}
    </ul>
  );
}

const PLAY = ["economy.timezone", "economy.contribution.amount"] as const;

function AccessStep() {
  const t = useT();
  const { value, set } = useSetting("identity.registrationMode");
  const current = (value as string | undefined) ?? "invite_only";
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

/** The interface members get until they choose one: each family drawn in miniature, then those they may pick. */
function AppearanceStep() {
  const t = useT();
  const { themes } = useTheme();
  const { value, set } = useSetting("ui.defaultTheme");
  const shown = themes.filter(
    (theme, index) => !theme.family || themes.findIndex((other) => other.family === theme.family) === index,
  );
  const chosen = (theme: ThemeDefinition) => value === theme.key || (theme.family && value === theme.family);
  return (
    <>
      <ul className="theme-gallery__list" aria-label={t("account:arrival.appearance.default")}>
        {shown.map((theme) => (
          <li key={theme.key} className="theme-gallery__item">
            <button
              type="button"
              className="theme-card"
              aria-pressed={Boolean(chosen(theme))}
              disabled={set.isPending}
              onClick={() => set.mutate(theme.family ?? theme.key)}
            >
              <ThemeMiniature theme={theme} />
              <span className="theme-card__name">
                {theme.family === DEFAULT_FAMILY ? "Portalab" : (theme.family ?? theme.name)}
                {chosen(theme) ? (
                  <span className="theme-card__current">
                    <Icon name="check" size={12} />
                    {t("account:arrival.appearance.chosen")}
                  </span>
                ) : null}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {set.isError ? <p role="alert">{t("account:arrival.error")}</p> : null}
      <Settings keys={["ui.allowedThemes"]} />
    </>
  );
}

const OPEN_TASKS = ["save", "navigation", "services", "home"] as const;
const PACKS_AT_ONCE = 5; // a request per few packs: the ring follows them, none runs for minutes
const OPEN_WEIGHTS = { packs: 12, shop: 3 }; // a minute or so, a few seconds, where the others take a moment

/** The recommended install's visual packs, a few at a time; those not installed (an extension they dress is
 * missing…) said, never fatal. */
export async function installPacks(
  progress: (share: number, detail?: string | null) => void,
): Promise<string[]> {
  const presets = (await api.GET("/api/v1/admin/game/presets")).data as unknown as Array<{
    key: string;
    packs?: string[];
  }>;
  const packs = (Array.isArray(presets) ? presets : []).find((p) => p.key === "lan")?.packs ?? [];
  const missed: string[] = [];
  for (let start = 0; start < packs.length; start += PACKS_AT_ONCE) {
    progress(start / packs.length, `${start}/${packs.length}`);
    const batch = packs.slice(start, start + PACKS_AT_ONCE);
    const { data, error } = await api.POST("/api/v1/admin/game/setup", {
      body: { preset: "lan", parts: ["packs"], packs: batch } as never,
    });
    if (error) throw error;
    const report = data as unknown as { skipped: Array<{ part: string; key: string }> };
    for (const s of report.skipped ?? []) if (s.key.startsWith("pack ")) missed.push(s.key.slice(5));
  }
  progress(1, `${packs.length}/${packs.length}`);
  return missed;
}

/** What is ready, then the last checks behind the waiting screens, and the portal opens. */
function Open({
  progress,
  steps,
  save,
  onBack,
}: {
  progress: WithArrival;
  steps: readonly Configure[];
  save: (next: WithArrival) => Promise<void>;
  onBack: () => void;
}) {
  const t = useT();
  const site = useSite();
  const navigate = useNavigate();
  const client = useQueryClient();
  const titleId = useId();
  const services = useServices();
  const game = progress.arrival?.game;
  const [tasks] = useState<readonly string[]>(() => [
    ...(game === "lan" ? GAME_TASKS : []), // adjusted: already in place at the game step
    ...(game === "lan" || game === "tune" ? ["packs"] : []),
    ...OPEN_TASKS,
  ]);
  const { states, percent, detail, run, finished } = useTasks(tasks, OPEN_WEIGHTS);
  const [missed, setMissed] = useState<string[]>([]);
  const [failed, setFailed] = useState<string[]>([]);
  const slides = useArrivalSlides(ALL_FEATURES);
  const opened = useRef(false);
  const open = useMutation({
    mutationFn: async () => {
      opened.current = true;
      const left: string[] = [];
      for (const task of GAME_TASKS)
        if (tasks.includes(task)) left.push(...notApplied(await run(task, () => applyGame(task))));
      setFailed(left);
      if (tasks.includes("packs")) setMissed(await run("packs", installPacks)); // before the wizard ends
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
    if (!finished || missed.length || failed.length) return; // what is not in place said, the way in left to the button
    const timer = setTimeout(() => navigate("/", { replace: true }), 1600);
    return () => clearTimeout(timer);
  }, [finished, missed.length, failed.length, navigate]);
  if (opened.current || open.isPending || open.isSuccess) {
    return (
      <section className="arrival-card arrival-card--launch" aria-label={t("account:arrival.open.launching")}>
        <Launch
          title={
            finished
              ? t("account:arrival.open.welcome", { name: site.name })
              : t("account:arrival.open.launching")
          }
          tasks={tasks.map((key) => ({
            key,
            label: t(`account:arrival.open.task.${key}`),
            detail: states[key] === "running" ? detail : null,
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
            <>
              {failed.length ? (
                <p className="arrival__note">
                  <Icon name="info" size={16} />
                  {t("account:arrival.game.failed", { keys: failed.join(", ") })}
                </p>
              ) : null}
              {missed.length ? (
                <p className="arrival__note">
                  <Icon name="info" size={16} />
                  {t("account:arrival.game.packs", { count: missed.length, packs: missed.join(", ") })}
                </p>
              ) : null}
              <p>
                <Button onClick={() => navigate("/", { replace: true })}>
                  {t("account:arrival.open.enter")}
                  <Icon name="chevron-right" size={16} />
                </Button>
              </p>
            </>
          ) : null}
        </Launch>
      </section>
    );
  }
  const skipped = progress.arrival?.skipped ?? [];
  const facts: Array<[Step, string]> = steps.map((key) => [
    key,
    key === "services"
      ? t("account:arrival.open.services", { count: services.data?.length ?? 0 })
      : skipped.includes(key)
        ? t("account:arrival.open.later")
        : t("account:arrival.open.ready"),
  ]);
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
