/** standard-version updater for `portalab/backend/uv.lock`: the project's own entry (keeps `uv sync --locked`
 * happy after a bump). */
const versionRegex = /(\[\[package\]\]\nname = "portalab"\nversion = ")([^"]+)(")/;

module.exports.readVersion = (contents) => {
  const match = contents.match(versionRegex);
  if (!match) throw new Error('No portalab package in uv.lock');
  return match[2];
};

module.exports.writeVersion = (contents, version) => contents.replace(versionRegex, `$1${version}$3`);
