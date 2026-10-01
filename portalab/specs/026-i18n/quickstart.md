# Quickstart — i18n
1. `GET /i18n/context` as a user with no preference → portal default; set `language=fr` in `/me/preferences` → next call returns `fr`; disable `fr` in Administration → context falls back, preference retained; re-enable → restored.
2. Render a plural message in a language with several categories → correct form; a missing key shows the fallback language string and increments the missing-key stat.
3. Set locale `de-DE` while language stays `en` → dates/numbers use German conventions, strings stay English.
4. Store an instant, view it from two time zones; a "9:00 local" schedule across a DST gap fires once per documented policy.
5. Enable pseudo-locales in dev → long and RTL strings do not clip critical info; axe passes.
6. `portalab i18n check` fails when a translation drops a placeholder.
