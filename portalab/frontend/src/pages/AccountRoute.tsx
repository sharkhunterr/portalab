import { PageHeader } from "../design-system/components/PageHeader";
import { AccountPage } from "../features/auth";
import { useShellStrings } from "../shell/strings";

export default function AccountRoute() {
  const strings = useShellStrings();
  return (
    <>
      <PageHeader icon="user" title={strings.label("nav.account")} />
      <AccountPage />
    </>
  );
}
