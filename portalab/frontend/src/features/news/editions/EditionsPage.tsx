import { Link, useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { EmptyState } from "../../../design-system/components/Placeholders";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useEdition, useEditions } from "./api";
import "./editions.css";

/** issue 316: an edition shown in the portal exactly as it was e-mailed — its own page, framed and confined
 * (no script, its links open in the portal). */
export function EditionFrame({ src, title }: { src: string; title: string }) {
  return (
    <iframe
      className="edition-frame"
      src={src}
      title={title}
      sandbox="allow-popups allow-top-navigation-by-user-activation"
    />
  );
}

/** ``/news/editions``: the published editions of the self-writing newsletters, the latest first. */
export default function EditionsPage() {
  const t = useT();
  const format = useFormat();
  const editions = useEditions();
  const items = editions.data ?? [];
  return (
    <section className="ds-stack editions-page">
      <PageHeader icon="mail" title={t("news:edition.page.title")} context={t("news:edition.page.intro")} />
      {editions.isPending ? <FunctionalState state="loading" /> : null}
      {editions.isError ? <FunctionalState state="error" onRetry={() => editions.refetch()} /> : null}
      {editions.isSuccess && !items.length ? (
        <EmptyState
          icon="mail"
          title={t("news:edition.page.empty")}
          message={t("news:edition.page.emptyHint")}
          action={{ label: t("news:edition.page.toNews"), href: "/news" }}
        />
      ) : null}
      <ul className="editions-list">
        {items.map((edition, index) => (
          <li key={edition.id} data-latest={index === 0 || undefined}>
            <Link to={`/news/editions/${edition.id}`} className="editions-list__card">
              <span className="editions-list__icon" aria-hidden="true">
                <Icon name="mail" size={20} />
              </span>
              <span className="editions-list__text">
                <strong>{edition.title}</strong>
                {edition.preheader ? <span>{edition.preheader}</span> : null}
                <small>
                  {edition.published_at ? format.date(edition.published_at, "long") : null}
                  {index === 0 ? ` · ${t("news:edition.page.latest")}` : ""}
                </small>
              </span>
              <Icon name="chevron-right" size={18} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** ``/news/editions/:editionId``: one edition, as it was e-mailed. */
export function EditionPage() {
  const t = useT();
  const format = useFormat();
  const { editionId = "" } = useParams();
  const edition = useEdition(editionId);
  if (edition.isPending) return <FunctionalState state="loading" />;
  if (edition.isError || !edition.data)
    return <FunctionalState state="unavailable" onRetry={() => edition.refetch()} />;
  return (
    <section className="ds-stack edition-page">
      <PageHeader
        icon="mail"
        title={edition.data.title}
        context={edition.data.published_at ? format.date(edition.data.published_at, "long") : undefined}
      />
      <Link to="/news/editions" className="edition-page__back">
        <Icon name="chevron-left" size={16} />
        {t("news:edition.page.all")}
      </Link>
      <EditionFrame src={`/api/v1/news/editions/${editionId}/page`} title={edition.data.title} />
    </section>
  );
}
