import { useEffect, useRef, useState } from "react";
import { AdminPage, AdminSection, StatusBadge, type Tone } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { TextField } from "../../design-system/components/Field";
import { Icon } from "../../design-system/components/Icon";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import {
  type ExternalElement,
  externalFx,
  fxName,
  installElements,
  uninstallScope,
} from "../../design-system/themes/external/external";
import { useT } from "../../i18n/hooks/useT";
import type { Product } from "../marketplace/api";
import { ProductArt } from "../marketplace/catalog/ProductArt";
import { TryOn } from "../marketplace/product/ProductSheet";
import {
  type Economy,
  type ElementReport,
  type Finding,
  type PackRow,
  type SimulationResult,
  useVersionDetail,
  useVisualAction,
  useVisualPacks,
  type VersionDetail,
} from "./api";
import "./visuals.css";

/**
 * issue 1 (POC): « Visual packs » — where imported looks come in. Sources (the inbox folder read again, a
 * .zip uploaded, a GitHub address, the updates on offer), every pack and its versions, and for a version:
 * its analysis report, its elements drawn for real in a sandbox (as in the shop, tried on oneself), what the
 * browser measured, the economy each element proposes — changeable — and the decision.
 */

const STATUS_TONE: Record<string, Tone> = { pending: "warn", approved: "ok", rejected: "bad" };
const LEVEL_TONE: Record<string, Tone> = { blocking: "bad", warning: "warn", info: "info" };
const RARITIES = ["common", "rare", "epic", "legendary"];

function param(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value ?? "");
}

