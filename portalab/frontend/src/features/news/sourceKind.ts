/** issue 299: a news source's icon, after its kind (told by the server from its address). */
const ICONS: Record<string, string> = {
  youtube: "youtube",
  video: "circle-play",
  podcast: "podcast",
  reddit: "reddit",
  rss: "rss",
};

export function sourceIcon(kind: string | null | undefined): string {
  return ICONS[kind ?? "rss"] ?? "rss";
}
