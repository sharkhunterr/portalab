/**
 * The name of a kind of product: Portalab's own from the ``marketplace`` catalog; a plugin's
 * (``plugin:<plugin>.<type>``, spec 030) from that plugin's catalog (``plugin.<plugin>:type.<type>``).
 */
export function productTypeLabel(
  t: (key: string, values?: Record<string, string | number>) => string,
  type: string,
): string {
  const plugin = /^plugin:([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)$/.exec(type);
  if (plugin) {
    const key = `plugin.${plugin[1]}:type.${plugin[2]}`;
    const text = t(key);
    return text === key || key.endsWith(text) ? (plugin[2] ?? type).replace(/_/g, " ") : text;
  }
  return t(`marketplace:type.${type}`);
}
