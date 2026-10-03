import { Link } from "react-router";
import { useT } from "../../../i18n/hooks/useT";
import { useIncidents } from "./api";

/**
 * Open incidents banner (spec 016 T013): shown above the page content while incidents are open, so users
 * know before opening a ticket (fewer duplicates). Silent when there is none or when incidents are not
 * available — never a page error.
 */
export function IncidentBanner() {
  const t = useT();
  const open = useIncidents("open");
  const incidents = open.data ?? [];
  if (!incidents.length) return null;
  const [first] = incidents;
  return (
    <section
      className="incident-banner"
      aria-label={t("support:incident.banner")}
      data-severity={first?.severity}
    >
      <p>
        <strong>{t("support:incident.banner")}</strong>{" "}
        {incidents.length === 1 && first ? (
          <Link to={`/incidents/${first.id}`}>
            {first.reference} · {first.title}
          </Link>
        ) : (
          <Link to="/incidents">{t("support:incident.count", { count: incidents.length })}</Link>
        )}
      </p>
    </section>
  );
}
