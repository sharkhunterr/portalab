"""Plugin admission rule (T039, F19): a plugin that stores personal data must provide a
``privacy.erasure_participant`` — otherwise its load is refused (enforced by the plugin runtime, spec 023)."""


class PluginPrivacyError(ValueError):
    pass


def check_plugin_personal_data(
    owner: str, *, declares_personal_data: bool, has_erasure_participant: bool
) -> None:
    if declares_personal_data and not has_erasure_participant:
        raise PluginPrivacyError(f"{owner} stores personal data without an erasure participant")
