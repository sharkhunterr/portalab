import { fingerprint, getBytes, putBytes, type Sitting } from "./api";

/** The emulator's own API, as far as the play page uses it (EmulatorJS 4). */
export type Emulator = {
  pause?: (silent?: boolean) => void;
  controls?: unknown; // 421: the controls the member set (keyboard and gamepads)
  settings?: Record<string, unknown>;
  on?: (event: string, callback: (data: unknown) => void) => void;
  // 4.2 answers ``blob``, later versions ``screenshot`` (the PNG's bytes)
  takeScreenshot?: (source: string, format: string, upscale: number) => Promise<Shot>;
  canvas?: HTMLCanvasElement;
  gameManager?: {
    saveSaveFiles?: () => void;
    getSaveFile?: (save?: boolean) => Uint8Array | null;
    getSaveFilePath?: () => string;
    loadSaveFiles?: () => void;
    getState?: () => Uint8Array;
    loadState?: (state: Uint8Array) => void;
    FS?: { writeFile: (path: string, data: Uint8Array) => void };
  };
};

export function emulator(): Emulator | undefined {
  return (window as unknown as { EJS_emulator?: Emulator }).EJS_emulator;
}

type Shot = { blob?: Blob | null; screenshot?: Uint8Array | null; format?: string } | null | undefined;

const PICTURE_WAIT_MS = 2000; // the core's frame is written within a frame or two: past this, the stage is taken

function within<T>(promise: Promise<T>, ms: number): Promise<T | null> {
  return Promise.race([promise, new Promise<null>((resolve) => setTimeout(() => resolve(null), ms))]);
}

function asBlob(shot: Shot): Blob | null {
  if (shot?.blob) return shot.blob;
  if (shot?.screenshot?.length) return new Blob([shot.screenshot as BlobPart], { type: "image/png" });
  return null;
}

/** The smallest box holding every pixel brighter than the stage's black around the game (null: all black). */
export function contentBox(
  image: { data: ArrayLike<number>; width: number; height: number },
  threshold = 16,
): { x: number; y: number; width: number; height: number } | null {
  const { data, width, height } = image;
  let top = height;
  let left = width;
  let bottom = -1;
  let right = -1;
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      if (Math.max(data[i] ?? 0, data[i + 1] ?? 0, data[i + 2] ?? 0) <= threshold) continue;
      top = Math.min(top, y);
      bottom = Math.max(bottom, y);
      left = Math.min(left, x);
      right = Math.max(right, x);
    }
  return bottom < 0 ? null : { x: left, y: top, width: right - left + 1, height: bottom - top + 1 };
}

/** The emulator's whole canvas, its black bands cut off (where the game is drawn depends on the screen). */
function stage(source: HTMLCanvasElement | undefined): Promise<Blob | null> {
  if (!source?.width || !source.height) return Promise.resolve(null);
  return new Promise((resolve) =>
    // read in the frame the emulator draws, before the browser clears a WebGL canvas
    requestAnimationFrame(() => {
      try {
        const copy = document.createElement("canvas");
        copy.width = source.width;
        copy.height = source.height;
        const context = copy.getContext("2d", { willReadFrequently: true });
        if (!context) return resolve(null);
        context.drawImage(source, 0, 0);
        const box = contentBox(context.getImageData(0, 0, copy.width, copy.height));
        if (!box) return resolve(null);
        const out = document.createElement("canvas");
        out.width = box.width;
        out.height = box.height;
        out
          .getContext("2d")
          ?.drawImage(copy, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height);
        out.toBlob((blob) => resolve(blob), "image/png");
      } catch {
        resolve(null);
      }
    }),
  );
}

/**
 * The screen as a PNG picture (none when the emulator cannot take one): the core's own frame, at the game's
 * size. Not EmulatorJS's « canvas » picture — on a phone held upright the game is drawn at the top of the
 * stage and 4.2 crops its middle: half the game over a black band. (Its core picture answers only for
 * upscale 0 in 4.2, hence 0, and waits for a file that may never come, hence the limit.)
 */
export async function picture(): Promise<Blob | null> {
  const e = emulator();
  if (!e) return null;
  try {
    const core = e.takeScreenshot
      ? asBlob(await within(e.takeScreenshot("retroarch", "png", 0), PICTURE_WAIT_MS))
      : null;
    return core ?? (await stage(e.canvas));
  } catch {
    return null;
  }
}

const KEEPALIVE_BYTES = 60_000; // what a page going away may still send

/**
 * Issue 420: the sitting's saves, kept by the portal — the game's own save sent only when the game changed it,
 * the states in their slots with the screen's picture, loaded back into the emulator.
 */
export class SaveKeeper {
  private sent: string | null = null;

  constructor(private readonly sitting: Sitting) {}

  get sramUrl(): string {
    return `${this.sitting.saves_path}sram`;
  }

  stateUrl(slot: number): string {
    return `${this.sitting.saves_path}states/${slot}`;
  }

  pictureUrl(slot: number, version: string): string {
    return `${this.stateUrl(slot)}/picture?v=${encodeURIComponent(version)}`;
  }

  /** The game's own save, as the emulator wrote it; unchanged, nothing is sent. */
  async keepSram(data: Uint8Array | null | undefined, leaving = false): Promise<boolean> {
    if (!data?.length) return false;
    const print = fingerprint(data);
    if (print === this.sent) return false;
    if (leaving && data.length > KEEPALIVE_BYTES) return false;
    const before = this.sent;
    this.sent = print; // claimed at once: the same save written twice in a row goes once
    const ok = await putBytes(this.sramUrl, data, leaving).catch(() => false);
    if (!ok) this.sent = before;
    return ok;
  }

  async keepState(slot: number, state: Uint8Array, shot: Blob | null): Promise<boolean> {
    const ok = await putBytes(this.stateUrl(slot), state).catch(() => false);
    if (ok && shot) await putBytes(`${this.stateUrl(slot)}/picture`, shot).catch(() => false);
    return ok;
  }

  /** The game's own save written where the emulator reads it, then read by the game. */
  async loadSram(): Promise<boolean> {
    const data = await getBytes(this.sramUrl).catch(() => null);
    const manager = emulator()?.gameManager;
    const path = manager?.getSaveFilePath?.();
    if (!data || !manager?.FS || !path) return false;
    manager.FS.writeFile(path, data);
    manager.loadSaveFiles?.();
    this.sent = fingerprint(data);
    return true;
  }

  async loadState(slot: number): Promise<boolean> {
    const data = await getBytes(this.stateUrl(slot)).catch(() => null);
    const manager = emulator()?.gameManager;
    if (!data || !manager?.loadState) return false;
    manager.loadState(data);
    return true;
  }

  /** The current state in a slot, with the screen's picture (false: the game has none to give). */
  async saveCurrent(slot: number): Promise<boolean> {
    let state: Uint8Array | undefined;
    try {
      state = emulator()?.gameManager?.getState?.();
    } catch {
      return false; // the core keeps no states
    }
    if (!state?.length) return false;
    return this.keepState(slot, state, await picture());
  }

  /** The game's own save as it is now (the emulator writes it down first). */
  currentSram(): Uint8Array | null {
    try {
      return emulator()?.gameManager?.getSaveFile?.(true) ?? null;
    } catch {
      return null;
    }
  }
}
