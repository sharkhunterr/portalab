#!/usr/bin/env node
/**
 * Portalab graphic-identity renderer.
 *
 * The SVG sources in ``assets/`` are the tracked source of truth. This script renders them with headless
 * Chromium (so the banner uses Portalab's own typeface, Plus Jakarta Sans, from the frontend's
 * node_modules), turns the renders into JPEG / PNG / ICO with Pillow, and installs the web-facing ones
 * into ``portalab/frontend/public/``.
 *
 * Usage:
 *   npm run assets                          # render + install into portalab/frontend/public
 *   node scripts/render-assets.js --no-install
 *
 * Requires: chromium (or google-chrome), python3 with Pillow, and `npm ci` done in portalab/frontend.
 */

const { execFileSync, execSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const ASSETS = path.join(ROOT, 'assets');
const PUBLIC = path.join(ROOT, 'portalab', 'frontend', 'public');
const FONTS = path.join(ROOT, 'portalab', 'frontend', 'node_modules', '@fontsource-variable', 'plus-jakarta-sans', 'files');
const install = !process.argv.includes('--no-install');

function have(bin) {
  try {
    execSync(`command -v ${bin}`, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

const browser = ['chromium', 'chromium-browser', 'google-chrome'].find(have);
if (!browser) {
  console.error('❌ Headless Chromium not found (chromium, chromium-browser or google-chrome).');
  process.exit(1);
}
const font = path.join(FONTS, 'plus-jakarta-sans-latin-wght-normal.woff2');
if (!fs.existsSync(font)) {
  console.error('❌ Plus Jakarta Sans not found — run `npm ci` in portalab/frontend first.');
  process.exit(1);
}

const work = fs.mkdtempSync(path.join(os.tmpdir(), 'portalab-assets-'));

/** One SVG → PNG at ``width``×``height`` (its own fonts, its own relative images). */
function shoot(svgName, width, height, out) {
  const page = path.join(ASSETS, `.render-${svgName}.html`);
  fs.writeFileSync(
    page,
    `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "Plus Jakarta Sans"; src: url("file://${font}") format("woff2"); font-weight: 200 800; }
html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
img { display: block; width: ${width}px; height: ${height}px; }
</style></head><body>${fs.readFileSync(path.join(ASSETS, svgName), 'utf8')
      .replace(/<svg /, `<svg style="display:block;width:${width}px;height:${height}px" `)
      .replace(/href="icon\.svg"/g, `href="file://${path.join(ASSETS, 'icon.svg')}"`)}</body></html>`,
  );
  try {
    execFileSync(browser, [
      '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--no-default-browser-check',
      '--allow-file-access-from-files', '--default-background-color=00000000', '--force-device-scale-factor=1',
      `--user-data-dir=${path.join(work, 'profile')}`, `--window-size=${width},${height}`,
      `--screenshot=${out}`, `file://${page}`,
    ], { stdio: 'ignore' });
  } finally {
    fs.unlinkSync(page);
  }
}

/** Pillow does the encoding: JPEG (flattened on the banner's own background), PNG, ICO. */
function convert(jobs) {
  const script = `
import json, sys
from PIL import Image
for job in json.loads(sys.argv[1]):
    image = Image.open(job["src"]).convert("RGBA")
    if job.get("size"):
        image = image.resize((job["size"], job["size"]), Image.LANCZOS)
    if job["format"] == "JPEG":
        flat = Image.new("RGB", image.size, tuple(job.get("matte", (6, 10, 31))))
        flat.paste(image, mask=image.split()[3])
        flat.save(job["out"], "JPEG", quality=92, optimize=True, progressive=True)
    elif job["format"] == "ICO":
        image.save(job["out"], "ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    else:
        image.save(job["out"], "PNG", optimize=True)
    print("   ✓", job["out"].split("/assets/")[-1].split("/public/")[-1])
`;
  execFileSync('python3', ['-c', script, JSON.stringify(jobs)], { stdio: 'inherit' });
}

console.log(`🎨 Rendering with ${browser} …`);
const banner = path.join(work, 'banner.png');
const icon = path.join(work, 'icon.png');
const favicon = path.join(work, 'favicon.png');
shoot('banner.svg', 1280, 400, banner);
shoot('icon.svg', 1024, 1024, icon);
shoot('favicon.svg', 256, 256, favicon);

const jobs = [
  { src: banner, out: path.join(ASSETS, 'banner.jpg'), format: 'JPEG', matte: [7, 11, 36] },
  { src: icon, out: path.join(ASSETS, 'icon.jpg'), format: 'JPEG', size: 512, matte: [255, 255, 255] },
  { src: icon, out: path.join(ASSETS, 'icon.png'), format: 'PNG', size: 512 },
  { src: favicon, out: path.join(ASSETS, 'favicon.ico'), format: 'ICO' },
];
if (install && fs.existsSync(PUBLIC)) {
  jobs.push(
    { src: icon, out: path.join(PUBLIC, 'icon-192.png'), format: 'PNG', size: 192 },
    { src: icon, out: path.join(PUBLIC, 'icon-512.png'), format: 'PNG', size: 512 },
    { src: icon, out: path.join(PUBLIC, 'apple-touch-icon.png'), format: 'PNG', size: 180 },
    { src: favicon, out: path.join(PUBLIC, 'favicon.ico'), format: 'ICO' },
  );
}
convert(jobs);
if (install && fs.existsSync(PUBLIC)) {
  fs.copyFileSync(path.join(ASSETS, 'favicon.svg'), path.join(PUBLIC, 'favicon.svg'));
  console.log('   ✓ favicon.svg');
}
fs.rmSync(work, { recursive: true, force: true });
console.log('\n✅ Assets rendered.');
console.log('   Sources : assets/{icon,favicon,banner}.svg');
console.log('   Renders : assets/{banner,icon}.jpg, assets/icon.png, assets/favicon.ico (+ portalab/frontend/public)');
