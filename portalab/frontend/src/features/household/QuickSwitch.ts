import { useMe } from "../auth/useAuth";
import { chooseProfile, type MemberTile, useHouseholdSession, useSwitchProfile } from "./api";

export interface QuickSwitch {
  member: MemberTile;
  icon: string;
  go: () => void;
}

/**
 * Spec 032: the other household members, one tap away from the avatar menu (and the phone's drawer) — a
 * protected one opens its PIN pad, the others switch at once.
 */
export function useQuickSwitch(): QuickSwitch[] {
  const household = (useMe().data?.household_profiles ?? 0) > 0;
  const session = useHouseholdSession(household);
  const switcher = useSwitchProfile();
  const state = session.data;
  if (!household || !state?.enabled) return [];
  return state.members
    .filter((member) => member.id !== state.active_id)
    .map((member) => ({
      member,
      icon: member.needs_pin
        ? "lock"
        : member.kind === "owner"
          ? "crown"
          : member.kind === "child"
            ? "smile"
            : "user",
      go: () => (member.needs_pin ? chooseProfile(member.id) : switcher.mutate({ user_id: member.id })),
    }));
}
