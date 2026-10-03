-- Runs with the plugin's own role, in schema plugin_hello (no access to core tables).
CREATE TABLE greetings (
    id bigserial PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
