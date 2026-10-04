import type { ReactNode } from "react";
import { Button } from "./Button";
import { Icon } from "./Icon";

/**
 * Loading and empty placeholders (spec 027 FR-025/FR-026): skeletons shaped like the coming content, and
 * empty states that always offer a next action (no dead end, constitution X).
 */

export type SkeletonShape = "text" | "card" | "tile" | "list" | "figure";

export function Skeleton({
  shape = "text",
  count = 1,
  label,
}: {
  shape?: SkeletonShape;
  count?: number;
  label: string;
}) {
  return (
    <div className="ds-skeleton-group" data-shape={shape} aria-busy="true" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      {Array.from({ length: count }, (_, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
        <span key={index} className={`ds-skeleton ds-skeleton--${shape}`} aria-hidden="true" />
      ))}
    </div>
  );
}

export interface EmptyStateAction {
  label: string;
  onSelect?: () => void;
  href?: string;
}

export interface EmptyStateProps {
  icon?: string;
  title: string;
  message?: ReactNode;
  /** Required: an empty state always leads somewhere. */
  action: EmptyStateAction | ReactNode;
}

function isAction(value: unknown): value is EmptyStateAction {
  return typeof value === "object" && value !== null && "label" in value && !("$$typeof" in value);
}

export function EmptyState({ icon = "sparkles", title, message, action }: EmptyStateProps) {
  return (
    <div className="ds-empty" role="status">
      <span className="ds-empty__art" aria-hidden="true">
        <Icon name={icon} size={40} />
      </span>
      <p className="ds-empty__title">{title}</p>
      {message ? <p className="ds-empty__message">{message}</p> : null}
      <div className="ds-empty__action">
        {isAction(action) ? (
          action.href ? (
            <a className="ds-button ds-button--primary" href={action.href}>
              {action.label}
            </a>
          ) : (
            <Button variant="primary" onClick={action.onSelect}>
              {action.label}
            </Button>
          )
        ) : (
          action
        )}
      </div>
    </div>
  );
}
