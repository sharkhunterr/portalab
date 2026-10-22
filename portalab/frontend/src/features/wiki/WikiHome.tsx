import { useId, useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../design-system/components/Icon";
import { PageHeader } from "../../design-system/components/PageHeader";
import { EmptyState } from "../../design-system/components/Placeholders";
import { FunctionalState } from "../../design-system/state/FunctionalState";
import { useT } from "../../i18n/hooks/useT";
import { useHasPermission } from "../authz/useMyPermissions";
import { type TreeNode, useTree } from "./api";
import { flatten, groupsOf, type WikiGroup } from "./WikiTree";
import "./wiki.css";

/**
 * Wiki home (spec 011 T016, 027 T095): "New page" for those who may write, a title filter, and the wiki as
 * groups — each section (a top-level page with sub-pages) a coloured block of page cards that folds away,
 * the top-level pages without sub-pages gathered last. The viewer only receives the pages they may read.
 */
const TONES = 5;
const FOLDED = "portalab.wiki.folded";

function readFolded(): string[] {
  try {
    return JSON.parse(localStorage.getItem(FOLDED) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function PageCard({ node, index }: { node: TreeNode; index: number }) {
  const t = useT();
  const below = flatten(node.children).length;
  return (
    <li>
      <Link className="wiki-card" to={`/wiki/${node.slug}`}>
        <span className="wiki-card__number" aria-hidden="true">
          {index}
        </span>
        <span className="wiki-card__text">
          <span className="wiki-card__title">
            {node.title}
            {node.status !== "published" ? (
              <span className="ds-badge wiki-badge">{t(`wiki:status.${node.status}`)}</span>
            ) : null}
          </span>
          {node.summary ? <span className="wiki-card__summary">{node.summary}</span> : null}
          {below ? <span className="wiki-meta">{t("wiki:subpages", { count: below })}</span> : null}
        </span>
      </Link>
    </li>
  );
}

function Group({
  group,
  tone,
  folded,
  onToggle,
}: {
  group: WikiGroup;
  tone: number;
  folded: boolean;
  onToggle: () => void;
}) {
  const t = useT();
  const bodyId = useId();
  const title = group.root?.title ?? t("wiki:loose");
  const cards = group.root ? group.root.children : group.pages;
  return (
    <section className="wiki-group" data-tone={tone} aria-label={title}>
      <header className="wiki-group__head">
        <span className="wiki-group__icon" aria-hidden="true">
          <Icon name="book" size={20} />
        </span>
        <span className="wiki-group__text">
          <h3 className="wiki-group__title">
            {group.root ? <Link to={`/wiki/${group.root.slug}`}>{title}</Link> : title}
          </h3>
          {group.root?.summary ? <span className="wiki-card__summary">{group.root.summary}</span> : null}
        </span>
        <button
          type="button"
          className="wiki-group__toggle"
          aria-expanded={!folded}
          aria-controls={bodyId}
          aria-label={t("wiki:toggle", { title })}
          onClick={onToggle}
        >
          <span className="wiki-meta">{t("wiki:pageCount", { count: cards.length })}</span>
          <Icon name="chevron-down" size={18} />
        </button>
      </header>
      <ul id={bodyId} className="wiki-cards" hidden={folded}>
        {cards.map((node, index) => (
          <PageCard key={node.id} node={node} index={index + 1} />
        ))}
      </ul>
    </section>
  );
}

export function WikiHome() {
  const t = useT();
  const headingId = useId();
  const tree = useTree();
  const canWrite = useHasPermission("wiki.edit");
  const [query, setQuery] = useState("");
  const [folded, setFolded] = useState<string[]>(readFolded);
  const toggle = (key: string) =>
    setFolded((current) => {
      const next = current.includes(key) ? current.filter((k) => k !== key) : [...current, key];
      try {
        localStorage.setItem(FOLDED, JSON.stringify(next));
      } catch {
        // a remembered fold is a convenience
      }
      return next;
    });
  const needle = query.trim().toLowerCase();
  const matches = needle
    ? flatten(tree.data ?? []).filter((node) => node.title.toLowerCase().includes(needle))
    : [];
  return (
    <section aria-labelledby={headingId} className="wiki-home">
      <PageHeader
        titleId={headingId}
        level={2}
        icon="book"
        title={t("wiki:title")}
        context={t("wiki:subtitle")}
        primary={
          canWrite ? (
            <Link className="ds-button ds-button--primary" to="/wiki/new">
              <Icon name="plus" size={18} />
              {t("wiki:new")}
            </Link>
          ) : undefined
        }
      />
      {tree.isPending ? <FunctionalState state="loading" /> : null}
      {tree.isError ? <FunctionalState state="unavailable" onRetry={() => tree.refetch()} /> : null}
      {tree.data && tree.data.length === 0 ? (
        <EmptyState
          icon="book"
          title={t("wiki:empty")}
          action={
            canWrite ? (
              <Link className="ds-button ds-button--primary" to="/wiki/new">
                {t("wiki:new")}
              </Link>
            ) : undefined
          }
        />
      ) : null}
      {tree.data?.length ? (
        <>
          <label className="wiki-search">
            <Icon name="search" size={18} />
            <span className="visually-hidden">{t("wiki:search")}</span>
            <input
              type="search"
              value={query}
              placeholder={t("wiki:search")}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {needle ? (
            matches.length ? (
              <ul className="wiki-results" aria-label={t("wiki:search")}>
                {matches.map((node) => (
                  <li key={node.id}>
                    <Link to={`/wiki/${node.slug}`}>
                      <Icon name="book" size={16} />
                      {node.title}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="wiki-meta">{t("wiki:noMatch", { query })}</p>
            )
          ) : (
            <nav aria-label={t("wiki:tree")} className="wiki-groups">
              {groupsOf(tree.data).map((group, index) => {
                const key = group.root?.id ?? "loose";
                return (
                  <Group
                    key={key}
                    group={group}
                    tone={index % TONES}
                    folded={folded.includes(key)}
                    onToggle={() => toggle(key)}
                  />
                );
              })}
            </nav>
          )}
        </>
      ) : null}
    </section>
  );
}

export default WikiHome;
