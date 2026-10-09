/**
 * 027 (#31): the « pulse » look of the services — a heartbeat trace, drawn in the summary line between
 * « all services are working » and « All », in the tone of their health (a beam running along it).
 */
const BEAT = "H{x} l3 -3 l3 3 h5 l2 -13 l4 27 l3 -18 l2 4 h8 q4 -7 8 0";
const TRACE = `M0 20 ${BEAT.replace("{x}", "22")} H122 ${BEAT.replace("{x}", "122").slice(5)} H200`;

export function HeartbeatTrace() {
  return (
    <svg className="skin-pulse__trace" viewBox="0 0 200 40" preserveAspectRatio="none" aria-hidden="true">
      <path d={TRACE} />
      <path className="skin-pulse__beam" d={TRACE} pathLength={100} />
    </svg>
  );
}
