#!/usr/bin/env node
/**
 * standard-version `postchangelog` hook: CHANGELOG.md names no issue. The GitLab instance is private, so a
 * commit's issue references (« (#383) », « (T081, #1) », « closes #12 », linked or not) are taken out of
 * every line; the other references in a parenthesis (task ids) stay. Runs before the release commit, so the
 * committed changelog is the cleaned one. Also by hand: `node scripts/version/changelog-private.js`.
 */

const fs = require('fs');
const path = require('path');

const FILE = path.join(__dirname, '..', '..', 'CHANGELOG.md');
const ISSUE = /^#\d+(?:[-–]#?\d+)?$/; // one issue, or a range (« #152-154 »)

function clean(line) {
  let out = line
    .replace(/\[(#\d+)\]\([^)]*\)/g, '$1') // a linked reference, as a plain one
    .replace(/,? closes #\d+(?:,? #\d+)*/g, '');
  // a parenthesis of references: the issues out, the rest kept; empty, it goes with its space
  out = out.replace(/ ?\(([^()]*#\d+[^()]*)\)/g, (whole, inside) => {
    const kept = inside
      .split(',')
      .map((part) => part.trim())
      .filter((part) => part && !ISSUE.test(part));
    return kept.length ? ` (${kept.join(', ')})` : '';
  });
  return out;
}

function main() {
  const before = fs.readFileSync(FILE, 'utf8');
  const after = before.split('\n').map(clean).join('\n');
  if (after !== before) fs.writeFileSync(FILE, after);
}

main();
