# Business Rules

## Priority
1. Security / Permissions
2. Data Integrity
3. Privacy
4. Business Rules
5. Admin Configuration
6. User Preferences
7. Presentation / Theme

## Administration
- Exactly one account has Admin role.
- No temporary role delegation.

## Economy
- Coins are strictly internal and virtual.
- No real-money coin purchases under the current definition.
- Coin balance normally cannot be negative.
- Manual corrections are explicit and audited.
- Refunds are new transactions.
- Final account deletion destroys remaining coins.

## Marketplace
- Already-owned permanent products cannot be purchased twice unless explicitly repeatable.
- Existing owners keep access when products are archived.
- Marketplace plugins activate immediately after purchase unless explicit configuration is required.
- Request quota can be sold for coins; paid request priority does not exist.

## Community
- Every active account can vote.
- No minimum level.
- Voting and funding are independent.
- Funding does not guarantee implementation.

## Events
- Multiple events may overlap.
- Modifiers combine according to deterministic configured rules.
- Duplicate rewards are prevented.
- Anti-farming limits apply.

## Gamification
- XP, Contribution and Coins are separate.
- Historical rewards remain tied to their historical rules/version.
- Manual rewards are marked and audited.

## Privacy
- Historized does not mean public.
- Temporary admin visibility overrides preserve the user's underlying preference.
- Removing the override restores the preference.

## Services
- Native data source remains authoritative.
- Disconnecting a service removes live access/sync, not necessarily history.
- Outage does not erase existing data.
- Sync state and service health are distinct.

## Plugins
- Disabling a plugin does not delete its data.
- Plugin failures must not break unrelated portal functions.
- Plugins respect core security and permission rules.

## AI
- AI has the same effective rights as the current user.
- AI cannot bypass permissions.
- Sensitive actions require confirmation where appropriate.
- AI failure must not break classic functions.

## Support
- Ticket = individual issue.
- Incident = broad/systemic problem.
- Known incidents should be surfaced to reduce duplicate tickets.

## Deletion
- Account deletion is a lifecycle.
- Personal data is deleted/anonymized at final deletion.
- Aggregate data may remain when non-identifying and necessary.
- Historical transaction integrity is preserved.

## Synchronization
- Synchronization is idempotent where needed.
- Event occurrence time is not sync receipt time.
- Conflicting sources follow configured source-of-truth rules or preserve provenance.
- Full resync must not blindly destroy native portal data.
