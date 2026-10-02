import { useState } from "react";
import { Button } from "../../design-system/components/Button";
import { useBreakpoint } from "../../design-system/components/Layout";
import { Drawer } from "../../design-system/components/Overlays";
import { shellStrings } from "../strings";
import { PrimaryNav } from "./PrimaryNav";

/**
 * Responsive navigation (spec 004 T032, FR-022/023): a sidebar on wide screens (collapsible), a drawer on
 * small screens — the same destination set everywhere.
 */
export function ResponsiveNav({ collapsed = false }: { collapsed?: boolean }) {
  const wide = useBreakpoint("md");
  const [open, setOpen] = useState(false);
  if (wide) {
    return collapsed ? null : (
      <nav aria-label={shellStrings.mainNav} className="shell-sidebar">
        <PrimaryNav />
      </nav>
    );
  }
  return (
    <Drawer
      title={shellStrings.mainNav}
      open={open}
      onOpenChange={setOpen}
      closeLabel={shellStrings.closeMenu}
      trigger={<Button variant="secondary">{shellStrings.menu}</Button>}
    >
      <nav aria-label={shellStrings.mainNav}>
        <PrimaryNav onNavigate={() => setOpen(false)} />
      </nav>
    </Drawer>
  );
}
