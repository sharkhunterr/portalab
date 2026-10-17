// moving the page around it elsewhere
export default (_root, api) => {
  let refused = false;
  try {
    window.top.location.href = "/elsewhere";
  } catch {
    refused = true;
  }
  // reported either way: the spec also checks the page did not move
  api.navigate(`probe:${JSON.stringify({ probe: "navigation", refused })}`);
};
