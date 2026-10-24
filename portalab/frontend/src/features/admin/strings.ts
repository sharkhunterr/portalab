import { useStrings } from "../../i18n/hooks/useStrings";

/** The first-run screen's strings (spec 020 T030) — issue 201: read from the catalogs (``admin:firstRun.*``). */
export const adminStrings = {
  wizardTitle: "Set up your portal",
  wizardIntro:
    "Create the administrator account. Once signed in, the setup assistant takes you through the rest, step by step.",
  loginField: "Administrator login",
  passwordField: "Password",
  passwordHint: "At least 12 characters.",
  displayNameField: "Display name",
  finish: "Create the account",
  finished: "Your portal is ready. Sign in with the administrator account: the setup assistant will guide you.",
  signIn: "Sign in",
  closed: "The portal is already set up.",
  genericError: "Something went wrong. Try again.",
} as const;

export function useAdminStrings() {
  return useStrings(adminStrings, "admin:firstRun");
}
