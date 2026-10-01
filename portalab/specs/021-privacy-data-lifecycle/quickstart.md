# Quickstart — Privacy & Audit completion
1. Set a profile field to Private; as another permitted user fetch the profile → field redacted.
2. As Admin force `private` for a class on a user; effective level changes; remove the policy → the original preference is effective again (preference row untouched).
3. Run the retention job with a 1-day audit window on a test DB: old partitions dropped, integrity tables untouched.
4. `uv run portalab audit verify` passes; tamper with a row in a test DB (superuser) → verification fails.
5. Aggregate endpoint returns no cell with fewer than `privacy.minAggregateSize` members.
