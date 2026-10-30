import { useState } from "react";
import { Link, useNavigate } from "react-router";
import {
  AdminPage,
  AdminSection,
  SearchBox,
  StatusBadge,
  type Tone,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog, DialogActions, Menu } from "../../design-system/components/Overlays";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { useLocaleContext } from "../../i18n/provider/I18nProvider";
import { nextStep, type PackRow, packPath, useVisualAction, useVisualPacks, type VersionRow } from "./api";
import { nameOf } from "./parts";
import { VisualPackImport } from "./VisualPackImport";
import "./visuals.css";

/**
 * 028: Extensions → « Visual packs » — where every look comes in. The import first (the inbox, a .zip, a GitHub
 * address, the updates on offer), then the packs: imported ones apart from Portalab's own, searchable, one
 * compact card each — its state, what it holds, the version waiting for a step (one tap to carry on), its
 * actions in a menu and its earlier versions folded away.
 */

const STATE_TONE: Record<string, Tone> = { enabled: "ok", disabled: "neutral", archived: "warn" };
const STEP_TONE: Record<string, Tone> = {
  imported: "neutral",
  analysed: "info",
  tested: "info",
  reviewed: "info",
  published: "ok",
  refused: "bad",
  superseded: "neutral",
  purged: "neutral",
};
const CLOSED = new Set(["published", "superseded", "refused", "purged"]);

type Run = (path: string, body?: unknown) => Promise<Record<string, unknown> | null>;

