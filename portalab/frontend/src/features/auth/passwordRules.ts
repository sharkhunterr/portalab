import type { useT } from "../../i18n/hooks/useT";
import { ApiError } from "../../state/regions";

/** Issue 406: why a new password was refused — too short, found in data breaches, holding the login or
 * name — in the reader's language; ``null`` for any other error. */
export function passwordRuleMessage(error: unknown, t: ReturnType<typeof useT>): string | null {
  if (!(error instanceof ApiError)) return null;
  if (error.code === "user.password_common") return t("account:signInPhrase.common");
  if (error.code === "user.password_personal") return t("account:signInPhrase.personal");
  if (error.code === "user.password_invalid")
    return t("account:signInPhrase.policy", { min: Number(error.extensions.min_length ?? 12) });
  return null;
}
