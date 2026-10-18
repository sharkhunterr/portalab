CREATE TABLE conversations (
  id bigserial PRIMARY KEY,
  a uuid NOT NULL,
  b uuid NOT NULL,
  a_name text NOT NULL,
  b_name text NOT NULL,
  last_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (a, b)
);
CREATE TABLE messages (
  id bigserial PRIMARY KEY,
  conversation_id bigint NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
  author uuid NOT NULL,
  body text NOT NULL,
  read boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX messages_conversation ON messages (conversation_id, id)
