# Spike — backend ICU MessageFormat renderer (spec 026 T004)

**Question.** Which `MessageRenderer` adapter renders the same ICU catalogs on the backend as `react-intl`
(`intl-messageformat`) does in the browser: the `PyICU` binding, or a pure-Python ICU MessageFormat parser
with Babel plural rules?

**Conformance suite.** `backend/tests/data/icu_vectors.json` — 25 golden vectors over 9 languages
(`en`, `fr`, `de`, `ru`, `pl`, `cs`, `ar`, `ja`; multi-category plurals incl. `zero/two/few/many`):
`=N`/keyword plurals, `offset`, `#`, `selectordinal`, `select` (gender), nested select→plural, apostrophe
quoting (`''`, `'{…}'`, `'#'`), `number`/`percent` styles. Both runtimes run the same file
(`tests/unit/i18n/test_icu_vectors.py`, `frontend/tests/unit/i18n/messages.test.tsx`).

| Candidate | Vectors | Image impact | Notes |
|---|---|---|---|
| `PyICU` | not run | needs `libicu-dev` + compiler in the build stage and `libicu` in the runtime image (≈ 40 MB), version coupling with the system ICU | rejected by the exit criterion (no unaccepted system packages) |
| **pure Python + Babel** (`modules/i18n/render/icu.py`) | **25/25** | none beyond `babel` (pure Python, bundles CLDR) | supports the message subset the catalogs use; date/time args are formatted by `Formatter`, not inside messages |

`intl-messageformat` (frontend) also passes **25/25** on the same file, so backend and browser renderings agree.

**Decision.** Pure-Python adapter behind the `MessageRenderer` port; CLDR via `babel==2.18`, IANA zones via
`tzdata`. Catalog rule: dates and times are passed pre-formatted (or formatted by the caller with
`Formatter`), never as ICU `date`/`time` arguments, so both runtimes stay aligned.
