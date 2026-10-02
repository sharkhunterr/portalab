/**
 * ``SoundService`` (spec 022 R10, FR-012/018/019): the only place sounds are played. It honours
 * ``ui.soundEnabled``, never autoplays before a user gesture, plays only bundled theme assets and fails
 * silently (a missing asset never breaks a notification).
 */
export type SoundEvent = "notification" | "alert" | "success";

export interface AudioLike {
  play: () => Promise<void>;
}

export class SoundService {
  private gestureSeen = false;
  enabled = true;
  sounds: Partial<Record<SoundEvent, string>> = {};

  constructor(private readonly createAudio: (src: string) => AudioLike = (src) => new Audio(src)) {}

  /** Call from a user-gesture handler (click/keydown) — browsers forbid autoplay before one. */
  noteGesture(): void {
    this.gestureSeen = true;
  }

  listenForGesture(target: Document = document): () => void {
    const mark = () => this.noteGesture();
    target.addEventListener("pointerdown", mark, { once: true });
    target.addEventListener("keydown", mark, { once: true });
    return () => {
      target.removeEventListener("pointerdown", mark);
      target.removeEventListener("keydown", mark);
    };
  }

  resolve(asset: string): string | null {
    const match = /^asset:([a-z0-9][a-z0-9._/-]*)$/.exec(asset);
    return match ? `/assets/sounds/${match[1]}` : null;
  }

  async play(event: SoundEvent): Promise<boolean> {
    if (!this.enabled || !this.gestureSeen) return false;
    const asset = this.sounds[event];
    const src = asset ? this.resolve(asset) : null;
    if (!src) return false;
    try {
      await this.createAudio(src).play();
      return true;
    } catch {
      return false;
    }
  }
}

export const sound = new SoundService();
