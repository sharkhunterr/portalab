import { api } from "../../api/client";
import type { PreferenceBackend } from "../../design-system/a11y/PreferencesProvider";
import type { UiPolicy } from "../../design-system/a11y/preferences";

/** ``/me/preferences`` (020) + ``/ui/themes`` policy (022) as the preference backend of the design system. */
export const preferenceBackend: PreferenceBackend = {
  async load() {
    const [prefs, catalog] = await Promise.all([
      api.GET("/api/v1/me/preferences"),
      api.GET("/api/v1/ui/themes"),
    ]);
    const views = ((prefs.data as unknown as { preferences?: Array<{ key: string; value: unknown }> })
      ?.preferences ?? []) as Array<{ key: string; value: unknown }>;
    const values = Object.fromEntries(
      views.filter((v) => v.key.startsWith("ui.")).map((v) => [v.key, v.value]),
    );
    const policy = (catalog.data as unknown as { policy?: UiPolicy })?.policy;
    return policy ? { preferences: values, policy } : { preferences: values };
  },
  async save(values) {
    await api.PUT("/api/v1/me/preferences", { body: values as never });
  },
};
