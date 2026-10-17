# Isolation probes (028, T094 — test only)

Each module is run in the sandbox a pack's script runs in, attempts **one** capability a pack must never
have, and reports through the sandbox's only channel (`api.navigate("probe:<json>")`) whether it was
refused. They read and send nothing: `isolation.spec.ts` expects every one to report `refused`.
