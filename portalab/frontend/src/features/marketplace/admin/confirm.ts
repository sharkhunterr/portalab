import { ApiError } from "../../../state/regions";

/** Run a sensitive admin call, retrying once with the confirmation the server asks for. */
export async function withConfirmation<T>(
  call: (confirmation?: string) => Promise<T>,
  confirm: () => boolean,
): Promise<T> {
  try {
    return await call();
  } catch (error) {
    if (error instanceof ApiError && error.code === "authz.confirmation_required" && confirm()) {
      return call(String(error.extensions.confirmation ?? ""));
    }
    throw error;
  }
}
