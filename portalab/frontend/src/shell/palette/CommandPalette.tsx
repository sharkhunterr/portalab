import * as DialogPrimitive from "@radix-ui/react-dialog";
import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useAnnounce } from "../../design-system/a11y/Announce";
import { Button } from "../../design-system/components/Button";
import { useT } from "../../i18n/hooks/useT";
import { useNavigationView } from "../nav/NavigationProvider";
import { useShellStrings } from "../strings";
import { type Command, fromNavigation, rank } from "./CommandRegistry";
import { useSearchCommands } from "./providers/search";

/**
 * Command palette (spec 004 T028; FR-019/020): opens from any page (Mod+K), lists only permitted commands,
 * fully keyboard operable (combobox + listbox, arrow keys, Enter, Escape), announces the result count and
 * returns focus to the trigger on close (Radix Dialog).
 */
export function CommandPalette({
  open,
  onOpenChange,
  initialQuery = "",
  actions,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialQuery?: string;
  actions: Record<string, () => void>;
}) {
  const shellStrings = useShellStrings();
  const t = useT();
  const { view } = useNavigationView();
  const navigate = useNavigate();
  const announce = useAnnounce();
  const ids = { input: useId(), list: useId() };
  const [query, setQuery] = useState(initialQuery);
  const [active, setActive] = useState(0);
  const commands = useMemo(
    () => fromNavigation(view.commands, shellStrings.label, actions),
    [view.commands, shellStrings.label, actions],
  );
  const location = useLocation();
  const searched = useSearchCommands(query, location.pathname, open);
  const results = useMemo(() => {
    const local = rank(commands, query);
    const seen = new Set(local.map((c) => c.route).filter(Boolean));
    return [...local, ...searched.filter((c) => !c.route || !seen.has(c.route))].slice(0, 30);
  }, [commands, query, searched]);
  const [pending, setPending] = useState<Command | null>(null);

  const returnFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (open) {
      returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setQuery(initialQuery);
      setActive(0);
      setPending(null);
    }
  }, [open, initialQuery]);
  const { paletteResults, paletteEmpty } = shellStrings;
  useEffect(() => {
    if (open) announce(results.length ? paletteResults(results.length) : paletteEmpty);
  }, [open, results.length, announce, paletteResults, paletteEmpty]);

  function execute(command: Command | undefined, confirmed = false) {
    if (!command) return;
    if (command.sensitive && !confirmed) {
      // sensitive actions need an explicit second step; the owning endpoint confirms and audits (008 R12)
      setPending(command);
      announce(t("search:palette.confirm"));
      return;
    }
    setPending(null);
    onOpenChange(false);
    if (command.run) command.run();
    else if (command.route) navigate(command.route);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, Math.max(results.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (pending) execute(pending, true);
      else execute(results[active]);
    }
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="ds-overlay" />
        <DialogPrimitive.Content
          className="ds-dialog shell-palette"
          aria-describedby={undefined}
          onEscapeKeyDown={(event) => {
            if (pending) {
              event.preventDefault(); // Escape first cancels a pending confirmation, then closes
              setPending(null);
            }
          }}
          onCloseAutoFocus={(event) => {
            // opened from a shortcut or a slot (no Radix trigger): give focus back to where it was
            if (returnFocus.current?.isConnected) {
              event.preventDefault();
              returnFocus.current.focus();
            }
          }}
        >
          <DialogPrimitive.Title className="visually-hidden">{shellStrings.palette}</DialogPrimitive.Title>
          <label htmlFor={ids.input} className="visually-hidden">
            {shellStrings.paletteInput}
          </label>
          <input
            id={ids.input}
            className="shell-palette__input"
            role="combobox"
            aria-expanded="true"
            aria-controls={ids.list}
            aria-autocomplete="list"
            aria-activedescendant={results[active] ? `${ids.list}-${active}` : undefined}
            placeholder={shellStrings.searchPlaceholder}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
          />
          <div
            id={ids.list}
            role="listbox"
            aria-label={shellStrings.palette}
            className="ds-list shell-palette__list"
          >
            {results.map((command, index) => (
              <div
                key={command.id}
                tabIndex={-1}
                id={`${ids.list}-${index}`}
                role="option"
                aria-selected={index === active}
                className="shell-palette__option"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => execute(command)}
                onKeyDown={() => undefined}
              >
                {command.label}
              </div>
            ))}
          </div>
          {results.length === 0 ? <p>{shellStrings.paletteEmpty}</p> : null}
          {pending ? (
            <div role="alert" className="shell-palette__confirm">
              <p>
                {pending.label} — {t("search:palette.confirm")}
              </p>
              <div className="ds-stack ds-stack--row">
                <Button onClick={() => execute(pending, true)}>{pending.label}</Button>
                <Button variant="secondary" onClick={() => setPending(null)}>
                  {t("core:cancel")}
                </Button>
              </div>
            </div>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
