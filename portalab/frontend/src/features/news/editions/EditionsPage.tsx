import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { Icon } from "../../../design-system/components/Icon";
import { PageHeader } from "../../../design-system/components/PageHeader";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useEdition } from "./api";
import "./editions.css";

/** issue 316: an edition shown in the portal exactly as it was e-mailed — its own page, framed and confined
 * (no script, its links open in the portal). Issue 335: ``fit`` — as tall as the letter, read with the page
 * (no script in it still: the portal measures it). */
export function EditionFrame({ src, title, fit = false }: { src: string; title: string; fit?: boolean }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState<number | null>(null);
  const observer = useRef<ResizeObserver | null>(null);
  useEffect(() => () => observer.current?.disconnect(), []);
  const measure = () => {
    const page = frame.current?.contentDocument?.documentElement;
    if (!fit || !page) return;
    const update = () => setHeight(page.scrollHeight);
    update();
    observer.current?.disconnect();
    observer.current = new ResizeObserver(update);
    observer.current.observe(page);
  };
  return (
    <iframe
      ref={frame}
      className="edition-frame"
      data-fit={fit || undefined}
      src={src}
      title={title}
      style={height ? { blockSize: `${height}px` } : undefined}
      onLoad={measure}
      sandbox={`allow-popups allow-top-navigation-by-user-activation${fit ? " allow-same-origin" : ""}`}
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
      <EditionFrame src={`/api/v1/news/editions/${editionId}/page`} title={edition.data.title} fit />
    </section>
  );
}
