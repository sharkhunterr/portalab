# Quickstart — Marketplace
1. A proposal (Community) registers a lifecycle record; Admin promotes it, sets funding rules (refund 100 %, consume at release) and opens it → rules frozen; votes (free) and funding (reserved, with the non-guarantee acknowledgement) proceed independently.
2. A funder's Coins are reserved (ledger reservation transactions); Admin validates → development → beta → released: reserved funds are consumed per rules (new transactions). Another project is rejected → all funds released (new transactions).
3. Publish a product (widget, price 50 Coins, min level 3, refund 7 days); a level-2 user sees the unmet condition by name and cannot acquire; a level-3 user acquires once (idempotent request) → ownership + ledger spend in one unit; second purchase refused.
4. A plugin/feature product that needs configuration shows needs-configuration until configured; activation failure leaves ownership intact with retry and does not break other features.
5. Buy quota units → Media request quota rises after the base quota; queue ordering is identical for buyers and non-buyers.
6. Refund within the window → new ledger transaction, ownership refunded; non-refundable products are labelled before purchase; revoke for `abuse` with reason → user notified, history intact.
7. Archive a product → existing owners keep access, no new purchases; final deletion of a funder resolves per R6.