export default function VisualsAdmin() {
  const t = useT();
  const packs = useVisualPacks();
  const action = useVisualAction();
  const [selected, setSelected] = useState<{ pack: string; version: string } | null>(null);
  const [github, setGithub] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [updates, setUpdates] = useState<Array<Record<string, unknown>> | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const run = async (path: string, body?: unknown, raw?: Blob) => {
    setMessage(null);
    try {
      const result = await action.mutateAsync({ path, body, ...(raw ? { raw } : {}) });
      return result;
    } catch (error) {
      setMessage({ tone: "error", text: String((error as Error).message) });
      return null;
    }
  };

  const list = packs.data?.packs ?? [];
  return (
    <AdminPage
      icon="sparkles"
      title={t("admin:visuals.title")}
      description={t("admin:visuals.description")}
      wide
    >
      {message ? (
        <FunctionalState state={message.tone === "error" ? "error" : "available"} label={message.text} />
      ) : null}
      <AdminSection
        title={t("admin:visuals.sources")}
        icon="download"
        description={t("admin:visuals.sourcesHelp")}
      >
        <div className="visuals-sources">
          <div className="visuals-source">
            <p className="visuals-source__title">
              <Icon name="folder" size={16} /> {t("admin:visuals.inbox")}
            </p>
            <code className="visuals-source__path">{packs.data?.inbox ?? "…"}</code>
            <Button
              onClick={async () => {
                const result = await run("/api/v1/admin/visuals/scan");
                if (result) {
                  const found = (result.found as Array<Record<string, unknown>>) ?? [];
                  setMessage({
                    tone: "ok",
                    text: t("admin:visuals.scanned", {
                      count: found.length,
                      fresh: found.filter((f) => f.new).length,
                    }),
                  });
                }
              }}
            >
              <Icon name="refresh" size={16} /> {t("admin:visuals.scan")}
            </Button>
          </div>
          <div className="visuals-source">
            <p className="visuals-source__title">
              <Icon name="upload" size={16} /> {t("admin:visuals.upload")}
            </p>
            <input
              ref={file}
              type="file"
              accept=".zip,application/zip"
              aria-label={t("admin:visuals.upload")}
              onChange={async (event) => {
                const chosen = event.target.files?.[0];
                if (!chosen) return;
                const result = await run(
                  `/api/v1/admin/visuals/upload?filename=${encodeURIComponent(chosen.name)}`,
                  undefined,
                  chosen,
                );
                if (result) {
                  setSelected({ pack: String(result.pack), version: String(result.version) });
                  setMessage({
                    tone: "ok",
                    text: t("admin:visuals.imported", { pack: String(result.pack) }),
                  });
                }
                if (file.current) file.current.value = "";
              }}
            />
          </div>
          <div className="visuals-source">
            <p className="visuals-source__title">
              <Icon name="link" size={16} /> {t("admin:visuals.github")}
            </p>
            <TextField
              label={t("admin:visuals.githubUrl")}
              value={github}
              onChange={(event) => setGithub(event.target.value)}
              placeholder="https://github.com/owner/repository"
            />
            <div className="ds-stack--row">
              <Button
                disabled={!github.trim()}
                onClick={async () => {
                  const result = await run("/api/v1/admin/visuals/github", { url: github.trim() });
                  if (result) {
                    setSelected({ pack: String(result.pack), version: String(result.version) });
                    setMessage({
                      tone: "ok",
                      text: t("admin:visuals.imported", { pack: String(result.pack) }),
                    });
                  }
                }}
              >
                {t("admin:visuals.githubImport")}
              </Button>
              <Button
                variant="secondary"
                onClick={async () => {
                  const result = await run("/api/v1/admin/visuals/updates");
                  if (result) setUpdates((result.updates as Array<Record<string, unknown>>) ?? []);
                }}
              >
                {t("admin:visuals.checkUpdates")}
              </Button>
            </div>
            {updates ? (
              <ul className="visuals-updates">
                {updates.length === 0 ? <li>{t("admin:visuals.noGithub")}</li> : null}
                {updates.map((u) => (
                  <li key={String(u.pack)}>
                    <strong>{String(u.pack)}</strong>{" "}
                    {u.error
                      ? String(u.error)
                      : u.update
                        ? t("admin:visuals.updateOffered", {
                            offered: param(u.offered),
                            installed: param(u.installed),
                          })
                        : t("admin:visuals.upToDate", { installed: param(u.installed) })}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      </AdminSection>

      <AdminSection title={t("admin:visuals.packs")} icon="package" flush>
        {packs.isPending ? <FunctionalState state="loading" label={t("admin:visuals.loading")} /> : null}
        {list.length === 0 && !packs.isPending ? (
          <p className="visuals-empty">{t("admin:visuals.none")}</p>
        ) : null}
        <ul className="visuals-packs">
          {list.map((pack) => (
            <PackItem
              key={pack.id}
              pack={pack}
              selected={selected}
              onSelect={(version) => setSelected({ pack: pack.id, version })}
              onSwitch={(enabled) => run(`/api/v1/admin/visuals/${pack.id}/switch`, { enabled })}
              onRollback={(version) => run(`/api/v1/admin/visuals/${pack.id}/${version}/rollback`)}
            />
          ))}
        </ul>
      </AdminSection>

      {selected ? (
        <VersionPanel
          key={`${selected.pack}@${selected.version}`}
          pack={selected.pack}
          version={selected.version}
          current={list.find((p) => p.id === selected.pack)?.current ?? null}
          run={run}
          busy={action.isPending}
        />
      ) : null}
    </AdminPage>
  );
}

function PackItem({
  pack,
  selected,
  onSelect,
  onSwitch,
  onRollback,
}: {
  pack: PackRow;
  selected: { pack: string; version: string } | null;
  onSelect: (version: string) => void;
  onSwitch: (enabled: boolean) => void;
  onRollback: (version: string) => void;
}) {
  const t = useT();
  const latest = pack.versions[0];
  const name = latest?.names?.fr || latest?.names?.en || pack.id;
  const remoteNewer =
    pack.remote && !pack.versions.some((v) => v.version === pack.remote?.version)
      ? pack.remote.version
      : null;
  return (
    <li className="visuals-pack">
      <div className="visuals-pack__head">
        <div>
          <p className="visuals-pack__name">{name}</p>
          <p className="visuals-pack__meta">
            <code>{pack.id}</code> · {t(`admin:visuals.source.${pack.source?.kind ?? "inbox"}`)}
            {pack.source?.url ? ` · ${pack.source.url}` : pack.source?.path ? ` · ${pack.source.path}` : ""}
            {latest?.author ? ` · ${latest.author}` : ""}
            {latest?.license ? ` · ${latest.license}` : ""}
          </p>
        </div>
        <div className="visuals-pack__state">
          {pack.current ? (
            <StatusBadge tone={pack.enabled ? "ok" : "neutral"}>
              {pack.enabled
                ? t("admin:visuals.live", { version: pack.current })
                : t("admin:visuals.off", { version: pack.current })}
            </StatusBadge>
          ) : (
            <StatusBadge tone="neutral">{t("admin:visuals.unpublished")}</StatusBadge>
          )}
          {remoteNewer ? (
            <StatusBadge tone="info">{t("admin:visuals.remote", { version: remoteNewer })}</StatusBadge>
          ) : null}
          {pack.current ? (
            <Button variant="secondary" onClick={() => onSwitch(!pack.enabled)}>
              <Icon name={pack.enabled ? "pause" : "play"} size={16} />
              {pack.enabled ? t("admin:visuals.switchOff") : t("admin:visuals.switchOn")}
            </Button>
          ) : null}
        </div>
      </div>
      <ul className="visuals-versions">
        {pack.versions.map((v) => (
          <li
            key={v.version}
            data-selected={(selected?.pack === pack.id && selected.version === v.version) || undefined}
          >
            <button type="button" className="visuals-version" onClick={() => onSelect(v.version)}>
              <span className="visuals-version__number">{v.version}</span>
              <StatusBadge tone={STATUS_TONE[v.status] ?? "neutral"}>
                {t(`admin:visuals.status.${v.status}`)}
              </StatusBadge>
              <span className="visuals-version__counts">
                {v.summary.blocking ? <span data-level="blocking">{v.summary.blocking}</span> : null}
                {v.summary.warning ? <span data-level="warning">{v.summary.warning}</span> : null}
                {v.summary.info ? <span data-level="info">{v.summary.info}</span> : null}
              </span>
              <span className="visuals-version__flags">
                {t("admin:visuals.elements", { count: v.summary.elements })}
                {v.summary.hd ? (
                  <span className="visuals-flag" data-flag="hd">
                    HD
                  </span>
                ) : null}
                {v.summary.script ? (
                  <span className="visuals-flag" data-flag="script">
                    {t("admin:visuals.script")}
                  </span>
                ) : null}
                {v.simulated ? <Icon name="check" size={14} /> : null}
              </span>
            </button>
            {v.status === "approved" && pack.current !== v.version ? (
              <Button variant="ghost" onClick={() => onRollback(v.version)}>
                {t("admin:visuals.rollback")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </li>
  );
}

function VersionPanel({
  pack,
  version,
  current,
  run,
  busy,
}: {
  pack: string;
  version: string;
  current: string | null;
  run: (path: string, body?: unknown) => Promise<Record<string, unknown> | null>;
  busy: boolean;
}) {
  const t = useT();
  const detail = useVersionDetail(pack, version);
  const data = detail.data;
  const [sandbox, setSandbox] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, Partial<Economy>>>({});
  const [script, setScript] = useState(false);

  // the sandbox: this version's elements installed for this page only (they win over the published ones)
  useEffect(() => {
    if (!sandbox || !data) return;
    void installElements(data.elements, "preview");
    return () => uninstallScope("preview");
  }, [sandbox, data]);

  if (!data) return <FunctionalState state="loading" label={t("admin:visuals.loading")} />;
  const summary = data.report.summary;
  const byElement = new Map<string | null, Finding[]>();
  for (const finding of data.report.items) {
    byElement.set(finding.element, [...(byElement.get(finding.element) ?? []), finding]);
  }
  const general = byElement.get(null) ?? [];
  const pending = data.status !== "approved" || current !== version;
  return (
    <AdminSection
      title={t("admin:visuals.version", { pack, version })}
      icon="clipboard"
      description={t("admin:visuals.summary", {
        blocking: summary.blocking,
        warning: summary.warning,
        info: summary.info,
      })}
      span="full"
      actions={
        <Button variant={sandbox ? "primary" : "secondary"} onClick={() => setSandbox(!sandbox)}>
          <Icon name="eye" size={16} />{" "}
          {sandbox ? t("admin:visuals.sandboxOff") : t("admin:visuals.sandboxOn")}
        </Button>
      }
    >
      {general.length ? <Findings findings={general} /> : null}
      {sandbox ? <Simulation detail={data} run={run} /> : null}
      <ul className="visuals-elements">
        {data.report.elements.map((element) => (
          <ElementCard
            key={element.product}
            element={element}
            findings={byElement.get(element.product) ?? []}
            sandbox={sandbox}
            decided={{
              ...(data.decision?.economy?.[element.product] ?? {}),
              ...(decisions[element.product] ?? {}),
            }}
            onDecide={(change) =>
              setDecisions((all) => ({
                ...all,
                [element.product]: { ...(all[element.product] ?? {}), ...change },
              }))
            }
            simulated={data.simulation?.results.find((r) => r.product === element.product)}
          />
        ))}
      </ul>
      {pending ? (
        <div className="visuals-decision">
          {summary.script ? (
            <label className="visuals-decision__script">
              <input type="checkbox" checked={script} onChange={(event) => setScript(event.target.checked)} />
              {t("admin:visuals.acceptScript")}
            </label>
          ) : null}
          {!summary.publishable ? <FunctionalState state="error" label={t("admin:visuals.blocked")} /> : null}
          <div className="ds-stack--row">
            <Button
              disabled={busy || !summary.publishable || (summary.script && !script)}
              onClick={() =>
                run(`/api/v1/admin/visuals/${pack}/${version}/approve`, {
                  economy: decisions,
                  accept_script: script,
                })
              }
            >
              <Icon name="check" size={16} /> {t("admin:visuals.approve")}
            </Button>
            {data.status === "pending" ? (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => run(`/api/v1/admin/visuals/${pack}/${version}/reject`, {})}
              >
                {t("admin:visuals.reject")}
              </Button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="visuals-decision__done">
          <Icon name="check" size={16} /> {t("admin:visuals.published")}
        </p>
      )}
    </AdminSection>
  );
}

function Findings({ findings }: { findings: Finding[] }) {
  const t = useT();
  return (
    <ul className="visuals-findings">
      {findings.map((finding, index) => (
        <li
          // biome-ignore lint/suspicious/noArrayIndexKey: findings have no identity of their own
          key={index}
          data-level={finding.level}
        >
          <StatusBadge tone={LEVEL_TONE[finding.level] ?? "neutral"}>
            {t(`admin:visuals.level.${finding.level}`)}
          </StatusBadge>
          <span>
            {t(
              `admin:visuals.check.${finding.code}`,
              Object.fromEntries(Object.entries(finding.params).map(([k, v]) => [k, param(v)])),
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The element as a shop product, to draw it as the shop does and to try it on. */
function asProduct(element: ElementReport, economy: Economy, sandbox: boolean): Product {
  const field: Record<string, string> = {
    level_up: "animation",
    effect: "effect",
    ambient: "ambient",
    profile_background: "background",
    avatar_frame: "frame",
    profile_banner: "banner",
    name_style: "style",
    level_badge: "style",
    notification_style: "style",
    notification_animation: "animation",
    palette: "palette",
    badge: "style",
    title: "style",
  };
  const key = field[element.type];
  const preview = { ...element.payload, ...(key && element.look && sandbox ? { [key]: element.look } : {}) };
  return {
    key: element.product,
    type: element.type,
    name: element.names.fr || element.names.en || element.product,
    names: element.names,
    descriptions: element.descriptions,
    rarity: economy.rarity,
    icon: economy.icon,
    price_coins: economy.price,
    preview,
    theme: element.type === "theme" ? element.look : null,
    conditions: [],
    eligibility: [],
    config_required: false,
    featured: false,
    locked: false,
    owned: false,
    poster_effect: "none",
    repeatable: false,
    state: "available",
    version: 1,
    refund_policy: { refundable: false, window_days: 0, percent: 0 },
  } as unknown as Product;
}

function ElementCard({
  element,
  findings,
  sandbox,
  decided,
  onDecide,
  simulated,
}: {
  element: ElementReport;
  findings: Finding[];
  sandbox: boolean;
  decided: Partial<Economy>;
  onDecide: (change: Partial<Economy>) => void;
  simulated: SimulationResult | undefined;
}) {
  const t = useT();
  const economy: Economy = { ...element.economy, ...decided };
  const product = asProduct(element, economy, sandbox);
  const number = (value: string) => (value.trim() === "" ? null : Math.max(0, Math.round(Number(value))));
  return (
    <li className="visuals-element">
      <div className="visuals-element__art">
        {sandbox ? (
          <ProductArt product={product} size="card" />
        ) : (
          <span className="visuals-element__off">{t("admin:visuals.sandboxHint")}</span>
        )}
      </div>
      <div className="visuals-element__body">
        <p className="visuals-element__name">
          {element.names.fr || element.names.en}
          <span className="visuals-element__type">{t(`marketplace:type.${element.type}`)}</span>
          {element.hd ? (
            <span className="visuals-flag" data-flag="hd">
              HD
            </span>
          ) : null}
          {element.script ? (
            <span className="visuals-flag" data-flag="script">
              {t("admin:visuals.script")}
            </span>
          ) : null}
        </p>
        <p className="visuals-element__meta">
          <code>{element.product}</code>
          {element.look ? (
            <>
              {" "}
              · look <code>{element.look}</code>
            </>
          ) : null}{" "}
          · {t(`admin:visuals.kind.${element.kind}`)} · {Math.ceil(element.bytes / 1024)} Ko
          {simulated ? (
            <>
              {" · "}
              {simulated.ok
                ? t("admin:visuals.simOk", { fps: simulated.fps ?? "?" })
                : t("admin:visuals.simFailed", { detail: simulated.detail ?? "" })}
            </>
          ) : null}
        </p>
        {findings.length ? <Findings findings={findings} /> : null}
        <div className="visuals-economy">
          <label>
            {t("admin:visuals.price")}
            <input
              type="number"
              min={0}
              value={economy.price ?? ""}
              onChange={(event) => onDecide({ price: number(event.target.value) })}
            />
          </label>
          <label>
            {t("admin:visuals.rarity")}
            <select value={economy.rarity} onChange={(event) => onDecide({ rarity: event.target.value })}>
              {RARITIES.map((r) => (
                <option key={r} value={r}>
                  {t(`marketplace:rarity.${r}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("admin:visuals.minLevel")}
            <input
              type="number"
              min={1}
              max={100}
              value={economy.level ?? ""}
              onChange={(event) => onDecide({ level: number(event.target.value) })}
            />
          </label>
          <label>
            {t("admin:visuals.supply")}
            <input
              type="number"
              min={1}
              value={economy.supply ?? ""}
              onChange={(event) => onDecide({ supply: number(event.target.value) })}
            />
          </label>
        </div>
        {sandbox ? (
          <div className="ds-stack--row">
            <TryOn product={product} />
          </div>
        ) : null}
      </div>
    </li>
  );
}

/** What the browser measures in the sandbox: each GPU look compiled, the frames per second while shown. */
function Simulation({
  detail,
  run,
}: {
  detail: VersionDetail;
  run: (path: string, body?: unknown) => Promise<Record<string, unknown> | null>;
}) {
  const t = useT();
  const [results, setResults] = useState<SimulationResult[] | null>(null);
  const measure = async () => {
    const out: SimulationResult[] = [];
    const [{ fxFragment }, { COMMON }] = await Promise.all([
      import("../../design-system/themes/premium/badgeFx"),
      import("../../design-system/themes/premium/shaders"),
    ]);
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl");
    for (const element of detail.elements as ExternalElement[]) {
      if (element.kind !== "glsl") {
        out.push({ product: element.product, ok: true, detail: element.kind });
        continue;
      }
      const name = fxName(element);
      const fx = externalFx(name);
      if (!gl || !fx) {
        out.push({ product: element.product, ok: false, detail: gl ? "not loaded" : "no WebGL" });
        continue;
      }
      const source = fx.ambient ? `${COMMON}${fx.body}` : fxFragment(name);
      const shader = gl.createShader(gl.FRAGMENT_SHADER);
      if (!shader) continue;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      const ok = Boolean(gl.getShaderParameter(shader, gl.COMPILE_STATUS));
      out.push({
        product: element.product,
        ok,
        ...(ok ? {} : { detail: (gl.getShaderInfoLog(shader) ?? "").slice(0, 300) }),
      });
      gl.deleteShader(shader);
    }
    // frames per second of the page while the sandbox draws everything at once
    const fps = await new Promise<number>((resolve) => {
      let frames = 0;
      const start = performance.now();
      const tick = (now: number) => {
        frames += 1;
        if (now - start < 2000) requestAnimationFrame(tick);
        else resolve(Math.round((frames * 1000) / (now - start)));
      };
      requestAnimationFrame(tick);
    });
    const measured = out.map((r) => ({ ...r, fps }));
    setResults(measured);
    await run(`/api/v1/admin/visuals/${detail.pack}/${detail.version}/simulation`, { results: measured });
  };
  return (
    <div className="visuals-simulation">
      <p>{t("admin:visuals.simulationHelp")}</p>
      <Button variant="secondary" onClick={() => void measure()}>
        <Icon name="gauge" size={16} /> {t("admin:visuals.simulate")}
      </Button>
      {results ? (
        <p className="visuals-simulation__result">
          {t("admin:visuals.simulated", {
            ok: results.filter((r) => r.ok).length,
            count: results.length,
            fps: results[0]?.fps ?? "?",
          })}
        </p>
      ) : null}
    </div>
  );
}
