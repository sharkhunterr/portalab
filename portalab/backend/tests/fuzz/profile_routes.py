"""Issue 404 — every GET route of the API without a path parameter, timed (best of 3) with the SQL statements
it ran (tests/fuzz/serve.py's « X-Query-Count »): the slowest and the most talkative, to find slow pages and
queries repeated in a loop (N+1).

    uv run python -m tests.fuzz.profile_routes http://127.0.0.1:8099 TOKEN [openapi.json]
"""

import json
import statistics
import sys
import time
from pathlib import Path

import httpx


def main() -> None:
    base, token = sys.argv[1].rstrip("/"), sys.argv[2]
    spec = json.loads(Path(sys.argv[3] if len(sys.argv) > 3 else "openapi.json").read_text(encoding="utf-8"))
    paths = sorted(p for p, ops in spec["paths"].items() if "get" in ops and "{" not in p)
    rows = []
    with httpx.Client(base_url=base, cookies={"portalab_session": token}, timeout=60) as client:
        for path in paths:
            if path.endswith(("/stream", "/events/live", "/download")) or "stream" in path:
                continue
            times, queries, status = [], 0, 0
            for _ in range(3):
                started = time.perf_counter()
                response = client.get(path)
                times.append((time.perf_counter() - started) * 1000)
                status, queries = response.status_code, int(response.headers.get("x-query-count", 0))
            rows.append((min(times), statistics.median(times), queries, status, path))
    print(f"{len(rows)} routes")
    print("\n== slowest (best of 3, ms)")
    for best, median, queries, status, path in sorted(rows, reverse=True)[:25]:
        print(f"{best:8.0f} {median:8.0f} {queries:5} q  {status}  {path}")
    print("\n== most SQL statements")
    for best, _median, queries, status, path in sorted(rows, key=lambda r: -r[2])[:25]:
        print(f"{queries:5} q {best:8.0f} ms  {status}  {path}")


if __name__ == "__main__":
    main()
