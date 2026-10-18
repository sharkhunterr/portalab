CREATE TABLE bubbles (
  member uuid NOT NULL,
  look text NOT NULL,
  chosen boolean NOT NULL DEFAULT false,
  PRIMARY KEY (member, look)
)
