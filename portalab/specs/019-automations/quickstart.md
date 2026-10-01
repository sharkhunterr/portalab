# Quickstart — Automations
1. Admin builds "campaign start announcement": WHEN `campaign.started` IF audience = all THEN `communication.produce`; dry-run shows the planned communication; publish → fires once on the event (duplicate delivery ⇒ one execution).
2. Add a condition on a failing context (service state) → execution `no_op` with a trace of which leaf was false.
3. Author loses a permission → next run is `refused`, automation flagged `needs_review`; an action the author could not do manually is refused.
4. Create A→triggers→B→triggers→A → loop prevented at the cycle; depth limit stops at 3; both recorded.
5. An action that always throws → after 5 failures the automation is auto-suspended with a notification; re-enable resets counters.
6. A destructive action requires per-run approval: execution waits (`awaiting_approval`), approver approves in time → runs once; expiry ⇒ not executed.
7. Trigger storm (1000 events/min) → batched/throttled executions recorded, none silently dropped, other automations unaffected.
