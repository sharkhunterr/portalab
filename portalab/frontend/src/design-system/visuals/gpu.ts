import { externalLook, fxName, useExternalRevision } from "./registry";

/**
 * 028 (B2): how a look is drawn by the GPU — found in its pack, Portalab's own included (none is written in
 * the interface's code): the effect it runs (its fragment, registered by the registry), the shape it is drawn
 * in (frames, notifications), its corner radius, whether it covers the whole stage, from when in its
 * timeline it plays, whether it comes and goes over and over. ``undefined``: a look of CSS only (or none).
 */
export interface GpuLook {
  effect: string;
  shape: number;
  radius?: string;
  stage: boolean;
  start: number;
  cycle: boolean;
}

// a badge's and a title's styles are one vocabulary: either's element draws the other
const SHARED: Record<string, string> = { title: "badge", badge: "title" };

export function gpuLook(type: string, look: string | null | undefined): GpuLook | undefined {
  if (!look) return undefined;
  for (const kind of [type, SHARED[type]]) {
    const element = kind ? externalLook(kind, look) : undefined;
    if (element?.kind === "glsl" && element.file)
      return {
        effect: fxName(element),
        shape: element.shape ?? 0,
        ...(element.radius ? { radius: element.radius } : {}),
        stage: Boolean(element.stage),
        start: element.start ?? 0,
        cycle: Boolean(element.cycle),
      };
  }
  return undefined;
}

/** ``gpuLook``, drawn again when the packs are installed or change. */
export function useGpuLook(type: string, look: string | null | undefined): GpuLook | undefined {
  useExternalRevision();
  return gpuLook(type, look);
}
