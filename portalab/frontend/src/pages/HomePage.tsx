import { Link } from "react-router";
import { EmptyState } from "../shell/breadcrumbs/Breadcrumbs";
import { useNavigationView } from "../shell/nav/NavigationProvider";
import { label, shellStrings } from "../shell/strings";

/** Home (placeholder until the dashboard, spec 009): never a dead end — it offers the user's destinations. */
export default function HomePage() {
  const { view } = useNavigationView();
  const destinations = view.groups
    .flatMap((g) => g.entries)
    .filter((e) => e.route && e.route !== "/")
    .slice(0, 6);
  return (
    <EmptyState
      title={shellStrings.homeTitle}
      nextAction={destinations.map((entry) => (
        <Link key={entry.key} className="ds-button ds-button--secondary" to={entry.route ?? "/"}>
          {label(entry.label_key)}
        </Link>
      ))}
    >
      <p>{shellStrings.homeEmpty}</p>
    </EmptyState>
  );
}
