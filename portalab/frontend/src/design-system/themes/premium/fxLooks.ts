/**
 * #73, #77, #78 / 028: the looks drawn by the GPU are their packs' (Portalab's own included): each element
 * holds its effect's fragment and how it is drawn (``visuals/gpu``) — none is listed here. What stays is the
 * renderer's own: the outline each frame shape cuts the avatar to.
 */
import { gpuLook } from "../../visuals/gpu";

export interface FxSpec {
  effect: string;
  shape?: number;
  radius?: string;
  /** comes and goes over and over */
  cycle?: boolean;
}

/** issue 1 / 028: the GPU frame drawing ``key``, from its pack. */
export function fxFrameOf(key: string | null | undefined): FxSpec | undefined {
  const look = gpuLook("avatar_frame", key);
  if (!look) return undefined;
  return {
    effect: look.effect,
    shape: look.shape,
    ...(look.radius ? { radius: look.radius } : {}),
    ...(look.cycle ? { cycle: true } : {}),
  };
}

/** CSS clip of an avatar inside a shaped frame. */
export const FRAME_CLIPS: Record<number, string> = {
  1: "polygon(25% 3%, 75% 3%, 98% 50%, 75% 97%, 25% 97%, 2% 50%)",
  2: "polygon(50% 2%, 98% 50%, 50% 98%, 2% 50%)",
  3: "polygon(6% 4%, 94% 4%, 94% 52%, 50% 98%, 6% 52%)",
  5: "polygon(50% 6%, 97% 90%, 3% 90%)",
  4: "polygon(50% 4%, 61% 36%, 96% 38%, 68% 58%, 78% 92%, 50% 72%, 22% 92%, 32% 58%, 4% 38%, 39% 36%)",
};
