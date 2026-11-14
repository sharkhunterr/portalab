# Data Model: Household Profiles

## identity.household_members

| Column | Type | Notes |
|---|---|---|
| user_id | uuid PK → users | the member (master or profile) |
| owner_id | uuid → users | the master; `owner_id = user_id` ⇔ `kind = 'owner'` (check) |
| kind | varchar(16) | `owner`, `standard`, `child`, `custom` |
| color | varchar(16) | from the portal palette |
| position | int | order on the picker |
| pin_hash | varchar(512) null | Argon2 of a 4–6 digit PIN |
| community_visible | bool | false: out of the members directory and leaderboards |
| restrictions | jsonb | `{max_age: 0|6|10|12|14|16|18|null, allow_unrated: bool, blocked: [feature…]}` |
| created_at, updated_at | timestamptz | |

The master's row is created with its first profile (it then holds the master's PIN).

## identity.access_requests

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| profile_id, owner_id | uuid → users | |
| kind, subject_ref | varchar | `media`, the object id |
| title, rating, note | varchar | shown to the master (title tombstoned to "") |
| status | varchar(16) | `pending` → `approved` / `denied`; one pending per (profile, kind, ref) |
| created_at, decided_at, expires_at | timestamptz | an approval in force: `expires_at` null or future |

## identity.sessions (new columns)

`acting_user_id` (uuid → users, null: the account itself), `profile_chosen` (bool, the picker answered).

## gamification.transactions (new column)

`profile_id` (uuid null): set on the master's copy of a profile's row.
