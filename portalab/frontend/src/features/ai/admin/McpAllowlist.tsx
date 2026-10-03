import { useEffect, useState } from "react";
import { Button } from "../../../design-system/components/Button";
import { SelectField, TextField } from "../../../design-system/components/Field";
import { useT } from "../../../i18n/hooks/useT";
import { useAiAdmin, useMcpServers } from "../api";

/**
 * MCP allow-list (spec 018 T030): each server's tools are invisible to the assistant until mapped here to
 * a portal permission and a sensitivity. Server credentials are write-only.
 */
let counter = 0;
const uid = () => `mcp-${counter++}`;

interface Entry {
  uid: string;
  tool: string;
  permission: string;
  sensitivity: "read" | "write" | "sensitive";
}
interface Server {
  uid: string;
  name: string;
  url: string;
  allowlist: Entry[];
  access: string;
  credential_set: boolean;
  state: string;
  discovered_tools: string[];
}

export function McpAllowlist() {
  const t = useT();
  const servers = useMcpServers();
  const { saveServers } = useAiAdmin();
  const [rows, setRows] = useState<Server[]>([]);
  useEffect(() => {
    if (servers.data)
      setRows(
        servers.data.map((s) => ({
          ...s,
          uid: uid(),
          allowlist: (s.allowlist as unknown as Omit<Entry, "uid">[]).map((e) => ({ ...e, uid: uid() })),
          access: "",
        })),
      );
  }, [servers.data]);
  const update = (index: number, patch: Partial<Server>) =>
    setRows(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const save = () =>
    saveServers.mutate({
      servers: rows.map(({ name, url, allowlist }) => ({
        name,
        url,
        allowlist: allowlist.map(({ tool, permission, sensitivity }) => ({ tool, permission, sensitivity })),
      })),
      credentials: Object.fromEntries(rows.filter((r) => r.access).map((r) => [r.name, r.access])),
    });
  return (
    <section aria-labelledby="ai-mcp-title">
      <h2 id="ai-mcp-title">{t("ai:mcp.title")}</h2>
      <p>{t("ai:mcp.description")}</p>
      {rows.map((row, index) => (
        <fieldset key={row.uid} className="ds-card ds-stack">
          <legend>{row.name || t("ai:mcp.addServer")}</legend>
          <TextField
            label={t("ai:mcp.name")}
            value={row.name}
            onChange={(e) => update(index, { name: e.target.value })}
          />
          <TextField
            label={t("ai:mcp.url")}
            type="url"
            value={row.url}
            onChange={(e) => update(index, { url: e.target.value })}
          />
          <TextField
            label={t("ai:mcp.access")}
            type="password"
            autoComplete="off"
            value={row.access}
            hint={row.credential_set ? t("ai:admin.accessSet") : undefined}
            onChange={(e) => update(index, { access: e.target.value })}
          />
          <p className="ai-meta">{t("ai:mcp.state", { state: row.state })}</p>
          {row.discovered_tools.length ? (
            <p className="ai-meta">
              {t("ai:mcp.discovered")}: {row.discovered_tools.join(", ")}
            </p>
          ) : null}
          {row.allowlist.map((entry, position) => (
            <div key={entry.uid} className="ds-stack--row">
              <TextField
                label={t("ai:mcp.tool")}
                value={entry.tool}
                onChange={(e) =>
                  update(index, {
                    allowlist: row.allowlist.map((x, i) =>
                      i === position ? { ...x, tool: e.target.value } : x,
                    ),
                  })
                }
              />
              <TextField
                label={t("ai:mcp.permission")}
                value={entry.permission}
                onChange={(e) =>
                  update(index, {
                    allowlist: row.allowlist.map((x, i) =>
                      i === position ? { ...x, permission: e.target.value } : x,
                    ),
                  })
                }
              />
              <SelectField
                label={t("ai:mcp.sensitivity")}
                value={entry.sensitivity}
                onChange={(e) =>
                  update(index, {
                    allowlist: row.allowlist.map((x, i) =>
                      i === position ? { ...x, sensitivity: e.target.value as Entry["sensitivity"] } : x,
                    ),
                  })
                }
              >
                {(["read", "write", "sensitive"] as const).map((value) => (
                  <option key={value} value={value}>
                    {t(`ai:admin.sensitivity.${value}`)}
                  </option>
                ))}
              </SelectField>
              <Button
                variant="secondary"
                onClick={() => update(index, { allowlist: row.allowlist.filter((_, i) => i !== position) })}
              >
                {t("ai:mcp.remove")}
              </Button>
            </div>
          ))}
          <div className="ds-stack--row">
            <Button
              variant="secondary"
              onClick={() =>
                update(index, {
                  allowlist: [
                    ...row.allowlist,
                    { uid: uid(), tool: "", permission: "", sensitivity: "sensitive" },
                  ],
                })
              }
            >
              {t("ai:mcp.addTool")}
            </Button>
            <Button variant="secondary" onClick={() => setRows(rows.filter((_, i) => i !== index))}>
              {t("ai:mcp.remove")}
            </Button>
          </div>
        </fieldset>
      ))}
      <div className="ds-stack--row">
        <Button
          variant="secondary"
          onClick={() =>
            setRows([
              ...rows,
              {
                uid: uid(),
                name: "",
                url: "",
                allowlist: [],
                access: "",
                credential_set: false,
                state: "unknown",
                discovered_tools: [],
              },
            ])
          }
        >
          {t("ai:mcp.addServer")}
        </Button>
        <Button onClick={save} disabled={saveServers.isPending}>
          {t("ai:mcp.save")}
        </Button>
      </div>
    </section>
  );
}
