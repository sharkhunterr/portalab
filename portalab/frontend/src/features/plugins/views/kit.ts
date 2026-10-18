/**
 * 030: the base kit Portalab hands a plugin's own view — plain elements and a few ``pl-`` classes styled only
 * with the member's tokens (CSS variables), so a view that uses them, or the variables themselves, follows
 * the theme, the interface and the palette. A view may draw anything else on top; these are a floor.
 */
export const THEME_KIT = `
html,body{color:var(--color-text);font-family:var(--font-sans,system-ui,sans-serif);font-size:var(--font-size-md,1rem)}
*{box-sizing:border-box}
a{color:var(--color-accent)}
:focus-visible{outline:2px solid var(--color-focus,var(--color-accent));outline-offset:2px}
.pl-stack{display:flex;flex-direction:column;gap:var(--space-3)}
.pl-row{display:flex;flex-wrap:wrap;align-items:center;gap:var(--space-2)}
.pl-card{background:var(--color-surface-raised,var(--color-surface));border:1px solid var(--color-border);border-radius:var(--radius-md);padding:var(--space-4);box-shadow:var(--shadow-sm)}
h1,h2,h3{font-family:var(--font-display,var(--font-sans,system-ui,sans-serif))}
.pl-muted{color:var(--color-text-muted)}
.pl-button{display:inline-flex;align-items:center;justify-content:center;gap:var(--space-1);min-height:var(--target-min,2.5rem);padding:0 var(--space-4);border-radius:var(--radius-pill);border:1px solid transparent;background:var(--color-accent);color:var(--color-accent-contrast);font:inherit;font-weight:var(--font-weight-semibold);cursor:pointer;transition:filter var(--motion-duration-fast) var(--motion-easing)}
.pl-button:hover{filter:brightness(1.08)}
.pl-button[data-variant=ghost]{background:transparent;color:var(--color-text);border-color:var(--color-border)}
.pl-button:disabled{opacity:.5;cursor:default}
.pl-input,.pl-textarea{width:100%;min-height:var(--target-min,2.5rem);padding:var(--space-2) var(--space-3);border-radius:var(--radius-sm);border:1px solid var(--color-border);background:var(--color-surface);color:var(--color-text);font:inherit}
.pl-textarea{min-height:5rem;resize:vertical}
.pl-badge{display:inline-flex;min-width:1.25rem;padding:0 var(--space-1);border-radius:var(--radius-pill);background:var(--color-accent);color:var(--color-accent-contrast);font-size:var(--font-size-xs);justify-content:center}
.pl-error{color:var(--state-error-fg);background:var(--state-error-bg);border-radius:var(--radius-sm);padding:var(--space-2)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
`;
