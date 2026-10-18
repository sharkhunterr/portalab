ALTER TABLE entries ADD COLUMN image_id text;
ALTER TABLE entries ADD COLUMN kind text NOT NULL DEFAULT 'movie'
