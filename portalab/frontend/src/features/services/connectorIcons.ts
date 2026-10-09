/** 027: the icon of a service by its connector (dashboard cards, the ticket form's service picker). */
export const CONNECTOR_ICON: Record<string, string> = {
  plex: "film",
  jellyfin: "film",
  emby: "film",
  tautulli: "chart",
  radarr: "clapperboard",
  sonarr: "tv",
  lidarr: "music",
  seerr: "inbox",
  overseerr: "inbox",
  jellyseerr: "inbox",
  grimmory: "book",
  audiobookshelf: "headphones",
  romm: "joystick",
  tmdb: "database",
  qbittorrent: "package",
  deluge: "package",
};

export function connectorIcon(connector: string | null | undefined): string {
  return CONNECTOR_ICON[connector ?? ""] ?? "server";
}
