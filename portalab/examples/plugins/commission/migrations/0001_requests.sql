CREATE TABLE requests (
  ownership uuid PRIMARY KEY,
  member uuid NOT NULL,
  product text NOT NULL,
  description text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'open',
  created_at timestamptz NOT NULL DEFAULT now()
)
