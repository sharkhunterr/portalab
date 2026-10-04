import { useState } from "react";

/**
 * ``Avatar`` (spec 027 FR-001, edge "avatar fails to load"): the image when there is one, else the
 * initials on a hue derived from the user id — stable across sessions and devices. A broken image falls
 * back to the initials, never to an empty frame.
 */
export type AvatarSize = "sm" | "md" | "lg" | "xl";

const PIXELS: Record<AvatarSize, number> = { sm: 28, md: 36, lg: 56, xl: 96 };

export function initialsOf(name: string): string {
  const parts = name.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : parts.slice(0, 1);
  return letters.map((part) => (part ? Array.from(part)[0]?.toUpperCase() : "")).join("") || "?";
}

/** A hue in [0, 360) derived from an identifier (FNV-1a), so the same user always gets the same color. */
export function hueOf(seed: string): number {
  let hash = 0x811c9dc5;
  for (const char of seed) {
    hash ^= char.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash % 360;
}

export interface AvatarProps {
  name: string;
  /** Stable identifier used for the placeholder color (falls back to the name). */
  userId?: string | undefined;
  src?: string | null | undefined;
  size?: AvatarSize;
  /** Decorative when the name is shown next to it. */
  decorative?: boolean;
  className?: string;
}

export function Avatar({ name, userId, src, size = "md", decorative = false, className }: AvatarProps) {
  const [broken, setBroken] = useState(false);
  const pixels = PIXELS[size];
  const showImage = Boolean(src) && !broken;
  const a11y = decorative ? { "aria-hidden": true as const } : { role: "img", "aria-label": name };
  return (
    <span
      className={["ds-avatar", `ds-avatar--${size}`, className].filter(Boolean).join(" ")}
      style={{ "--avatar-hue": hueOf(userId ?? name) } as React.CSSProperties}
      data-placeholder={showImage ? undefined : "true"}
      {...a11y}
    >
      {showImage ? (
        <img src={src ?? undefined} alt="" width={pixels} height={pixels} onError={() => setBroken(true)} />
      ) : (
        <span aria-hidden="true">{initialsOf(name)}</span>
      )}
    </span>
  );
}
