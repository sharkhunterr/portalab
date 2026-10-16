import type { ReactNode } from "react";
import { AdminSection } from "../../design-system/admin/AdminKit";
import { Icon } from "../../design-system/components/Icon";
import "./extensions.css";

/**
 * 028 (issue 138): the « Import » section every tab of Extensions opens with — its sources side by side, each
 * a compact tile (an icon, a name, one line), acting at once (a folder read again, a file chosen) or opening
 * what it needs (an address to give). What came of the last import is said under them.
 */
export interface ImportSource {
  key: string;
  icon: string;
  label: string;
  hint?: string | undefined;
  /** the tile itself: a button, a file picker, a dialog's trigger — given by the tab */
  render: (tile: { className: string; children: ReactNode }) => ReactNode;
}

export function ImportPanel({
  title,
  description,
  sources,
  children,
}: {
  title: string;
  description?: string;
  sources: ImportSource[];
  /** what the last import gave, the packages found… */
  children?: ReactNode;
}) {
  return (
    <AdminSection title={title} icon="download" description={description}>
      <ul className="ext-import ext-import__list">
        {sources.map((source) => (
          <li key={source.key}>
            {source.render({
              className: "ext-import__tile",
              children: (
                <>
                  <span className="ext-import__icon" aria-hidden="true">
                    <Icon name={source.icon} size={18} />
                  </span>
                  <span className="ext-import__text">
                    <strong>{source.label}</strong>
                    {source.hint ? <span>{source.hint}</span> : null}
                  </span>
                </>
              ),
            })}
          </li>
        ))}
      </ul>
      {children}
    </AdminSection>
  );
}
