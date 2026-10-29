/** standard-version updater for `portalab/frontend/package-lock.json`: the lock's own version and its root
 * package's (both, as npm writes them). */
module.exports.readVersion = (contents) => JSON.parse(contents).version;

module.exports.writeVersion = (contents, version) => {
  const lock = JSON.parse(contents);
  lock.version = version;
  if (lock.packages && lock.packages['']) lock.packages[''].version = version;
  return `${JSON.stringify(lock, null, 2)}\n`;
};
