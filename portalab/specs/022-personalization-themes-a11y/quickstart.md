# Quickstart — Design System & Themes
1. Open the component gallery route (dev) → every component shown in all functional states under light, dark and high-contrast.
2. Register a theme with a low-contrast state color → rejected with a floor report.
3. Set `ui.reducedMotion=on` and `ui.textScale=1.5` → animations stop, layout reflows at 320 px without clipping.
4. Switch language to an RTL language (once configured) → layout mirrors, directional icons flip.
5. Run `npm run test:a11y` → axe passes on gallery and key routes; keyboard-only journey passes.
