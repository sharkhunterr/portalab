// the browser's storage (local, session, indexed)
export default (_root, api) => {
  const tries = [
    () => window.localStorage.setItem("probe", "1"),
    () => window.sessionStorage.setItem("probe", "1"),
    () => window.indexedDB.open("probe"),
  ];
  const refused = tries.every((attempt) => {
    try {
      attempt();
      return false;
    } catch {
      return true;
    }
  });
  api.navigate(`probe:${JSON.stringify({ probe: "storage", refused })}`);
};
