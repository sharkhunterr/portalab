// submitting a form (the spec checks no request reached the server)
export default (root, api) => {
  const form = document.createElement("form");
  form.method = "post";
  form.action = "/submit";
  root.append(form);
  let refused = true;
  try {
    form.submit();
  } catch {
    refused = true;
  }
  api.navigate(`probe:${JSON.stringify({ probe: "form", refused })}`);
};
