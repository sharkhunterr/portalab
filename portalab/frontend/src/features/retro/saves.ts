import { fingerprint, getBytes, putBytes, type Sitting } from "./api";

/** The emulator's own API, as far as the play page uses it (EmulatorJS 4). */
export type Emulator = {
  pause?: (silent?: boolean) => void;
  controls?: unknown; // 421: the controls the member set (keyboard and gamepads)
  settings?: Record<string, unknown>;
  on?: (event: string, callback: (data: unknown) => void) => void;
  takeScreenshot?: (source: string, format: string, upscale: number) => Promise<{ blob?: Blob | null }>;
  capture?: { photo?: { source?: string; upscale?: number } };
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

/** The screen as a PNG picture (none when the emulator cannot take one). */
export async function picture(): Promise<Blob | null> {
  const e = emulator();
  try {
    const taken = await e?.takeScreenshot?.(e.capture?.photo?.source ?? "canvas", "png", 1);
    return taken?.blob ?? null;
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
