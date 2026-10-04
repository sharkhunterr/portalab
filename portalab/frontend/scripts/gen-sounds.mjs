#!/usr/bin/env node
/**
 * Generates the default theme's sound set (spec 027 R18): short synthesized tones written as 16-bit mono
 * WAV files under `public/assets/sounds/portalab/`. No third-party audio, no licensing question; rerun
 * with `npm run gen:sounds` after changing a recipe.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RATE = 22050;
const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "assets", "sounds", "portalab");

/** A note: frequency (Hz), start and length (s), peak gain, waveform. */
const RECIPES = {
  notification: [
    { f: 880, at: 0, len: 0.12, gain: 0.35 },
    { f: 1318.5, at: 0.09, len: 0.18, gain: 0.3 },
  ],
  alert: [
    { f: 659.3, at: 0, len: 0.14, gain: 0.4, wave: "triangle" },
    { f: 523.3, at: 0.16, len: 0.22, gain: 0.4, wave: "triangle" },
  ],
  success: [
    { f: 523.3, at: 0, len: 0.1, gain: 0.3 },
    { f: 659.3, at: 0.08, len: 0.1, gain: 0.3 },
    { f: 784, at: 0.16, len: 0.2, gain: 0.3 },
  ],
  reward: [
    { f: 1046.5, at: 0, len: 0.08, gain: 0.25 },
    { f: 1568, at: 0.06, len: 0.16, gain: 0.25 },
  ],
  levelUp: [
    { f: 523.3, at: 0, len: 0.12, gain: 0.3 },
    { f: 659.3, at: 0.1, len: 0.12, gain: 0.3 },
    { f: 784, at: 0.2, len: 0.12, gain: 0.3 },
    { f: 1046.5, at: 0.3, len: 0.35, gain: 0.35 },
  ],
  ui: [{ f: 1760, at: 0, len: 0.04, gain: 0.15 }],
};

function sample(wave, phase) {
  if (wave === "triangle") return (2 / Math.PI) * Math.asin(Math.sin(phase));
  return Math.sin(phase);
}

function render(notes) {
  const length = Math.max(...notes.map((n) => n.at + n.len)) + 0.05;
  const data = new Float32Array(Math.ceil(length * RATE));
  for (const note of notes) {
    const start = Math.floor(note.at * RATE);
    const count = Math.floor(note.len * RATE);
    for (let i = 0; i < count; i += 1) {
      const t = i / RATE;
      const attack = Math.min(1, t / 0.008);
      const release = Math.exp((-4 * t) / note.len);
      data[start + i] += sample(note.wave, 2 * Math.PI * note.f * t) * note.gain * attack * release;
    }
  }
  return data;
}

function wav(samples) {
  const buffer = Buffer.alloc(44 + samples.length * 2);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + samples.length * 2, 4);
  buffer.write("WAVEfmt ", 8);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20); // PCM
  buffer.writeUInt16LE(1, 22); // mono
  buffer.writeUInt32LE(RATE, 24);
  buffer.writeUInt32LE(RATE * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(samples.length * 2, 40);
  samples.forEach((value, index) => {
    const clamped = Math.max(-1, Math.min(1, value));
    buffer.writeInt16LE(Math.round(clamped * 32767), 44 + index * 2);
  });
  return buffer;
}

mkdirSync(OUT, { recursive: true });
for (const [name, notes] of Object.entries(RECIPES)) {
  const file = name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`); // asset names are lowercase
  writeFileSync(join(OUT, `${file}.wav`), wav(render(notes)));
}
process.stdout.write(`generated ${Object.keys(RECIPES).length} sounds in ${OUT}\n`);
