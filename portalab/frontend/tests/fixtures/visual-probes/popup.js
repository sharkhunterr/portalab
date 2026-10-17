// opening a window
export default (_root, api) => {
  let opened = null;
  try {
    opened = window.open("/popup", "_blank");
  } catch {
    opened = null;
  }
  api.navigate(`probe:${JSON.stringify({ probe: "popup", refused: !opened })}`);
};
