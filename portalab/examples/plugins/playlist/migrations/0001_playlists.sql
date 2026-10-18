CREATE TABLE playlists (
  id bigserial PRIMARY KEY,
  owner uuid NOT NULL,
  name text NOT NULL,
  description text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE entries (
  playlist_id bigint NOT NULL REFERENCES playlists (id) ON DELETE CASCADE,
  item text NOT NULL,
  title text NOT NULL,
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (playlist_id, item)
);
CREATE INDEX playlists_owner ON playlists (owner)
