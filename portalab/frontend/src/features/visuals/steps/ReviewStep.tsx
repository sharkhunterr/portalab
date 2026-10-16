import { useState } from "react";
import { AdminSection } from "../../../design-system/admin/AdminKit";
import { Button } from "../../../design-system/components/Button";
import { Icon } from "../../../design-system/components/Icon";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useT } from "../../../i18n/hooks/useT";
import { type Confirmations, type Economy, packPath, useVisualAction, type VersionDetail } from "../api";
import { nameOf, RARITIES } from "../parts";
import { confirmationsNeeded, NOT_SOLD } from "./review";

/** Review: the economy each element proposes — price, rarity, level, copies — changed if wanted, and the
 * confirmations the version needs (its scripts, a look it takes over, the data a widget asks for). Saved
 * with the version (another administrator sees the same review). */
export function ReviewStep({ detail, onSaved }: { detail: VersionDetail; onSaved: () => void }) {
  const t = useT();
  const action = useVisualAction();
  const closed = detail.step === "published" || detail.step === "refused" || detail.step === "purged";
  const [economy, setEconomy] = useState<Record<string, Partial<Economy>>>(() => ({
    ...(detail.decision?.economy ?? {}),
    ...(detail.draft?.economy ?? {}),
  }));
  const needed = confirmationsNeeded(detail);
  const [confirmations, setConfirmations] = useState<Confirmations>(() => ({
    scripts: Boolean(detail.draft?.confirmations?.scripts),
    replaces: detail.draft?.confirmations?.replaces ?? [],
    contracts: detail.draft?.confirmations?.contracts ?? [],
  }));
  const [error, setError] = useState<string | null>(null);
  // 028: the booster scenes, bound to every booster (« * »), one booster (its key) or none
  const scenes = detail.report.elements.filter((e) => e.type === "booster_scene" && e.look);
  const [modes, setModes] = useState<Record<string, "all" | "one" | "none">>({});
  const [bindings, setBindings] = useState<Record<string, string>>(() => ({
    ...Object.fromEntries(scenes.map((s) => [s.look as string, "*"])),
    ...((detail.draft as { bindings?: Record<string, string> } | null)?.bindings ?? {}),
  }));
  const number = (value: string) => (value.trim() === "" ? null : Math.max(0, Math.round(Number(value))));
  const decide = (product: string, change: Partial<Economy>) =>
    setEconomy((all) => ({ ...all, [product]: { ...(all[product] ?? {}), ...change } }));
  const toggle = (list: "replaces" | "contracts", value: string, on: boolean) =>
    setConfirmations((all) => ({
      ...all,
      [list]: on ? [...new Set([...all[list], value])] : all[list].filter((x) => x !== value),
    }));
  const sold = detail.report.elements.filter((e) => !NOT_SOLD.has(e.type));

  const save = async () => {
    setError(null);
    try {
      await action.mutateAsync({
        path: `${packPath(detail.pack, detail.version)}/draft`,
        method: "PUT",
        body: { economy, confirmations, bindings },
      });
      onSaved();
    } catch (failure) {
      setError(String((failure as Error).message));
    }
  };

  return (
    <>
      <AdminSection title={t("admin:visuals.review.economy")} icon="coins" flush>
        <section className="visuals-economy-table" aria-label={t("admin:visuals.review.economy")}>
          <table>
            <thead>
              <tr>
                <th scope="col">{t("admin:visuals.review.element")}</th>
                <th scope="col">{t("admin:visuals.price")}</th>
                <th scope="col">{t("admin:visuals.rarity")}</th>
                <th scope="col">{t("admin:visuals.minLevel")}</th>
                <th scope="col">{t("admin:visuals.supply")}</th>
              </tr>
            </thead>
            <tbody>
              {sold.map((element) => {
                const decided: Economy = { ...element.economy, ...(economy[element.product] ?? {}) };
                const label = nameOf(element.names, element.product);
                const changed = (field: keyof Economy) =>
                  decided[field] !== element.economy[field] || undefined;
                return (
                  <tr key={element.product}>
                    <th scope="row">
                      {label}
                      <span className="visuals-element__type">{t(`admin:visuals.type.${element.type}`)}</span>
                    </th>
                    <td data-changed={changed("price")}>
                      <input
                        type="number"
                        min={0}
                        disabled={closed}
                        aria-label={`${t("admin:visuals.price")} — ${label}`}
                        value={decided.price ?? ""}
                        placeholder={t("admin:visuals.review.rewardOnly")}
                        onChange={(event) => decide(element.product, { price: number(event.target.value) })}
                      />
                    </td>
                    <td data-changed={changed("rarity")}>
                      <select
                        disabled={closed}
                        aria-label={`${t("admin:visuals.rarity")} — ${label}`}
                        value={decided.rarity}
                        onChange={(event) => decide(element.product, { rarity: event.target.value })}
                      >
                        {RARITIES.map((r) => (
                          <option key={r} value={r}>
                            {t(`marketplace:rarity.${r}`)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td data-changed={changed("level")}>
                      <input
                        type="number"
                        min={1}
                        max={100}
                        disabled={closed}
                        aria-label={`${t("admin:visuals.minLevel")} — ${label}`}
                        value={decided.level ?? ""}
                        onChange={(event) => decide(element.product, { level: number(event.target.value) })}
                      />
                    </td>
                    <td data-changed={changed("supply")}>
                      <input
                        type="number"
                        min={1}
                        disabled={closed}
                        aria-label={`${t("admin:visuals.supply")} — ${label}`}
                        value={decided.supply ?? ""}
                        placeholder="∞"
                        onChange={(event) => decide(element.product, { supply: number(event.target.value) })}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </AdminSection>
      {scenes.length ? (
        <AdminSection title={t("admin:visuals.review.scenes")} icon="gift">
          <div className="visuals-confirmations">
            {scenes.map((scene) => {
              const look = scene.look as string;
              const value = bindings[look] ?? "";
              const mode = modes[look] ?? (value === "*" ? "all" : value ? "one" : "none");
              return (
                <label key={look}>
                  {nameOf(scene.names, look)}
                  <select
                    disabled={closed}
                    value={mode}
                    onChange={(event) => {
                      const next = event.target.value as "all" | "one" | "none";
                      setModes((all) => ({ ...all, [look]: next }));
                      setBindings((all) => ({ ...all, [look]: next === "all" ? "*" : "" }));
                    }}
                  >
                    <option value="all">{t("admin:visuals.review.sceneAll")}</option>
                    <option value="one">{t("admin:visuals.review.sceneOne")}</option>
                    <option value="none">{t("admin:visuals.review.sceneNone")}</option>
                  </select>
                  {mode === "one" ? (
                    <input
                      type="text"
                      disabled={closed}
                      aria-label={t("admin:visuals.review.sceneBooster")}
                      placeholder={t("admin:visuals.review.sceneBooster")}
                      value={value}
                      onChange={(event) =>
                        setBindings((all) => ({ ...all, [look]: event.target.value.trim() }))
                      }
                    />
                  ) : null}
                </label>
              );
            })}
          </div>
        </AdminSection>
      ) : null}
      {needed.scripts || needed.replaces.length || needed.contracts.length ? (
        <AdminSection title={t("admin:visuals.review.confirmations")} icon="shield">
          <div className="visuals-confirmations">
            {needed.scripts ? (
              <label>
                <input
                  type="checkbox"
                  disabled={closed}
                  checked={confirmations.scripts}
                  onChange={(event) => setConfirmations((all) => ({ ...all, scripts: event.target.checked }))}
                />
                {t("admin:visuals.acceptScript")}
              </label>
            ) : null}
            {needed.replaces.map((value) => (
              <label key={value}>
                <input
                  type="checkbox"
                  disabled={closed}
                  checked={confirmations.replaces.includes(value)}
                  onChange={(event) => toggle("replaces", value, event.target.checked)}
                />
                {t("admin:visuals.review.replace", { look: value.split(":")[1] ?? value })}
              </label>
            ))}
            {needed.contracts.map((value) => (
              <label key={value}>
                <input
                  type="checkbox"
                  disabled={closed}
                  checked={confirmations.contracts.includes(value)}
                  onChange={(event) => toggle("contracts", value, event.target.checked)}
                />
                {t("admin:visuals.review.contract", { contract: value })}
              </label>
            ))}
          </div>
        </AdminSection>
      ) : null}
      {error ? <FunctionalState state="error" label={error} /> : null}
      {!closed ? (
        <div className="ds-stack--row">
          <Button disabled={action.isPending} onClick={() => void save()}>
            <Icon name="check" size={16} /> {t("admin:visuals.review.save")}
          </Button>
        </div>
      ) : null}
    </>
  );
}
