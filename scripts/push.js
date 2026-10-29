#!/usr/bin/env node
/**
 * Portalab git push helper.
 *
 *   npm run push          # GitLab (origin), with tags
 *   npm run push:github   # GitHub (remote "github")
 *   npm run push:all      # both
 *   npm run push:tags     # tags only
 *
 * Options: --gitlab --github --all --tags-only --no-tags --force --dry-run
 */

const { execSync } = require('child_process');

const args = process.argv.slice(2);
const options = {
  github: args.includes('--github') || args.includes('--all'),
  gitlab: args.includes('--gitlab') || args.includes('--all') || (!args.includes('--github') && !args.includes('--tags-only')),
  tagsOnly: args.includes('--tags-only'),
  noTags: args.includes('--no-tags'),
  force: args.includes('--force'),
  dryRun: args.includes('--dry-run'),
};
if (options.tagsOnly && !args.includes('--github')) options.gitlab = true;

function remoteUrl(remote) {
  try {
    return execSync(`git remote get-url ${remote}`, { encoding: 'utf8' }).trim();
  } catch {
    return null;
  }
}

function run(command, description) {
  console.log(`\n> ${description}`);
  if (options.dryRun) {
    console.log(`  [dry run] ${command}`);
    return;
  }
  try {
    execSync(command, { stdio: 'inherit' });
  } catch {
    console.error(`x Failed: ${description}`);
    process.exit(1);
  }
}

const branch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf8' }).trim();
if (options.gitlab && !remoteUrl('origin')) {
  console.error('x The GitLab remote (origin) is not configured.');
  process.exit(1);
}
if (options.github && !remoteUrl('github')) {
  console.error('x The GitHub remote is not configured: git remote add github <url>');
  process.exit(1);
}

const force = options.force ? ' --force' : '';
for (const [enabled, remote, name] of [[options.gitlab, 'origin', 'GitLab'], [options.github, 'github', 'GitHub']]) {
  if (!enabled) continue;
  if (options.tagsOnly) run(`git push ${remote} --tags${force}`, `Pushing the tags to ${name}`);
  else run(`git push ${remote} ${branch}${options.noTags ? '' : ' --follow-tags'}${force}`, `Pushing ${branch} to ${name}`);
}
console.log('\nDone.');
