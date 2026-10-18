CREATE TABLE topics (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  author uuid NOT NULL,
  author_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE posts (
  id bigserial PRIMARY KEY,
  topic_id bigint NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
  author uuid NOT NULL,
  author_name text NOT NULL,
  body text NOT NULL,
  removed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX posts_topic ON posts (topic_id, id);
CREATE INDEX posts_author ON posts (author)
