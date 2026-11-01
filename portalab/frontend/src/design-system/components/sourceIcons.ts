import { createLucideIcon, type IconNode } from "lucide-react";

/**
 * issue 299: the kinds of news sources a feed can be — a YouTube channel (the play button in its rounded
 * frame, as the site draws it), a forum's thread (Reddit's alien's head, simplified) — drawn in the other
 * icons' stroke, since the icon set no longer carries brands.
 */
const YOUTUBE: IconNode = [
  [
    "path",
    {
      d: "M2.5 17a24.1 24.1 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.6 49.6 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.1 24.1 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.6 49.6 0 0 1-16.2 0A2 2 0 0 1 2.5 17",
      key: "frame",
    },
  ],
  ["path", { d: "m10 15 5-3-5-3z", key: "play" }],
];

const REDDIT: IconNode = [
  ["ellipse", { cx: 12, cy: 15, rx: 8, ry: 5.5, key: "head" }],
  ["path", { d: "M12 9.5 13.5 4l4 1", key: "antenna" }],
  ["circle", { cx: 18.5, cy: 5, r: 1.5, key: "tip" }],
  ["circle", { cx: 9, cy: 14, r: 0.8, fill: "currentColor", key: "left" }],
  ["circle", { cx: 15, cy: 14, r: 0.8, fill: "currentColor", key: "right" }],
  ["path", { d: "M9.5 17.5c1.5 1 3.5 1 5 0", key: "smile" }],
];

export const SOURCE_ICONS = {
  youtube: createLucideIcon("Youtube", YOUTUBE),
  reddit: createLucideIcon("Reddit", REDDIT),
};
