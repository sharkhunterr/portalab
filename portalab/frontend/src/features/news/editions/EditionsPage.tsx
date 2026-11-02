import { Link, useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useEdition } from "./api";
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

/** ``/news/editions/:editionId``: one edition, as it was e-mailed — issue 335: back to the news, where it is
 * one of them. */
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
      <Link to="/news" className="edition-page__back">
        <Icon name="chevron-left" size={16} />
        {t("news:back")}
      </Link>
      <EditionFrame src={`/api/v1/news/editions/${editionId}/page`} title={edition.data.title} />
    </section>
  );
}
