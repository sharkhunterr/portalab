---
slug: guide-centre-de-controle
title: Control center
position: 3
help_keys: [incidents, incidents.detail, services, services.detail]
tags: [guide, incidents, maintenance, services]
---
See at a glance whether everything is fine on the portal: the control center in the header, the banners, the incidents page and the services' status.

## The control center in the header

In the header, next to the bell, a small icon sums up the portal's state. Its drawing changes with what is going on:

| Icon | What it means |
|---|---|
| A beating heart | Everything is fine |
| The danger sign | One or more incidents in progress |
| A wrench | A maintenance in progress, or planned in less than a day |
| A warning triangle | Services in trouble |
| A megaphone, in the announcement's colour | One or more announcements running |

A small number shows how many there are. When several things happen at once, the icon shows them in turn, the most serious first and for longer.

### Opening the details

Click the icon: the « Control center » window opens. It can hold:

- **Incidents**: each open incident, with its severity, its stage and since when;
- **Maintenance**: the week's maintenance, in progress (with the time left) or coming up (with its times);
- **Announcements**: the running announcements, **even the ones whose banner you closed**;
- **Services**: « All services are working » or the number of services in trouble.

At the bottom, two links lead to « Service status » and « All incidents ». Click an item to open its details.

![The « Control center » window, opened from its icon in the header](shot:controle-fenetre)

> [!NOTE]
> Depending on your portal, the « Services » part may not show for you. Incidents, maintenance and announcements stay visible.

## Banners

When something important happens, a banner can show at the top of every page. It says what it is, its title, a line of details, its start and end dates, and a « Details » or « Learn more » link.

### The three kinds of banners

- **Maintenance**: it shows from the day before (« Planned maintenance · Starts in… »), then during the maintenance (« Maintenance in progress · Ends in… »). A bar under the banner shows the progress.
- **Incident**: « Ongoing incident », with its severity (« Minor », « Major », « Critical »), its stage and its latest update. If there are several, the most serious comes first.
- **Announcement**: a message from the portal's team, in the colour of its tone (information, success, warning or critical).

Not every maintenance or incident shows as a banner: the portal's team decides.

### Closing a banner

Click the small cross, « Hide this notice ».

- A **maintenance** or **incident** banner can always be closed. A closed incident **comes back** if it gets worse.
- Some **announcements** cannot be closed: the administrator chose to keep them showing. They then have no cross.
- A closed announcement can still be read in the control center as long as it is running.

> [!TIP]
> A banner is closed only on the device and the browser you are using. On another device, it may show again.

### When several services have a problem

If several services are degraded or unavailable at the same time, a message says so at the top of the page. Navigation and search still work.

## The Incidents page

The [Incidents](/incidents) page tells you what is wrong, where things stand and what has been fixed.

- At the top, a summary: the number of incidents in progress (or « Everything is working normally ») and the number of incidents resolved over the last 30 days.
- The « Ongoing », « Resolved » and « All » filters sort the list.
- Each incident is a card: its severity, its stage, how long it has lasted (or how long it lasted), the « Affected services » and its latest update.
- Open an incident to read its « Timeline »: every stage, from its declaration to its resolution.

![The Incidents page, with its seven numbered markers](shot:controle-incidents)

1. The summary: incidents in progress and resolved over the last 30 days.
2. The « Ongoing », « Resolved » and « All » filters.
3. The incident's severity.
4. How long it has lasted.
5. Its stage.
6. Its latest update.
7. The « Affected services ».

An incident's stages are: « Investigating », « Identified », « Monitoring », then « Resolved ».

At the bottom of the page, the « Planned maintenance » part lists the maintenance to come: when, for how long and what it affects.

## The services page

The [Services](/services) page (« Service status ») shows how the portal's services are doing.

- At the top, a summary: « Everything is working », or the number of services in trouble, incidents in progress or services under maintenance.
- The « Incidents in progress » and the « Planned maintenance » are repeated just below.
- Each service has its card: its state (operational, degraded, unavailable…), a bar of its **last 48 hours** and its availability.

![The services page, with its five numbered markers](shot:controle-services)

1. The summary of the services' status.
2. The « Incidents in progress ».
3. A service's state.
4. Its bar of the last hours and its availability.
5. « Open » and « Details ».

In the 48-hour bar, each line is one hour: green when everything worked, orange when there were hiccups, red when the service was mostly down, grey without checks. Hover over a line to see its hour.

On each card:

- « Open » takes you to the service, when it has a public address;
- « Details » opens its page: availability over 24 hours, downtime, recent changes, the incidents and maintenance that concern it… Depending on your rights, some parts may not show.

> [!TIP]
> A service is not working and nothing is reported? Open a [support ticket](/support/new) and choose the service concerned. See [Support](portalab://wiki/guide-support).

## Getting notified

Depending on your portal and your [notification preferences](/settings/notifications), the portal can also let you know:

- about a maintenance (« Maintenance tomorrow », « Maintenance in one hour », « Maintenance in progress », rescheduled or cancelled);
- about a service that becomes unavailable, then available again.

The settings are explained in [Notifications](portalab://wiki/guide-notifications). The « Open incidents » widget can also show on your [home page](portalab://wiki/guide-accueil).
