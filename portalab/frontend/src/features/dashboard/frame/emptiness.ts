import { createContext, useContext } from "react";

/**
 * 027: widgets set to « hide when empty » tell the dashboard when they have nothing to show; the grid
 * keeps them mounted (they may fill up again) but out of the layout, and closes the gap they leave.
 */
export const EmptyWidgets = createContext<(key: string, empty: boolean) => void>(() => {});

export const useEmptyReport = () => useContext(EmptyWidgets);
