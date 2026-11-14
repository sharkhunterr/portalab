import { useState } from "react";
import { Button } from "../../design-system/components/Button";
import { Icon } from "../../design-system/components/Icon";
import { useNotify } from "../../design-system/components/Notification";
import { Dialog } from "../../design-system/components/Overlays";
import { useT } from "../../i18n/hooks/useT";
import { Switch } from "../account/SettingsKit";
import { useMe } from "../auth/useAuth";
import { type HouseholdMember, useHousehold, useUpdateProfile } from "./api";
import { ProfileFace } from "./ProfilePicker";

/**
 * Spec 032: on a title's page, the master keeps it out of one profile or another — whatever its rating — with
 * a switch per profile (it then shows in « Titles kept out » of the profile's restrictions).
 */
export function TitleRestrictions({ objectId, title }: { objectId: string; title: string }) {
  const t = useT();
  const me = useMe().data;
  const master = Boolean(me && !me.profile_of && (me.household_profiles ?? 0) > 0);
  const [open, setOpen] = useState(false);
  if (!master) return null;
  return (
    <>
      <Button variant="ghost" onClick={() => setOpen(true)} title={t("household:title.restrictHint")}>
        <Icon name="shield" size={16} />
        {t("household:title.restrict")}
      </Button>
      {open ? <Profiles objectId={objectId} title={title} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function Profiles({ objectId, title, onClose }: { objectId: string; title: string; onClose: () => void }) {
  const t = useT();
  const notify = useNotify();
  const household = useHousehold();
  const update = useUpdateProfile();
  const profiles = (household.data?.members ?? []).filter((m) => m.kind !== "owner" && m.restrictions);
  const kept = (member: HouseholdMember) =>
    (member.restrictions?.titles ?? []).some((k) => k.id === objectId);
  const set = (member: HouseholdMember, on: boolean) => {
    const restrictions = member.restrictions;
    if (!restrictions) return;
    const others = (restrictions.titles ?? []).filter((k) => k.id !== objectId);
    update.mutate(
      {
        id: member.id,
        restrictions: { ...restrictions, titles: on ? [...others, { id: objectId, title }] : others },
      },
      { onSuccess: () => notify({ severity: "success", title: t("household:title.saved") }) },
    );
  };
  return (
    <Dialog
      trigger={null}
      open
      onOpenChange={(next) => (next ? undefined : onClose())}
      title={t("household:title.restrict")}
      description={t("household:title.restrictHint")}
      closeLabel={t("household:editor.cancel")}
    >
      <ul className="household-kept">
        {profiles.map((member) => (
          <li key={member.id}>
            <ProfileFace member={member} size="sm" />
            <Switch
              label={t("household:title.kept", { name: member.display_name })}
              checked={kept(member)}
              disabled={update.isPending}
              onChange={(event) => set(member, event.target.checked)}
            />
          </li>
        ))}
      </ul>
    </Dialog>
  );
}
