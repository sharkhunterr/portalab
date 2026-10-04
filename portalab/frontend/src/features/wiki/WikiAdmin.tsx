import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/client";
import {
  AdminPage,
  AdminSection,
  AdminStats,
  AdminTable,
  AdminTabs,
  AdminToolbar,
  SearchBox,
  StatusBadge,
  type Tone,
} from "../../design-system/admin/AdminKit";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useFormat } from "../../i18n/format/useFormat";
import { useT } from "../../i18n/hooks/useT";
import { type TreeNode, useTree } from "./api";

/**
 * Wiki administration (027 hubs, Support): every page with its place in the tree and its state, filtered
 * and searchable; publish, unpublish or archive in one click, open, edit or see the history; and the
 * broken internal links to fix. Writing stays on the wiki pages themselves.
 */
interface Row {
  node: TreeNode;
  path: string;
}

const TONE: Record<string, Tone> = { published: "ok", draft: "info", archived: "neutral", deleted: "bad" };

function rows(nodes: TreeNode[], parent = ""): Row[] {
  return nodes.flatMap((node) => {
    const path = parent ? `${parent} › ${node.title}` : node.title;
    return [{ node, path: parent }, ...rows(node.children, path)];
  });
}

export default function WikiAdmin() {
  const t = useT();
  const format = useFormat();
  const client = useQueryClient();
  const tree = useTree();
  const broken = useQuery({
    queryKey: ["wiki", "broken-links"],
    retry: false,
    queryFn: async () =>
      ((await api.GET("/api/v1/admin/wiki/broken-links")).data ?? []) as Array<Record<string, string>>,
  });
  const act = useMutation({
    mutationFn: async ({ id, action }: { id: string; action: "publish" | "archive" | "unpublish" }) =>
      api.POST("/api/v1/wiki/pages/{page_id}/{action}", { params: { path: { page_id: id, action } } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["wiki"] }),
  });
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const all = rows(tree.data ?? []);
  const count = (s: string) => all.filter((r) => r.node.status === s).length;
  const needle = query.trim().toLowerCase();
  const shown = all.filter(
    (r) =>
      (status === "all" || r.node.status === status) &&
      (!needle || r.node.title.toLowerCase().includes(needle)),
  );
  return (
    <AdminPage
      icon="book"
      title={t("wiki:admin.title")}
      description={t("wiki:admin.subtitle")}
      primary={
        <Link className="ds-button ds-button--primary" to="/wiki/new">
          <Icon name="plus" size={16} />
          {t("wiki:new")}
        </Link>
      }
    >
      <AdminStats
        label={t("wiki:admin.title")}
        stats={[
          {
            key: "pages",
            label: t("wiki:admin.pages"),
            value: format.number(all.length),
            icon: "book",
            tone: "info",
          },
          {
            key: "published",
            label: t("wiki:status.published"),
            value: format.number(count("published")),
            icon: "check",
            tone: "ok",
          },
          {
            key: "drafts",
            label: t("wiki:status.draft"),
            value: format.number(count("draft")),
            icon: "settings",
            tone: count("draft") ? "info" : "neutral",
          },
          {
            key: "broken",
            label: t("wiki:admin.broken"),
            value: format.number((broken.data ?? []).length),
            icon: "link",
            tone: (broken.data ?? []).length ? "warn" : "ok",
          },
        ]}
      />
      <AdminSection title={t("wiki:admin.pages")} icon="book" flush>
        <div className="config-toolbar">
          <AdminToolbar>
            <SearchBox label={t("wiki:search")} value={query} onChange={setQuery} />
          </AdminToolbar>
          <AdminTabs
            label={t("wiki:admin.pages")}
            current={status}
            onChange={setStatus}
            tabs={[
              { key: "all", label: t("wiki:admin.all"), count: all.length },
              ...(["published", "draft", "archived"] as const).map((s) => ({
                key: s,
                label: t(`wiki:status.${s}`),
                count: count(s),
              })),
            ]}
          />
        </div>
        <AdminTable<Row>
          label={t("wiki:admin.pages")}
          rows={shown}
          rowKey={(r) => r.node.id}
          empty={<p className="admin-muted admin-pad">{t("wiki:empty")}</p>}
          columns={[
            {
              key: "title",
              header: t("wiki:pageTitle"),
              primary: true,
              render: (r) => (
                <span className="services-admin__name">
                  <Link to={`/wiki/${r.node.slug}`}>{r.node.title}</Link>
                  {r.path ? <span className="admin-muted">{r.path}</span> : null}
                </span>
              ),
            },
            {
              key: "status",
              header: t("wiki:admin.state"),
              render: (r) => (
                <StatusBadge tone={TONE[r.node.status] ?? "neutral"}>
                  {t(`wiki:status.${r.node.status}`)}
                </StatusBadge>
              ),
            },
          ]}
          actions={(r) => (
            <>
              <Link
                className="ds-button ds-button--ghost"
                to={`/wiki/${r.node.slug}/edit`}
                aria-label={`${t("wiki:edit")} ${r.node.title}`}
              >
                {t("wiki:edit")}
              </Link>
              <Link
                className="ds-button ds-button--ghost"
                to={`/wiki/${r.node.slug}/history`}
                aria-label={`${t("wiki:history")} ${r.node.title}`}
              >
                <Icon name="clock" size={16} />
              </Link>
              {r.node.status === "draft" ? (
                <Button variant="secondary" onClick={() => act.mutate({ id: r.node.id, action: "publish" })}>
                  {t("wiki:publish")}
                </Button>
              ) : null}
              {r.node.status === "published" ? (
                <Button variant="ghost" onClick={() => act.mutate({ id: r.node.id, action: "archive" })}>
                  {t("wiki:admin.archive")}
                </Button>
              ) : null}
              {r.node.status === "archived" ? (
                <Button variant="ghost" onClick={() => act.mutate({ id: r.node.id, action: "unpublish" })}>
                  {t("wiki:admin.toDraft")}
                </Button>
              ) : null}
            </>
          )}
        />
      </AdminSection>
      {(broken.data ?? []).length ? (
        <AdminSection title={t("wiki:admin.broken")} icon="link" flush>
          <ul className="admin-list">
            {(broken.data ?? []).map((link, index) => (
              <li key={`${link.page ?? index}-${link.target ?? index}`}>
                <span className="admin-list__main">
                  <strong>{link.title ?? link.page}</strong>
                  <span className="admin-muted">→ {link.target ?? link.link}</span>
                </span>
              </li>
            ))}
          </ul>
        </AdminSection>
      ) : null}
    </AdminPage>
  );
}
