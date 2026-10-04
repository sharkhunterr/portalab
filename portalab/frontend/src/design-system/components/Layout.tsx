import type { HTMLAttributes, ReactNode } from "react";
import { useEffect, useState } from "react";

/** Responsive layout primitives (spec 022 T025): logical properties, reflow at 320 px, density-aware gaps. */
export function Stack({
  row = false,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { row?: boolean }) {
  return (
    <div
      className={["ds-stack", row ? "ds-stack--row" : "", className].filter(Boolean).join(" ")}
      {...props}
    />
  );
}

export function Grid({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={["ds-grid", className].filter(Boolean).join(" ")} {...props} />;
}

export function Container({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={["ds-container", className].filter(Boolean).join(" ")} {...props} />;
}

export const BREAKPOINTS = { sm: 640, md: 768, lg: 1024 } as const;

/** ``useBreakpoint("md")`` → true when the viewport is at least that wide (SSR/test safe). */
export function useBreakpoint(name: keyof typeof BREAKPOINTS): boolean {
  const query = `(min-width: ${BREAKPOINTS[name]}px)`;
  const read = () =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(query).matches;
  const [matches, setMatches] = useState(read);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

export function List({ children, label }: { children: ReactNode; label?: string }) {
  return (
    <ul className="ds-list" aria-label={label}>
      {children}
    </ul>
  );
}

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  rowHeader?: boolean;
}

/** Table with a caption, scoped headers and horizontal scroll inside its own region (no page overflow). */
export function Table<T>({
  caption,
  columns,
  rows,
  rowKey,
}: {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
}) {
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrollable region must be keyboard-focusable (WCAG 2.1.1)
    <section className="ds-table-wrap" aria-label={caption} tabIndex={0}>
      <table className="ds-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) =>
                column.rowHeader ? (
                  <th key={column.key} scope="row">
                    {column.render(row)}
                  </th>
                ) : (
                  <td key={column.key}>{column.render(row)}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** Device class (spec 027 R19): phone < 640 px ≤ tablet < 1024 px ≤ desktop. */
export type DeviceClass = "phone" | "tablet" | "desktop";

export function useDeviceClass(): DeviceClass {
  const tablet = useBreakpoint("sm");
  const desktop = useBreakpoint("lg");
  return desktop ? "desktop" : tablet ? "tablet" : "phone";
}
