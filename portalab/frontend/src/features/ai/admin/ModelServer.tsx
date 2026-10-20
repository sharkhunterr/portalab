import { SelectField, TextField } from "../../../design-system/components/Field";
import { Icon } from "../../../design-system/components/Icon";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { type AiModel, type AiModelServer, useAiServers } from "../api";

type Values = Record<string, unknown>;
const MANUAL = "";

/**
 * Issue 169 — where the assistant thinks: a model server of the connected services (Ollama, added in
 * Administration › Services) and one of its chat models — its size, what is in memory, whether it can use
 * the portal's tools — or an address typed by hand (any OpenAI-compatible server).
 */
export function ModelServer({ values, onChange }: { values: Values; onChange: (next: Values) => void }) {
  const t = useT();
  const format = useFormat();
  const servers = useAiServers().data ?? [];
  const gigabytes = (bytes: number | null | undefined) =>
    bytes
      ? t("ai:admin.server.size", { size: format.number(Math.round((bytes / 1024 ** 3) * 10) / 10) })
      : "";
  const endpoint = String(values.provider_endpoint ?? "");
  const model = String(values.provider_model ?? "");
  const current: AiModelServer | undefined = servers.find((s) => s.endpoint === endpoint);
  const chat = (current?.models ?? []).filter((m) => !m.embedding);
  const label = (m: AiModel) =>
    [
      m.name,
      m.parameters,
      m.quantization,
      m.loaded ? t("ai:admin.server.loaded", { size: gigabytes(m.vram_bytes) }) : null,
      m.tools === false ? t("ai:admin.server.noTools") : null,
    ]
      .filter(Boolean)
      .join(" · ");
  const chosen = chat.find((m) => m.name === model);
  return (
    <fieldset className="ai-server">
      <legend>
        <Icon name="brain" size={16} /> {t("ai:admin.server.title")}
      </legend>
      {servers.length ? (
        <SelectField
          label={t("ai:admin.server.label")}
          hint={t("ai:admin.server.hint")}
          value={current ? current.service_id : MANUAL}
          onChange={(event) => {
            const next = servers.find((s) => s.service_id === event.target.value);
            if (!next) return;
            const keep = next.models.some((m) => m.name === model && !m.embedding);
            const loaded = next.models.find((m) => m.loaded && !m.embedding && m.tools !== false);
            onChange({
              ...values,
              // a little reflection: a small model then tells which question a page is about, and uses its tools
              provider_reasoning: values.provider_reasoning || "low",
              provider_endpoint: next.endpoint,
              provider_model: keep
                ? model
                : (loaded?.name ?? next.models.find((m) => !m.embedding)?.name ?? ""),
            });
          }}
        >
          <option value={MANUAL}>{t("ai:admin.server.manual")}</option>
          {servers.map((server) => (
            <option key={server.service_id} value={server.service_id}>
              {server.state === "ok" ? server.name : `${server.name} — ${t("ai:admin.server.unavailable")}`}
            </option>
          ))}
        </SelectField>
      ) : (
        <p className="admin-muted">{t("ai:admin.server.none")}</p>
      )}
      {current ? (
        <SelectField
          label={t("ai:admin.model")}
          hint={chosen?.tools === false ? t("ai:admin.server.noToolsHint") : t("ai:admin.server.modelHint")}
          value={model}
          onChange={(event) => onChange({ ...values, provider_model: event.target.value })}
        >
          {chosen || !model ? null : <option value={model}>{model}</option>}
          {chat.map((m) => (
            <option key={m.name} value={m.name}>
              {label(m)}
            </option>
          ))}
        </SelectField>
      ) : (
        <>
          <TextField
            label={t("ai:admin.endpoint")}
            type="url"
            value={endpoint}
            onChange={(event) => onChange({ ...values, provider_endpoint: event.target.value })}
          />
          <TextField
            label={t("ai:admin.model")}
            value={model}
            onChange={(event) => onChange({ ...values, provider_model: event.target.value })}
          />
        </>
      )}
      <SelectField
        label={t("ai:admin.server.reasoning")}
        hint={t("ai:admin.server.reasoningHint")}
        value={String(values.provider_reasoning ?? "")}
        onChange={(event) => onChange({ ...values, provider_reasoning: event.target.value })}
      >
        {["", "none", "low", "medium", "high"].map((level) => (
          <option key={level} value={level}>
            {t(`ai:admin.server.reasoning.${level || "default"}`)}
          </option>
        ))}
      </SelectField>
      {current?.models.some((m) => m.loaded) ? (
        <p className="admin-muted">
          {t("ai:admin.server.inMemory", {
            models: current.models
              .filter((m) => m.loaded)
              .map((m) => `${m.name} (${gigabytes(m.vram_bytes)})`)
              .join(", "),
          })}
        </p>
      ) : null}
    </fieldset>
  );
}
