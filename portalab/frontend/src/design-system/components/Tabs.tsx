import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

/** Tabs on Radix (arrow-key navigation, roving focus, ``aria-selected``). */
export interface TabItem {
  value: string;
  label: string;
  content: ReactNode;
}

export function Tabs({
  items,
  label,
  defaultValue,
}: {
  items: TabItem[];
  label: string;
  defaultValue?: string;
}) {
  return (
    <TabsPrimitive.Root className="ds-tabs" defaultValue={defaultValue ?? items[0]?.value ?? ""}>
      <TabsPrimitive.List className="ds-tabs__list" aria-label={label}>
        {items.map((item) => (
          <TabsPrimitive.Trigger key={item.value} value={item.value} className="ds-tabs__trigger">
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {items.map((item) => (
        <TabsPrimitive.Content key={item.value} value={item.value} className="ds-tabs__panel">
          {item.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}
