/** standard-version updater for `portalab/backend/openapi.json`: the API's `info.version` (the snapshot the
 * backend's contract test compares with the running app, whose version is `portalab.__version__`). */
const versionRegex = /("info": \{\s*"title": "[^"]*",\s*"version": ")([^"]+)(")/;

module.exports.readVersion = (contents) => {
  const match = contents.match(versionRegex);
  if (!match) throw new Error('No info.version in openapi.json');
  return match[2];
};

module.exports.writeVersion = (contents, version) => contents.replace(versionRegex, `$1${version}$3`);
