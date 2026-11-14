import { type FormEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { Dialog, DialogActions } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";
import {
  CHOOSE_PROFILE_EVENT,
  type HouseholdSession,
  type MemberTile,
  useHouseholdSession,
  useSwitchProfile,
} from "./api";
import "./household.css";

/**
 * « Who's there? » (spec 032): after signing in, an account with profiles chooses who uses the portal; the
 * header's « Switch profile » brings the picker back. The server decides: entering a profile asks its PIN
 * when another profile is active, coming back to the master asks the master's.
 */
export function ProfileGate({ children }: { children: ReactNode }) {
  const session = useHouseholdSession();
  const [open, setOpen] = useState(false);
  const [member, setMember] = useState<string | null>(null);
  useEffect(() => {
    const show = (event: Event) => {
      setMember(event instanceof CustomEvent && typeof event.detail === "string" ? event.detail : null);
      setOpen(true);
    };
    window.addEventListener(CHOOSE_PROFILE_EVENT, show);
    return () => window.removeEventListener(CHOOSE_PROFILE_EVENT, show);
  }, []);
  if (session.isPending) return null;
  const state = session.data;
  if (state?.enabled && state.members.length > 1 && (state.must_choose || open)) {
    return (
      <ProfilePicker
        session={state}
        initial={member}
        onCancel={state.must_choose ? undefined : () => setOpen(false)}
      />
    );
  }
  return <>{children}</>;
}

/** A member's face: their picture, else their initial on their colour. */
export function ProfileFace({
  member,
  size = "lg",
}: {
  member: Pick<MemberTile, "id" | "display_name" | "color" | "has_avatar">;
  size?: "sm" | "md" | "lg";
}) {
  const initial = Array.from(member.display_name.trim())[0]?.toUpperCase() ?? "?";
  return (
    <span
      className={`household-face household-face--${size}`}
      style={{ "--profile-color": member.color } as React.CSSProperties}
      aria-hidden="true"
    >
      {member.has_avatar ? <img src={`/api/v1/users/${member.id}/avatar`} alt="" /> : <span>{initial}</span>}
    </span>
  );
}

export function ProfilePicker({
  session,
  initial = null,
  onCancel,
}: {
  session: HouseholdSession;
  initial?: string | null;
  onCancel?: (() => void) | undefined;
}) {
  const t = useT();
  const titleId = useId();
  const switcher = useSwitchProfile();
  const preset = session.members.find((m) => m.id === initial && m.needs_pin);
  const [asking, setAsking] = useState<{ member: MemberTile; next?: string } | null>(
    preset ? { member: preset } : null,
  );
  const owner = session.members.find((m) => m.id === session.owner_id);
  const go = (member: MemberTile, next?: string) => {
    if (member.id === session.active_id && !session.must_choose && !next) {
      onCancel?.();
      return;
    }
    if (member.needs_pin) setAsking({ member, ...(next ? { next } : {}) });
    else switcher.mutate({ user_id: member.id, next });
  };
  return (
    <main className="household-picker" aria-labelledby={titleId}>
      <div className="household-picker__glow" aria-hidden="true" />
      <h1 id={titleId} className="household-picker__title">
        {t("household:picker.title")}
      </h1>
      <p className="household-picker__subtitle">{t("household:picker.subtitle")}</p>
      <ul className="household-picker__grid">
        {session.members.map((member, index) => (
          <li key={member.id} style={{ "--index": index } as React.CSSProperties}>
            <button
              type="button"
              className="household-tile"
              data-active={member.id === session.active_id || undefined}
              style={{ "--profile-color": member.color } as React.CSSProperties}
              onClick={() => go(member)}
              disabled={switcher.isPending}
              aria-describedby={member.needs_pin ? `${titleId}-locked` : undefined}
            >
              <ProfileFace member={member} />
              <span className="household-tile__name">{member.display_name}</span>
              <span className="household-tile__kind">
                {member.kind === "owner" ? <Icon name="crown" size={14} /> : null}
                {t(`household:kind.${member.kind}`)}
              </span>
              {member.has_pin ? (
                <span className="household-tile__lock" title={t("household:picker.locked")}>
                  <Icon name="lock" size={14} />
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
      <span id={`${titleId}-locked`} hidden>
        {t("household:picker.locked")}
      </span>
      <div className="household-picker__actions">
        {owner && session.active_id === owner.id ? (
          <Button variant="secondary" onClick={() => go(owner, "/household")} disabled={switcher.isPending}>
            <Icon name="settings" size={16} />
            {t("household:picker.manage")}
          </Button>
        ) : null}
        {onCancel ? (
          <Button variant="ghost" onClick={onCancel}>
            {t("household:picker.back")}
          </Button>
        ) : null}
      </div>
      {switcher.isError && !asking ? <p role="alert">{t("household:error")}</p> : null}
      {asking ? (
        <PinPad
          member={asking.member}
          pending={switcher.isPending}
          error={switcher.error}
          onSubmit={(pin) => switcher.mutate({ user_id: asking.member.id, pin, next: asking.next })}
          onClose={() => {
            switcher.reset();
            setAsking(null);
          }}
        />
      ) : null}
    </main>
  );
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
const SLOTS = [0, 1, 2, 3, 4, 5];

/** The PIN pad: a real field (keyboard, paste, screen readers) and big keys for fingers and remotes. */
export function PinPad({
  member,
  pending,
  error,
  onSubmit,
  onClose,
}: {
  member: Pick<MemberTile, "id" | "display_name" | "color" | "has_avatar">;
  pending: boolean;
  error: unknown;
  onSubmit: (pin: string) => void;
  onClose: () => void;
}) {
  const t = useT();
  const [pin, setPin] = useState("");
  const field = useRef<HTMLInputElement>(null);
  const [shake, setShake] = useState(0);
  const problem = error instanceof ApiError ? error : null;
  useEffect(() => {
    if (problem?.code === "household.wrong_pin") {
      setPin("");
      setShake((n) => n + 1);
      field.current?.focus();
    }
  }, [problem]);
  const press = (digit: string) => setPin((value) => (value.length < 6 ? value + digit : value));
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (pin.length >= 4 && !pending) onSubmit(pin);
  };
  const seconds = Number(problem?.extensions.retry_after ?? 0);
  return (
    <Dialog
      trigger={null}
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={t("household:pin.title", { name: member.display_name })}
      description={t("household:pin.hint")}
      closeLabel={t("household:editor.cancel")}
    >
      <form className="household-pin" onSubmit={submit} key={shake} data-shake={shake > 0 || undefined}>
        <ProfileFace member={member} size="md" />
        <label className="household-pin__field">
          <span className="visually-hidden">{t("household:pin.field")}</span>
          <input
            ref={field}
            type="password"
            inputMode="numeric"
            autoComplete="off"
            pattern="[0-9]*"
            maxLength={6}
            value={pin}
            autoFocus
            onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 6))}
            aria-invalid={problem ? true : undefined}
          />
        </label>
        <span className="household-pin__dots" aria-hidden="true">
          {SLOTS.map((slot) => (
            <span
              key={slot}
              data-filled={slot < pin.length || undefined}
              data-optional={slot >= 4 || undefined}
            />
          ))}
        </span>
        {problem ? (
          <p role="alert" className="household-pin__error">
            {problem.code === "household.pin_throttled"
              ? t("household:pin.throttled", { seconds })
              : problem.code === "household.wrong_pin"
                ? t("household:pin.wrong")
                : t("household:error")}
          </p>
        ) : null}
        <div className="household-pin__keys">
          {KEYS.map((digit) => (
            <button
              key={digit}
              type="button"
              onClick={() => press(digit)}
              aria-label={t("household:pin.digit", { digit })}
            >
              {digit}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setPin((v) => v.slice(0, -1))}
            aria-label={t("household:pin.erase")}
          >
            <Icon name="back" size={20} />
          </button>
          <button
            type="button"
            onClick={() => press("0")}
            aria-label={t("household:pin.digit", { digit: "0" })}
          >
            0
          </button>
          <button
            type="submit"
            className="household-pin__open"
            disabled={pin.length < 4 || pending}
            aria-label={t("household:pin.open")}
          >
            <Icon name="check" size={20} />
          </button>
        </div>
        <DialogActions>
          <Button type="submit" disabled={pin.length < 4 || pending}>
            {t("household:pin.open")}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
