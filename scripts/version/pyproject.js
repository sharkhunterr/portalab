/** standard-version updater for `portalab/backend/pyproject.toml`: the `[project]` version line only. */
const versionRegex = /^version\s*=\s*["']([^"']+)["']/m;

module.exports.readVersion = (contents) => {
  const match = contents.match(versionRegex);
  if (!match) throw new Error('No top-level `version = "..."` in pyproject.toml');
  return match[1];
};

module.exports.writeVersion = (contents, version) => contents.replace(versionRegex, `version = "${version}"`);
