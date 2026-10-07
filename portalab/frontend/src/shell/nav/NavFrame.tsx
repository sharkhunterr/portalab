import { type DeviceClass, useDeviceClass } from "../../design-system/components/Layout";
import { presentationOf } from "../../design-system/themes/schema";
import { useTheme } from "../../design-system/themes/ThemeProvider";

/**
 * Arrangement of the frame (spec 027 R7/R19/R24): which navigation variant and header placement the active
 * theme chose for the current device class. Changing class (rotation, resize) or theme swaps the variant
 * beside the page outlet, which is never remounted — the page keeps its state.
 */
export type NavVariant =
  | "sidebar"
  | "topbar"
  | "rail"
  | "drawer"
  | "bottom-bar"
  | "orbit"
  | "dock"
  | "tabs"
  | "launcher"
  | "terminal"
  | "reel"
  | "lights"
  | "vcr"
  | "sheet";

export interface Arrangement {
  device: DeviceClass;
  nav: NavVariant;
  headerPosition: "top" | "bottom";
}

export function arrangementFor(
  device: DeviceClass,
  presentation: ReturnType<typeof presentationOf>,
): Arrangement {
  let nav: NavVariant = presentation.nav[device];
  // A footer header on a phone merges with the bottom bar: one bar, the menu opens a drawer (R24).
  if (device === "phone" && presentation.headerPosition === "bottom" && nav === "bottom-bar") nav = "drawer";
  return { device, nav, headerPosition: presentation.headerPosition };
}

export function useArrangement(): Arrangement {
  const device = useDeviceClass();
  const { effective } = useTheme();
  return arrangementFor(device, presentationOf(effective.theme));
}
