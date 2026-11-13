# Members and roles

Manage accounts and their linked service accounts, roles and permissions, single sign-on with Authentik or any OpenID Connect provider, privacy policies and request quotas.

## Where things are

| Administration hub | Pages |
|---|---|
| **Members & access** | **Members** (`/admin/members`), **Roles & permissions** (`/admin/roles`), **Privacy policies** (`/admin/privacy`), **Terms of use** (`/admin/terms`, see [Content and communication](content.md#terms-of-use)) |
| **Media** | **Request quotas** (`/admin/media-quotas`) |
| **System** | **Configuration** (area Accounts), **Security blocks** |

## Members

**Members**: "Every account of the portal: invite, suspend, reactivate or delete." It has two tabs, **Portal accounts** and **Service accounts**.

### Portal accounts

Each account has a state:

| State | Meaning |
|---|---|
| **Invited** | Created, waiting for the member to choose a password. |
| **Active** | Can sign in. |
| **Inactive** | Has not signed in for a while (setting *Inactive account delay*). |
| **Suspended** | Can no longer sign in; its data is kept. |
| **Being deleted** | Waiting for final deletion; the deletion can still be cancelled. |
| **Deleted** | Gone. |

- **Invite a member**: a login, a display name and an optional e-mail. The member receives a link to choose a password; share it as you like (message, e-mail…). It works once and expires; **New link** makes another.
- **Edit** changes the display name, the e-mail and the roles. The User role is implicit; the Admin role is handed over only by transfer.
- **Suspend** and **Reactivate**.
- **Password** (on the member's card, **Profile & roles**): set a new password for a member who signs in with a password of their own — forgotten, or to see the portal as they do. Confirm with your own password; every session of the member is signed out and the change is recorded in the audit log (never the password itself). Share the new password with them yourself. It is not offered on your own card (use **Change my password**), and the Admin's password and the accounts of the single sign-on are changed elsewhere.
- **Two-step verification** (on the member's card): when a member lost their phone and their recovery codes, turn their second factor off. Confirm with your own password; the member is told and can turn it back on from their account. It is not offered on your own card, and the Admin's is turned off from their own account only.
- **Delete** starts the deletion: the account waits for the *Account deletion delay*, during which you can **Cancel deletion**; **Confirm deletion (after the legal delay)** finishes it. The Admin account cannot be deleted: transfer the Admin role first.

Open a member's **card** for everything about them, in tabs: **Profile & roles**, **Linked accounts**, **Progression**, **Economy** (give or take Coins, XP, Contribution and items, see [Gamification and economy](gamification-and-economy.md#manual-grants-and-corrections)), **Requests**, **Support** and **Vigilance**, plus **Account suspension**.

### Service accounts

The portal attributes plays, requests and statistics to members through their accounts on the media services. **Service accounts** lists the accounts of every connected service that lists them (Plex, Jellyfin, Seerr, RomM), the member each one is linked to and its pending, unattributed activity.

- **Suggestions** match accounts to members by **same e-mail** or **same name**; **Apply the suggestions** links them and attributes their past activity.
- **Link to** a member by hand, or **Unlink**.
- **Create a member from this account**, or **Create the missing members** at once: each new member activates their account from a link, sent by e-mail when the portal sends e-mails, or shown once for you to hand over.

Members can link their own media accounts in **My settings → Media accounts** (see [Media](../members/media.md)).

### Registration and welcome

In Configuration, area Accounts:

| Setting | What it does |
|---|---|
| *Registration* | **Open registration** (people sign up themselves) or **Invitation only**. |
| *Welcome new members*, *Welcome message* | A few welcome steps and a guided tour at the first sign-in: a face and a name, media accounts, how far the member plays (the play gauge, from **Just the media** to **Keen**, see [Playing on the portal](../members/gamification.md#choosing-to-play)), public or anonymous in the community (a screen of its own, whatever the play gauge), their home to their taste, how they are told, a look. |
| *Password length*, *Password hashing strength* | Local password policy. |
| *Idle session expiry*, *Maximum session length* | Sessions. |
| *Verification link validity*, *Data export availability* | Links and exports. |

## Roles and permissions

**Roles & permissions**: "Who may do what: roles and groups, and the permissions they grant."

### Base roles

| Role | What it is for |
|---|---|
| **User** | Every account holds it: reading the portal, requesting, playing, opening tickets. |
| **Editor** | News and wiki writing and publishing. |
| **Support** | Tickets, incidents, feedback; wiki editing. |
| **Moderator** | Community proposals and community events. |
| **Admin** | Everything. There is exactly one Admin; the role is never granted or removed like the others, only transferred. |

You can create your own roles (**New role**: a key, a name, a base role) and groups (**New group**), then choose a role or a group to see and change its permissions.

### Permissions

**Add the permission** grants a permission to the chosen role or group, with:

- an **Effect**: **Allow** or **Deny**;
- a **Scope**: **Everywhere**, **One module**, **One service**, **One plugin**, **Own objects only** or **Own account only**.

Some permissions are marked **Admin only**: they can never be granted to anyone else. **Sensitive** permissions are audited each time they are allowed or denied, and some actions ask for an explicit confirmation. The assistant and automations never hold more rights than the member they act for (see [Assistant and automations](ai-and-automations.md)).

Shop products of type **Access** can grant a member a permission, only among those listed in *Permissions for sale*, never an Admin-only one.

## Single sign-on (Authentik or OpenID Connect)

Members can sign in with their homelab account through any OpenID Connect provider; Authentik is the tested setup. The sign-in page then shows a "Sign in with …" button.

### In the provider

1. Create an OAuth2/OpenID application for Portalab (confidential client, authorization code).
2. Set its redirect URI to `https://<your portal>/api/v1/auth/oidc/callback`.
3. Make sure the scopes `openid`, `email` and `profile` are provided, and that the `email` scope reports `email_verified: true` for the e-mails the provider has verified.
4. Bind the application to the group of your community's members, **forbid members from changing their own e-mail**, and enforce multi-factor authentication on that group.

### In Portalab

In Configuration, area Accounts:

| Setting | What it does |
|---|---|
| *Enable single sign-on* | Offer the "Sign in with" button on the sign-in page. |
| *Single sign-on provider address* | The issuer URL, for example `https://sso.example.org/application/o/portalab/`. |
| *Single sign-on client ID*, *Single sign-on client secret* | Given by the provider (the secret is write-only). |
| *Single sign-on button name* | The provider's name shown on the button. |
| *Create accounts on first sign-in* | Create a portal account for a provider user who signs in for the first time. |

### How accounts are linked

Accounts are linked **by the server**; nobody links them by hand. When someone signs in through the provider, Portalab looks, in order, for:

1. the member this provider account is already linked to;
2. the member already signed in in this browser, if any;
3. the member with the same e-mail address, when the provider vouches for it (`email_verified: true`);
4. otherwise, a new member, if *Create accounts on first sign-in* is on (else the sign-in is refused).

An e-mail the provider does not vouch for links nobody, and no second account is made with it: the sign-in is refused. Authentik leaves `email_verified` out for its own users. Either make its `email` scope report it, or turn on *Trust the provider's e-mails*, but only if your members cannot change their e-mail at the provider (otherwise anyone there could take a portal account by setting its e-mail).

The **Admin** account is linked by e-mail only when the provider vouches for that e-mail (`email_verified: true`), whatever that setting; otherwise the Admin keeps signing in with their password. A sign-on can only be finished in the browser that started it, so nobody can sign someone else in with a link. The provider's ID token is checked (signature, issuer, audience, expiry, nonce) and the flow uses PKCE.

Behind a reverse proxy, also set the trusted proxies so the sign-on can build its way back: see [Operations](operations.md) and the [internet exposure notes](../../portalab/docs/internet-exposure.md).

A **Service access** product of the shop can name an **Access group** of the identity provider; approving the request can create the account there (see [Gamification and economy](gamification-and-economy.md#orders-to-handle)).

## Privacy policies

Each member decides who sees each kind of their data in their **Privacy center**: **Everyone**, **Portal members**, **Leaderboards only** or **Only me**. A permission alone never reveals private data, even to administrators.

**Privacy policies** shows **Visibility overrides**: "Force a datum private or visible for everyone or one member; their own choice is kept."

1. Choose the **Data** (profile, progression, activity, projects…).
2. Choose the **Rule**: **Force private**, **Force visible** or **Follow the member's choice**.
3. Leave the member empty for everyone, or name one member; give a **Reason**.
4. **Apply**. **Remove the override** brings members' own choices back.

Members see "Set by the administrator for now; your own choice is kept and comes back afterwards."

Retention settings (Configuration, area Privacy) set how long each kind of data is kept: personal, activity, history, aggregated, technical and audit data, plus *Smallest group in totals* for aggregated figures and *Data export availability*. Members can download a copy of their data or delete their account from their Privacy center.

## Request quotas

**Request quotas** sets the request service's (Seerr) limits from the portal: "a number of requests every so many days, films and series apart. Every change is audited."

- **Defaults** apply to every account without limits of its own (empty or 0: no limit).
- **Accounts** lists every account of the service, the member it belongs to and what it used. **Edit** one, or tick several and **Apply** the same limits to all. **Manager: no quota** marks exempt accounts.

Members see their remaining quota on their requests page and can top it up with **Request quota** products from the shop, if you sell them. No product can buy priority.

## Security blocks

The intrusion guard blocks accounts, sessions or addresses that send suspicious requests. **Security blocks** lists the blocks in force with their time left; **Lift** or **Lift all**. See [Operations](operations.md).

---

Next: [Content and communication](content.md) · [Assistant and automations](ai-and-automations.md) · [Operations](operations.md) · [Configuration](../configuration.md)
