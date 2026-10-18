import { Button } from "../../../design-system/components/Button";
import { useT } from "../../../i18n/hooks/useT";
import type { Review } from "../api";

/**
 * Install review (spec 023 R2): everything the plugin asks for — permissions, extension points, events,
 * personal data, its own schema, code or not, checksum — before the Admin consents.
 */
export function ReviewConsent({
  review,
  onApprove,
  onCancel,
}: {
  review: Review;
  onApprove: () => void;
  onCancel: () => void;
}) {
  const t = useT();
  return (
    <section aria-labelledby="plugin-review" className="ds-card ds-stack">
      <h2 id="plugin-review">{t("plugins:review.title", { name: review.name, version: review.version })}</h2>
      <dl className="community-values">
        <div>
          <dt>{t("plugins:review.tier")}</dt>
          <dd>{review.code ? t("plugins:review.code") : t("plugins:review.declarative")}</dd>
        </div>
        <div>
          <dt>{t("plugins:review.maturity")}</dt>
          <dd>{t(`plugins:maturity.${review.maturity}`)}</dd>
        </div>
        <div>
          <dt>{t("plugins:review.personalData")}</dt>
          <dd>{review.personal_data ? t("plugins:review.yes") : t("plugins:review.no")}</dd>
        </div>
        <div>
          <dt>{t("plugins:review.schema")}</dt>
          <dd>{review.schema}</dd>
        </div>
      </dl>
      {review.runtime ? <p>{t(`plugins:confined.runtime.${review.runtime}`)}</p> : null}
      {review.requested_capabilities?.length ? (
        <>
          <h3>{t("plugins:review.capabilities")}</h3>
          <ul>
            {review.requested_capabilities.map((item) => {
              const key = `plugins:capability.${item.capability}`;
              const text = t(key);
              return <li key={item.capability}>{text === key ? item.description : text}</li>;
            })}
          </ul>
        </>
      ) : null}
      <h3>{t("plugins:review.permissions")}</h3>
      <ul>
        {review.permissions.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
      <h3>{t("plugins:review.points")}</h3>
      <p>{review.extension_points.join(", ") || t("plugins:review.none")}</p>
      <h3>{t("plugins:review.events")}</h3>
      <p>{[...review.events.produces, ...review.events.consumes].join(", ") || t("plugins:review.none")}</p>
      <p className="community-meta">SHA-256 {review.sha256}</p>
      <div className="ds-stack--row">
        <Button onClick={onApprove}>{t("plugins:review.approve")}</Button>
        <Button variant="secondary" onClick={onCancel}>
          {t("plugins:review.cancel")}
        </Button>
      </div>
    </section>
  );
}
