import type { ReactNode } from "react";

/**
 * Responsive grid (spec 009 T033; R4): 12 columns on large containers, 6 on medium, one column on small —
 * always in the stored order, so reading order = DOM order = layout order. Sizes come from each widget's
 * ``--widget-w`` / ``--widget-h`` (see dashboard.css, container queries).
 */
export function ResponsiveGrid({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="dashboard-grid-container">
      <ol className="dashboard-grid" aria-label={label}>
        {children}
      </ol>
    </div>
  );
}

export function GridCell({ w, children }: { w: number; children: ReactNode }) {
  return (
    <li className="dashboard-grid__cell" data-w={Math.max(1, Math.min(12, w))}>
      {children}
    </li>
  );
}
