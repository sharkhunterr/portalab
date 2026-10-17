// the portal's cookies: an opaque origin has none, and may not set any
export default (_root, api) => {
  let refused = false;
  try {
    document.cookie = "probe=1";
    refused = !document.cookie.includes("probe=1");
  } catch {
    refused = true;
  }
  api.navigate(`probe:${JSON.stringify({ probe: "cookies", refused })}`);
};
