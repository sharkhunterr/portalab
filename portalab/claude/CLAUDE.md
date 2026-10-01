# Claude Code Instructions

Read before implementation:
1. ../product/PRODUCT_BLUEPRINT.md
2. ../product/BUSINESS_RULES.md
3. ../architecture/FUNCTIONAL_ARCHITECTURE.md
4. ../features/FEATURE_CATALOG.md
5. ../architecture/EVENT_MODEL.md
6. ../architecture/PERMISSION_MODEL.md
7. ../architecture/EXTENSIBILITY.md
8. ../ux/USER_JOURNEYS.md

Critical:
- Do not contradict product decisions.
- Prefer capabilities over concrete service coupling.
- AI uses current user permissions.
- Never bypass security.
- Historized does not mean public.
- One Admin account.
- Coins are internal virtual currency only.
- Everyone active can vote.
- Marketplace plugins activate immediately after purchase unless explicit configuration is required.
- Account deletion destroys remaining coins.
- Search and AI are parallel/non-blocking.
- External outages must not break unrelated portal functions.
- Plugin disable does not automatically delete data.
- Historical rules/transactions are not rewritten.
- Themes change presentation only.

Do not invent a technical stack from these product documents. Technical architecture comes later.

For every non-trivial change:
1. identify feature;
2. read business rules;
3. identify permissions;
4. identify events;
5. identify source of truth;
6. identify degraded/error states;
7. identify extension points;
8. implement;
9. test.