export default function VisualsAdmin() {
  const t = useT();
  const packs = useVisualPacks();
  const action = useVisualAction();
  const [message, setMessage] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const all = packs.data?.packs ?? [];
  const imported = all.filter((p) => !p.builtin);
  const [filter, setFilter] = useState<"imported" | "builtin" | null>(null);
  const shown = filter ?? (imported.length ? "imported" : "builtin");
  const language = useLocaleContext().language.split("-")[0] ?? "en";
  const q = query.trim().toLowerCase();
  const list = all
    .filter((p) => (shown === "builtin" ? p.builtin : !p.builtin))
    .filter((p) => !q || p.id.includes(q) || nameOf(p.names, p.id, language).toLowerCase().includes(q));

  const run: Run = async (path, body) => {
    setMessage(null);
    try {
      return await action.mutateAsync({ path, body });
    } catch (error) {
      setMessage(String((error as Error).message));
      return null;
    }
  };
  const builtinState = async (state: "enabled" | "disabled") => {
    const result = await run("/api/v1/admin/visuals/builtin/state", { state });
    if (result) setMessage(t("admin:visuals.builtinChanged", { count: (result.changed as string[]).length }));
  };

  return (
    <AdminPage
      icon="sparkles"
      title={t("admin:visuals.title")}
      description={t("admin:visuals.description")}
      wide
    >
      <VisualPackImport />
      <AdminSection title={t("admin:visuals.packs")} icon="package" flush>
        <div className="vp-toolbar">
          <fieldset className="vp-tabs">
            <legend className="visually-hidden">{t("admin:visuals.filter")}</legend>
            {(["imported", "builtin"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={shown === value}
                onClick={() => setFilter(value)}
              >
                {t(`admin:visuals.filters.${value}`)}
                <span className="vp-tabs__count">
                  {value === "builtin" ? all.length - imported.length : imported.length}
                </span>
              </button>
            ))}
          </fieldset>
          <SearchBox label={t("admin:visuals.search")} value={query} onChange={setQuery} />
          {shown === "builtin" ? (
            <Menu
              label={t("admin:visuals.builtinActions")}
              align="end"
              trigger={
                <Button variant="ghost" size="icon" aria-label={t("admin:visuals.builtinActions")}>
                  <Icon name="more" size={18} />
                </Button>
              }
              items={[
                {
                  key: "on",
                  icon: "play",
                  label: t("admin:visuals.builtinOn"),
                  onSelect: () => void builtinState("enabled"),
                },
                {
                  key: "off",
                  icon: "pause",
                  label: t("admin:visuals.builtinOff"),
                  onSelect: () => void builtinState("disabled"),
                },
              ]}
            />
          ) : null}
        </div>
        {message ? (
          <p className="vp-message" role="status">
            {message}
          </p>
        ) : null}
        {packs.isPending ? <FunctionalState state="loading" label={t("admin:visuals.loading")} /> : null}
        {packs.isSuccess && !list.length ? <p className="visuals-empty">{t("admin:visuals.none")}</p> : null}
        <ul className="vp-list vp-list__packs">
          {list.map((pack) => (
            <PackCard key={pack.id} pack={pack} run={run} busy={action.isPending} language={language} />
          ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}

function PackCard({
  pack,
  run,
  busy,
  language,
}: {
  pack: PackRow;
  run: Run;
  busy: boolean;
  language: string;
}) {
  const t = useT();
  const navigate = useNavigate();
  const name = nameOf(pack.names, pack.id, language);
  const [removing, setRemoving] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);
  const live = pack.state === "enabled" && Boolean(pack.current);
  const current = pack.versions.find((v) => v.version === pack.current);
  // the version waiting for a step: the newest one not closed
  const waiting = pack.versions.find((v) => !CLOSED.has(v.step));
  const shown = current ?? waiting ?? pack.versions[0];
  const earlier = pack.versions.filter((v) => v !== current && v !== waiting);
  const summary = shown?.summary;
  const items = [
    ...(pack.current && !pack.socle
      ? [
          {
            key: "state",
            icon: live ? "pause" : "play",
            label: live ? t("admin:visuals.switchOff") : t("admin:visuals.switchOn"),
            onSelect: () => void run(`${packPath(pack.id)}/state`, { state: live ? "disabled" : "enabled" }),
          },
        ]
      : []),
    ...(shown
      ? [
          {
            key: "open",
            icon: "eye",
            label: t("admin:visuals.openVersion", { version: shown.version }),
            onSelect: () => navigate(`/admin/visuals/${pack.id}/${shown.version}`),
          },
        ]
      : []),
    ...(!pack.socle
      ? [
          {
            key: "remove",
            icon: "trash",
            label: t("admin:visuals.remove"),
            separated: true,
            onSelect: () => setRemoving(true),
          },
        ]
      : []),
  ];
  return (
    <li className="vp-card" data-state={pack.state}>
      <div className="vp-card__head">
        <div className="vp-card__title">
          {shown ? (
            <Link to={`/admin/visuals/${pack.id}/${shown.version}`} className="vp-card__name">
              {name}
            </Link>
          ) : (
            <span className="vp-card__name">{name}</span>
          )}
          <span className="vp-card__meta">
            <code>{pack.id}</code>
            {shown?.author ? ` · ${shown.author}` : ""}
            {!pack.builtin ? ` · ${t(`admin:visuals.source.${pack.source?.kind ?? "inbox"}`)}` : ""}
          </span>
        </div>
        <div className="vp-card__state">
          {pack.current ? (
            <StatusBadge tone={STATE_TONE[pack.state] ?? "neutral"}>
              {t(`admin:visuals.state.${pack.state}`, { version: pack.current })}
            </StatusBadge>
          ) : (
            <StatusBadge tone="neutral">{t("admin:visuals.unpublished")}</StatusBadge>
          )}
          {items.length ? (
            <Menu
              label={t("admin:visuals.actions", { pack: name })}
              align="end"
              trigger={
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={busy}
                  aria-label={t("admin:visuals.actions", { pack: name })}
                >
                  <Icon name="more" size={18} />
                </Button>
              }
              items={items}
            />
          ) : null}
        </div>
      </div>
      <div className="vp-card__facts">
        {summary ? <span>{t("admin:visuals.elements", { count: summary.elements })}</span> : null}
        {summary?.hd ? (
          <span className="visuals-flag" data-flag="hd">
            HD
          </span>
        ) : null}
        {summary?.video ? (
          <span className="visuals-flag" data-flag="video">
            {t("admin:visuals.video")}
          </span>
        ) : null}
        {summary?.script ? (
          <span className="visuals-flag" data-flag="script">
            {t("admin:visuals.script")}
          </span>
        ) : null}
        {pack.socle ? <span className="visuals-flag">{t("admin:visuals.socle")}</span> : null}
        {pack.failures ? (
          <StatusBadge tone="warn">{t("admin:visuals.failures", { count: pack.failures })}</StatusBadge>
        ) : null}
        {pack.update && pack.remote ? (
          <StatusBadge tone="info">{t("admin:visuals.remote", { version: pack.remote.version })}</StatusBadge>
        ) : null}
      </div>
      {waiting ? <Waiting pack={pack} version={waiting} /> : null}
      {outcome ? <p className="vp-message">{outcome}</p> : null}
      {earlier.length ? (
        <details className="vp-history">
          <summary>{t("admin:visuals.history", { count: earlier.length })}</summary>
          <ul>
            {earlier.map((v) => (
              <History key={v.version} pack={pack} version={v} run={run} busy={busy} />
            ))}
          </ul>
        </details>
      ) : null}
      <Dialog
        open={removing}
        onOpenChange={setRemoving}
        title={t("admin:visuals.removeTitle", { pack: name })}
        description={t("admin:visuals.removeHelp")}
        closeLabel={t("admin:visuals.cancel")}
        trigger={<span hidden />}
      >
        <DialogActions>
          <Button
            variant="danger"
            onClick={async () => {
              const result = await run(`${packPath(pack.id)}/remove`);
              setRemoving(false);
              if (result)
                setOutcome(
                  result.outcome === "archived"
                    ? t("admin:visuals.archived", { count: Number(result.owners) || 0 })
                    : t("admin:visuals.removed"),
                );
            }}
          >
            {t("admin:visuals.remove")}
          </Button>
        </DialogActions>
      </Dialog>
    </li>
  );
}

/** The version waiting for a step — where it stands, and one tap to carry on. */
function Waiting({ pack, version: v }: { pack: PackRow; version: VersionRow }) {
  const t = useT();
  const step = nextStep(v);
  const blocked = v.outcomes.analysis === "blocking" || v.outcomes.security === "blocking";
  return (
    <Link
      className="vp-waiting"
      data-blocked={blocked || undefined}
      to={`/admin/visuals/${pack.id}/${v.version}`}
    >
      <Icon name={blocked ? "alert" : "clock"} size={16} />
      <span>
        {t(blocked ? "admin:visuals.waitingBlocked" : "admin:visuals.waiting", {
          version: v.version,
          step: t(`admin:visuals.step.${step}`),
        })}
      </span>
      <Icon name="chevron-right" size={16} />
    </Link>
  );
}

function History({
  pack,
  version: v,
  run,
  busy,
}: {
  pack: PackRow;
  version: VersionRow;
  run: Run;
  busy: boolean;
}) {
  const t = useT();
  return (
    <li>
      <Link to={`/admin/visuals/${pack.id}/${v.version}`} className="vp-history__version">
        {v.version}
      </Link>
      <StatusBadge tone={STEP_TONE[v.step] ?? "neutral"}>
        {t(`admin:visuals.versionStep.${v.step}`)}
      </StatusBadge>
      {v.ever_published && pack.current !== v.version && !pack.builtin ? (
        <button
          type="button"
          className="vp-history__action"
          disabled={busy}
          onClick={() => run(`${packPath(pack.id, v.version)}/rollback`)}
        >
          {t("admin:visuals.rollbackShort")}
        </button>
      ) : null}
      {!v.ever_published && !pack.builtin ? (
        <button
          type="button"
          className="vp-history__action"
          disabled={busy}
          onClick={() => run(`${packPath(pack.id, v.version)}/purge`)}
        >
          {t("admin:visuals.purge")}
        </button>
      ) : null}
    </li>
  );
}
