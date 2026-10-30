#!/usr/bin/env node
/**
 * The GitLab issues closed since the last release, sorted by kind — the « Closed issues » part of the next
 * release notes (GITHUB_RELEASES.md). Read with glab (logged in to the GitLab instance); nothing is written.
 *
 *   npm run release:issues                 # since the latest tag
 *   npm run release:issues -- --since v1.2.0
 *
 * Kinds come from the labels: security, bug, feature, documentation / deploy (tooling); anything else is an
 * improvement. Titles are printed as written in GitLab: the notes are in English, so rewrite each line as a
 * member or an administrator would read it, keeping its « #123 ».
 */

const { execSync } = require('child_process');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PROJECT = process.env.GITLAB_PROJECT || 'root/portalab';

const args = process.argv.slice(2);
const sinceArg = args.includes('--since') ? args[args.indexOf('--since') + 1] : null;

function sh(command) {
  return execSync(command, { encoding: 'utf8', cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

/** The date of a tag (the latest one when none is given), or null when nothing was released yet. */
function since() {
  try {
    const tag = sinceArg || sh('git describe --tags --abbrev=0 --match "v[0-9]*"');
    return { tag, date: sh(`git log -1 --format=%cI ${tag}`) };
  } catch {
    return { tag: null, date: null };
  }
}

const KINDS = [
  ['Security', (labels) => labels.includes('security')],
  ['Fixed', (labels) => labels.includes('bug')],
  ['New', (labels) => labels.includes('feature')],
  ['Documentation and tooling', (labels) => labels.includes('documentation') || labels.includes('deploy')],
  ['Improved', () => true],
];

function closedIssues(after) {
  const out = [];
  for (let page = 1; page < 50; page += 1) {
    const query = [
      'state=closed',
      'per_page=100',
      `page=${page}`,
      'order_by=updated_at',
      ...(after ? [`updated_after=${encodeURIComponent(after)}`] : []),
    ].join('&');
    const rows = JSON.parse(sh(`glab api "projects/${encodeURIComponent(PROJECT)}/issues?${query}"`));
    out.push(...rows);
    if (rows.length < 100) break;
  }
  return out.filter((issue) => !after || (issue.closed_at && issue.closed_at >= after));
}

function main() {
  const { tag, date } = since();
  const issues = closedIssues(date).sort((a, b) => a.iid - b.iid);
  console.log(`<!-- closed since ${tag || 'the beginning'}: ${issues.length} issue(s) -->`);
  console.log('### Closed issues\n');
  const done = new Set();
  for (const [title, matches] of KINDS) {
    const rows = issues.filter((issue) => !done.has(issue.iid) && matches(issue.labels || []));
    if (!rows.length) continue;
    console.log(`#### ${title}\n`);
    for (const issue of rows) {
      done.add(issue.iid);
      console.log(`- ${issue.title} (#${issue.iid})`);
    }
    console.log('');
  }
}

try {
  main();
} catch (error) {
  console.error(`x Could not read the closed issues: ${error.message.split('\n')[0]}`);
  console.error('  glab must be logged in to the GitLab instance (glab auth login).');
  process.exit(1);
}
