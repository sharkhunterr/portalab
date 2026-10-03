import { useId } from "react";
import { Link } from "react-router";
import { Button } from "../../../design-system/components/Button";
import { FunctionalState } from "../../../design-system/state/FunctionalState";
import { useFormat } from "../../../i18n/format/useFormat";
import { useT } from "../../../i18n/hooks/useT";
import { useMyRequests, useRequestActions } from "../api";
import "../media.css";

/** My media requests (spec 024 T026): state as text, quota left (base + extra units), cancel while pending. */
const CANCELLABLE = new Set(["pending", "approved"]);

export function RequestsPage() {
  const t = useT();
  const format = useFormat();
  const headingId = useId();
  const requests = useMyRequests();
  const { cancel } = useRequestActions();
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{t("media:requests.title")}</h2>
      {requests.data ? (
        <p>
          {t("media:requests.quota", { count: Number(requests.data.quota.base_remaining ?? 0) })} ·{" "}
          {t("media:requests.extra", { count: Number(requests.data.quota.extra_units ?? 0) })}
        </p>
      ) : null}
      {requests.isPending ? <FunctionalState state="loading" /> : null}
      {requests.isError ? <FunctionalState state="unavailable" onRetry={() => requests.refetch()} /> : null}
      {requests.data && requests.data.items.length === 0 ? (
        <p>
          {t("media:requests.empty")} <Link to="/media/browse">{t("media:home.browse")}</Link>
        </p>
      ) : null}
      <ul className="media-list">
        {(requests.data?.items ?? []).map((request) => (
          <li key={request.id}>
            {request.object_id ? (
              <Link to={`/media/${request.object_id}`}>{request.title}</Link>
            ) : (
              request.title
            )}{" "}
            · {t(`media:requests.state.${request.state}`)} · {format.dateTime(request.requested_at)}{" "}
            {CANCELLABLE.has(request.state) ? (
              <Button variant="secondary" onClick={() => cancel.mutate(request.id)}>
                {t("media:requests.cancel")}
                <span className="visually-hidden">: {request.title}</span>
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default RequestsPage;
