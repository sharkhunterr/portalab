import { createContext, useContext } from "react";

export interface PaletteControl {
  open: (query?: string) => void;
  openShortcuts: () => void;
}

export const PaletteContext = createContext<PaletteControl>({
  open: () => undefined,
  openShortcuts: () => undefined,
});

export function usePalette(): PaletteControl {
  return useContext(PaletteContext);
}
