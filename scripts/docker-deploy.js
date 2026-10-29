#!/usr/bin/env node
/**
 * Build (and push) the Portalab image by hand — the release pipeline does it on every tag.
 *
 *   npm run docker:build          # build locally
 *   npm run docker:deploy         # build and push to Docker Hub
 *   npm run docker:deploy:multi   # linux/amd64 + linux/arm64, pushed
 *
 * The build context is the repository root (portalab/deploy/Dockerfile copies portalab/…).
 * Options: --push --multi-platform --no-latest --dry-run
 */

const { execSync } = require('child_process');
const fs = require('fs');

const args = process.argv.slice(2);
const options = {
  push: args.includes('--push'),
  multiPlatform: args.includes('--multi-platform'),
  latest: !args.includes('--no-latest'),
  dryRun: args.includes('--dry-run'),
};
const DOCKERFILE = 'portalab/deploy/Dockerfile';

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

const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
const version = pkg.version;
const image = `${pkg.config?.dockerRegistry || 'docker.io'}/${pkg.config?.dockerImage || 'sharkhunterr/portalab'}`;
try {
  execSync('docker info', { stdio: 'ignore' });
} catch {
  console.error('x Docker is not running.');
  process.exit(1);
}

const tags = [`${image}:${version}`, `${image}:v${version}`, ...(options.latest ? [`${image}:latest`] : [])];
const tagArgs = tags.map((t) => `-t ${t}`).join(' ');
let revision = 'unknown';
try {
  revision = execSync('git rev-parse HEAD', { encoding: 'utf8' }).trim();
} catch {}
const buildArgs = `--build-arg VERSION=${version} --build-arg VCS_REF=${revision} --build-arg BUILD_DATE=${new Date().toISOString()}`;
console.log(`Portalab ${version} → ${tags.join(', ')}`);

if (options.multiPlatform) {
  run('docker buildx create --use --name portalab-builder 2>/dev/null || docker buildx use portalab-builder', 'Preparing buildx');
  run(
    `docker buildx build --platform linux/amd64,linux/arm64 ${buildArgs} ${tagArgs} ${options.push ? '--push' : '--load'} -f ${DOCKERFILE} .`,
    'Building for linux/amd64 and linux/arm64',
  );
} else {
  run(`docker build ${buildArgs} ${tagArgs} -f ${DOCKERFILE} .`, 'Building the image');
  if (options.push) for (const tag of tags) run(`docker push ${tag}`, `Pushing ${tag}`);
}
console.log(options.push ? `\nPushed: docker pull ${tags[0]}` : '\nBuilt. Push with: npm run docker:deploy');
