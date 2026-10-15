import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CSRF_COOKIE, CSRF_HEADER } from "../../api/client";
import { AdminPage, AdminSection, StatusBadge } from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";

/**
 * issue 1: who the intrusion guard blocked — a member's account, a session, an address — why, for how long
 * more; an administrator lifts a block (or all of them). Each block is also in the audit log.
 */
interface Block {
  key: string;
  kind: "user" | "session" | "ip";
  who?: string;
  reason?: string;
  points?: number;
  paths?: string[];
  seconds_left: number;
}

async function lift(key: string | null) {
  const token = document.cookie
    .split("; ")
    .find((part) => part.startsWith(`${CSRF_COOKIE}=`))
    ?.slice(CSRF_COOKIE.length + 1);
  const response = await fetch("/api/v1/admin/security/blocks/lift", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { [CSRF_HEADER]: decodeURIComponent(token) } : {}),
    },
    body: JSON.stringify({ key }),
  });
  if (!response.ok) throw new Error(String(response.status));
}

export default function SecurityBlocks() {
  const t = useT();
  const client = useQueryClient();
  const blocks = useQuery({
    queryKey: ["security", "blocks"],
    refetchInterval: 15_000,
    queryFn: async () => {
      const response = await fetch("/api/v1/admin/security/blocks", { credentials: "same-origin" });
      if (!response.ok) throw new Error(String(response.status));
      return ((await response.json()) as { blocks: Block[] }).blocks;
    },
  });
  const action = useMutation({
    mutationFn: lift,
    onSettled: () => client.invalidateQueries({ queryKey: ["security", "blocks"] }),
  });
  const list = blocks.data ?? [];
  return (
    <AdminPage
      icon="shield"
      title={t("admin:securityBlocks.title")}
      description={t("admin:securityBlocks.description")}
    >
      <AdminSection
        title={t("admin:securityBlocks.current", { count: list.length })}
        icon="lock"
        actions={
          list.length ? (
            <Button variant="secondary" onClick={() => action.mutate(null)}>
              {t("admin:securityBlocks.liftAll")}
            </Button>
          ) : null
        }
      >
        {blocks.isPending ? <FunctionalState state="loading" label={t("admin:visuals.loading")} /> : null}
        {!blocks.isPending && !list.length ? <p>{t("admin:securityBlocks.none")}</p> : null}
        <ul className="ds-stack" style={{ listStyle: "none", padding: 0 }}>
          {list.map((block) => (
            <li key={block.key} className="ds-stack--row" style={{ alignItems: "center", flexWrap: "wrap" }}>
              <StatusBadge tone={block.kind === "user" ? "bad" : "warn"}>
                {t(`admin:securityBlocks.kind.${block.kind}`)}
              </StatusBadge>
              <strong>{block.who ?? block.key.split(":")[1]?.slice(0, 16)}</strong>
              <span>{block.reason ?? ""}</span>
              <span>
                {t("admin:securityBlocks.left", {
                  minutes: Math.max(1, Math.round(block.seconds_left / 60)),
                })}
              </span>
              <Button variant="ghost" onClick={() => action.mutate(block.key)}>
                {t("admin:securityBlocks.lift")}
              </Button>
            </li>
          ))}
        </ul>
      </AdminSection>
    </AdminPage>
  );
}
