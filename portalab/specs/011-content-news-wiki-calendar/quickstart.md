# Quickstart — Content
1. As an editor create a News draft (invisible to readers), schedule it for +2 min → appears at `publish_at` once; feature it (max 3 enforced); archive it → leaves discovery, still readable by direct permitted link per policy.
2. Publish with notification → `news.published` communication restricted to the article audience; unpermitted users get nothing.
3. Create a Wiki page with table, code, callout, Mermaid and an image asset; a pasted `<script>` or `javascript:` link renders inert; external image is blocked.
4. Two editors save from the same base version → second gets 409 with diff; resolve and save → new revision; compare two versions; restore v1 → new revision v(n+1).
5. Mark a page `readable_by_ai` + help key; as a user without access the help/AI search never returns it.
6. Open the Calendar: maintenance (006) and scheduled news show by type; stop one source → banner for that source only; opt in to a reminder → fires once, re-checks the item.
7. A News article links a Wiki page the viewer cannot read → link shows "not available" with no title leak.
