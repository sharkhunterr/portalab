/** standard-version updater for `portalab/backend/src/portalab/__init__.py`: `__version__`. */
const versionRegex = /__version__\s*=\s*["']([^"']+)["']/;

module.exports.readVersion = (contents) => {
  const match = contents.match(versionRegex);
  if (!match) throw new Error('No __version__ in __init__.py');
  return match[1];
};

module.exports.writeVersion = (contents, version) => contents.replace(versionRegex, `__version__ = "${version}"`);
