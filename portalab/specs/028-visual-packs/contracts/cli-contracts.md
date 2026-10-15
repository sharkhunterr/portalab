# CLI Contracts (028)

Same entry point as `portalab migrate|serve|worker` (bootstrap settings via env/`_FILE`).

## `portalab visuals analyse <folder|zip> [--json]`

Runs the portal's analysis offline (no database; built-in look keys known from the bundled socle list; pack
conflicts not checked). Prints findings grouped by element (level, code, file, plain-words message), then a
summary. Exit `0` no blocking finding, `1` blocking finding, `2` unreadable input. `--json` prints the report
object of `pack_versions.report`.

## `portalab visuals builtin sync [--dry-run]`

The built-in sync (R6/R7), also run by `migrate` and at `serve` start. `--dry-run` prints what would change
(packs new/updated, elements added/removed/changed) without writing.

## `portalab security blocks list`

Lists active blocks: `id  kind  label  reason  points  until`. Exit `0`.

## `portalab security blocks lift <id|account:<login>|address:<ip>> | --all`

Lifts the block(s); prints the count; writes `security.block.lifted` to the audit log with actor
`console:<os user>` and publishes `security.blocks.changed` (running processes drop it within 5 s). Works
without any session, the Admin's account included (FR-040a). Exit `0`, `1` nothing matched.
