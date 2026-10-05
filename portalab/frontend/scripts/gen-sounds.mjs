#!/usr/bin/env node
/**
 * Generates the themes' sound sets (spec 027 R18): short synthesized tones written as 16-bit mono WAV
 * files under `public/assets/sounds/<set>/` — the default `portalab` set and one per universe family
 * (magic bells, sci-fi sweeps, digital bleeps, spooky drones, cartoon boings, chiptune, soft marimba,
 * disco). No third-party audio, no licensing question; rerun with `npm run gen:sounds` after a change.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RATE = 22050;
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "assets", "sounds");

/**
 * A note: frequency (Hz, optionally gliding to `to`), start and length (s), peak gain, waveform (sine,
 * triangle, square, saw, noise), optional vibrato (Hz) and decay speed.
 */
const PORTALAB = {
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

const n = (f, at, len, gain, extra = {}) => ({ f, at, len, gain, ...extra });
const arpeggio = (freqs, step, len, gain, extra = {}) =>
  freqs.map((f, i) => n(f, i * step, len, gain, extra));

const SETS = {
  portalab: PORTALAB,
  // wizardry, Christmas: bells with shimmering overtones
  magic: {
    notification: [n(1568, 0, 0.5, 0.22, { bell: true }), n(2093, 0.08, 0.6, 0.16, { bell: true })],
    alert: [n(392, 0, 0.35, 0.3, { wave: "triangle" }), n(370, 0.2, 0.45, 0.3, { wave: "triangle" })],
    success: arpeggio([1047, 1319, 1568, 2093], 0.07, 0.5, 0.18, { bell: true }),
    reward: arpeggio([2093, 2637, 3136], 0.05, 0.45, 0.14, { bell: true }),
    levelUp: arpeggio([784, 988, 1175, 1568, 1976, 2349], 0.08, 0.7, 0.16, { bell: true }),
    ui: [n(2637, 0, 0.12, 0.1, { bell: true })],
  },
  // space opera, futuristic, alien: sweeps
  scifi: {
    notification: [n(600, 0, 0.18, 0.3, { to: 1400 }), n(1400, 0.18, 0.1, 0.2)],
    alert: [
      n(880, 0, 0.25, 0.32, { to: 440, wave: "triangle" }),
      n(880, 0.3, 0.25, 0.32, { to: 440, wave: "triangle" }),
    ],
    success: [n(400, 0, 0.3, 0.3, { to: 1200 }), n(1200, 0.28, 0.2, 0.2, { vibrato: 12 })],
    reward: [n(1800, 0, 0.25, 0.22, { to: 2600, vibrato: 30 })],
    levelUp: [n(300, 0, 0.6, 0.3, { to: 1600 }), n(1600, 0.55, 0.4, 0.22, { vibrato: 8 })],
    ui: [n(1200, 0, 0.05, 0.12, { to: 1800 })],
  },
  // simulation, cyberpunk: digital bleeps and glitches
  digital: {
    notification: [n(1320, 0, 0.05, 0.18, { wave: "square" }), n(1760, 0.07, 0.05, 0.18, { wave: "square" })],
    alert: [
      n(220, 0, 0.12, 0.22, { wave: "square" }),
      n(0, 0.12, 0.1, 0.15, { wave: "noise" }),
      n(220, 0.24, 0.16, 0.22, { wave: "square" }),
    ],
    success: arpeggio([880, 1175, 1760], 0.05, 0.06, 0.16, { wave: "square" }),
    reward: [n(0, 0, 0.06, 0.12, { wave: "noise" }), n(2349, 0.05, 0.1, 0.16, { wave: "square" })],
    levelUp: arpeggio([440, 587, 880, 1175, 1760], 0.06, 0.08, 0.16, { wave: "square" }),
    ui: [n(0, 0, 0.025, 0.08, { wave: "noise" })],
  },
  // horror, Halloween: low detuned drones, minor intervals
  spooky: {
    notification: [
      n(220, 0, 0.6, 0.3, { wave: "triangle", vibrato: 5 }),
      n(233, 0, 0.6, 0.18, { wave: "triangle" }),
    ],
    alert: [n(110, 0, 0.7, 0.4, { wave: "saw", vibrato: 4 }), n(116.5, 0, 0.7, 0.25, { wave: "saw" })],
    success: arpeggio([294, 349, 440], 0.12, 0.5, 0.2, { wave: "triangle", vibrato: 5 }),
    reward: [n(880, 0, 0.6, 0.18, { to: 440, vibrato: 7 })],
    levelUp: arpeggio([147, 175, 220, 262, 330], 0.14, 0.7, 0.2, { wave: "triangle", vibrato: 4 }),
    ui: [n(330, 0, 0.08, 0.1, { wave: "triangle" })],
  },
  // comic, manga, cartoon: boings and pops
  toon: {
    notification: [n(500, 0, 0.18, 0.3, { to: 900, vibrato: 18 })],
    alert: [n(900, 0, 0.2, 0.32, { to: 300 }), n(300, 0.2, 0.15, 0.25, { to: 500 })],
    success: [n(400, 0, 0.12, 0.28, { to: 800 }), n(800, 0.12, 0.2, 0.25, { to: 1200, vibrato: 20 })],
    reward: [n(1200, 0, 0.08, 0.2), n(1600, 0.06, 0.08, 0.2), n(2000, 0.12, 0.18, 0.2)],
    levelUp: [n(300, 0, 0.5, 0.3, { to: 1500, vibrato: 14 }), n(1500, 0.5, 0.3, 0.2, { vibrato: 20 })],
    ui: [n(700, 0, 0.05, 0.14, { to: 1100 })],
  },
  // neowave, retro: 8-bit chiptune
  chiptune: {
    notification: arpeggio([988, 1319], 0.06, 0.08, 0.14, { wave: "square" }),
    alert: arpeggio([392, 330, 262], 0.09, 0.1, 0.16, { wave: "square" }),
    success: arpeggio([523, 659, 784, 1047], 0.06, 0.08, 0.14, { wave: "square" }),
    reward: arpeggio([1568, 2093, 2637, 3136], 0.04, 0.06, 0.12, { wave: "square" }),
    levelUp: arpeggio([523, 659, 784, 1047, 784, 1047, 1319], 0.07, 0.1, 0.14, { wave: "square" }),
    ui: [n(1568, 0, 0.03, 0.1, { wave: "square" })],
  },
  // cozy, minimal, desert: soft wooden marimba
  soft: {
    notification: [n(659, 0, 0.3, 0.28, { decay: 10 }), n(988, 0.1, 0.3, 0.22, { decay: 10 })],
    alert: [n(330, 0, 0.35, 0.3, { decay: 8 }), n(311, 0.18, 0.4, 0.3, { decay: 8 })],
    success: arpeggio([523, 659, 784], 0.1, 0.35, 0.24, { decay: 9 }),
    reward: arpeggio([1047, 1319], 0.08, 0.3, 0.2, { decay: 10 }),
    levelUp: arpeggio([392, 494, 587, 784, 988], 0.11, 0.45, 0.22, { decay: 8 }),
    ui: [n(988, 0, 0.06, 0.1, { decay: 14 })],
  },
  // disco, heroes: funky octaves
  disco: {
    notification: [n(523, 0, 0.1, 0.22, { wave: "saw" }), n(1047, 0.1, 0.16, 0.18, { wave: "saw" })],
    alert: [n(196, 0, 0.18, 0.3, { wave: "saw" }), n(185, 0.2, 0.25, 0.3, { wave: "saw" })],
    success: arpeggio([392, 494, 587, 784], 0.08, 0.14, 0.18, { wave: "saw" }),
    reward: [n(1568, 0, 0.12, 0.18, { wave: "saw", vibrato: 9 }), n(2093, 0.1, 0.2, 0.15, { wave: "saw" })],
    levelUp: arpeggio([262, 330, 392, 523, 659, 784, 1047], 0.07, 0.16, 0.18, { wave: "saw" }),
    ui: [n(1319, 0, 0.04, 0.1, { wave: "saw" })],
  },
};

let seed = 1;
function noise() {
  seed = (seed * 16807) % 2147483647;
  return (seed / 2147483647) * 2 - 1;
}

function sample(wave, phase) {
  if (wave === "triangle") return (2 / Math.PI) * Math.asin(Math.sin(phase));
  if (wave === "square") return Math.sin(phase) >= 0 ? 0.6 : -0.6;
  if (wave === "saw") return 0.6 * (2 * ((phase / (2 * Math.PI)) % 1) - 1);
  if (wave === "noise") return noise() * 0.6;
  return Math.sin(phase);
}

function render(notes) {
  const length = Math.max(...notes.map((note) => note.at + note.len)) + 0.05;
  const data = new Float32Array(Math.ceil(length * RATE));
  for (const note of notes) {
    const start = Math.floor(note.at * RATE);
    const count = Math.floor(note.len * RATE);
    let phase = 0;
    for (let i = 0; i < count; i += 1) {
      const t = i / RATE;
      const progress = i / count;
      const glide = note.to ? note.f + (note.to - note.f) * progress : note.f;
      const frequency = glide * (note.vibrato ? 1 + 0.015 * Math.sin(2 * Math.PI * note.vibrato * t) : 1);
      phase += (2 * Math.PI * frequency) / RATE;
      const attack = Math.min(1, t / 0.008);
      const release = Math.exp((-(note.decay ?? 4) * t) / note.len);
      let value = sample(note.wave, phase);
      if (note.bell) value = 0.6 * value + 0.25 * Math.sin(phase * 2.76) + 0.15 * Math.sin(phase * 5.4);
      data[start + i] += value * note.gain * attack * release;
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

let total = 0;
for (const [set, recipes] of Object.entries(SETS)) {
  const out = join(ROOT, set);
  mkdirSync(out, { recursive: true });
  for (const [name, notes] of Object.entries(recipes)) {
    const file = name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`); // asset names are lowercase
    writeFileSync(join(out, `${file}.wav`), wav(render(notes)));
    total += 1;
  }
}
process.stdout.write(`generated ${total} sounds in ${ROOT}\n`);
