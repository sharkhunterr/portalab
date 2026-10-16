// Portalab — ambient/plasma: the « plasma » ambience (spec 028, B2)
// distance to a jagged arc from a to b (coarse turns, fine crackle), and how far along it the point is
vec2 arc(vec2 p, vec2 a, vec2 b, float seed, float t) {
  vec2 ab = b - a;
  float len = length(ab);
  vec2 dir = ab / len;
  vec2 nrm = vec2(-dir.y, dir.x);
  float along = clamp(dot(p - a, dir) / len, 0.0, 1.0);
  float bend = (fbm(vec2(along * 3.0, seed + t * 0.6)) - 0.5) * 0.35 * len
    + (noise(vec2(along * 26.0, seed * 3.0 + t * 9.0)) - 0.5) * 0.035;
  float taper = sin(along * 3.14159);
  vec2 onArc = a + dir * along * len + nrm * bend * taper;
  return vec2(length(p - onArc), along);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  // the charged clouds
  vec2 q = p * 1.4;
  vec2 w = vec2(fbm(q + t * 0.035), fbm(q + vec2(3.3, -t * 0.03)));
  vec2 w2 = vec2(fbm(q * 1.6 + w * 1.5 + t * 0.02), fbm(q * 1.6 + w * 1.5 + vec2(7.1, 2.4)));
  float n = fbm(q + w2 * 1.8);
  vec3 gas = mix(vec3(0.22, 0.04, 0.42), vec3(0.08, 0.55, 0.85), smoothstep(0.3, 0.8, w2.y));
  gas = mix(gas, vec3(0.85, 0.4, 1.0), smoothstep(0.62, 0.92, n));
  o = over(o, gas, smoothstep(0.32, 0.85, n) * 0.6);
  // arcs: four at a time, each born at a random moment between two drifting anchors
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = 1.4 + hash(vec2(fi, 3.0)) * 1.6;
    float slot = floor((t + fi * 0.83) / life);
    float age = fract((t + fi * 0.83) / life);
    float alive = step(0.35, hash(vec2(slot, fi)));
    float env = alive * smoothstep(0.0, 0.06, age) * smoothstep(0.55, 0.15, age); // a strike, then a fade
    vec2 a = vec2(hash(vec2(slot, fi + 1.0)) * aspect, 0.2 + hash(vec2(slot, fi + 2.0)) * 0.7);
    vec2 b = a + (vec2(hash(vec2(slot, fi + 4.0)), hash(vec2(slot, fi + 5.0))) - 0.5) * vec2(0.9, 0.6);
    vec2 d = arc(p, a, b, slot * 7.0 + fi, t);
    float core = smoothstep(0.004, 0.0, d.x);
    float halo = exp(-d.x * 70.0) * 0.6;
    // a fork leaving the arc halfway
    vec2 mid = mix(a, b, 0.45);
    vec2 tip = mid + (vec2(hash(vec2(slot, fi + 6.0)), hash(vec2(slot, fi + 7.0))) - 0.5) * 0.35;
    vec2 f = arc(p, mid, tip, slot * 11.0 + fi, t);
    core += smoothstep(0.003, 0.0, f.x) * 0.8;
    halo += exp(-f.x * 90.0) * 0.4;
    float flick = 0.75 + 0.25 * noise(vec2(t * 25.0, fi));
    o = over(o, vec3(0.75, 0.6, 1.0), halo * env * flick);
    o = over(o, vec3(0.95, 0.97, 1.0), core * env * flick);
  }
  gl_FragColor = o;
}