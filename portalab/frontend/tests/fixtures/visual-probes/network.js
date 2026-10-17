// any request: the portal's own API, an image, a worker (refused when it never runs)
export default async (_root, api) => {
  const results = {};
  try {
    await fetch("/api/v1/visuals/active");
    results.fetch = false;
  } catch {
    results.fetch = true;
  }
  results.image = await new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(false);
    image.onerror = () => resolve(true);
    image.src = "/probe.png";
  });
  results.worker = await new Promise((resolve) => {
    try {
      const worker = new Worker(
        URL.createObjectURL(new Blob(["postMessage(1)"], { type: "text/javascript" })),
      );
      worker.onmessage = () => resolve(false);
      worker.onerror = () => resolve(true);
      setTimeout(() => resolve(true), 1500);
    } catch {
      resolve(true);
    }
  });
  const refused = Object.values(results).every(Boolean);
  api.navigate(`probe:${JSON.stringify({ probe: "network", refused, results })}`);
};
