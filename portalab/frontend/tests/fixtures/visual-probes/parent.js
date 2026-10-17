// the page around it: its document, its location
export default (_root, api) => {
  let refused = false;
  try {
    void window.parent.document.body;
  } catch {
    refused = true;
  }
  try {
    void window.parent.location.href;
    refused = false;
  } catch {
    // still refused
  }
  api.navigate(`probe:${JSON.stringify({ probe: "parent", refused })}`);
};
