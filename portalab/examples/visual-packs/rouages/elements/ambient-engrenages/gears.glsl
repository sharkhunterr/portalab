// Engine room — an ambience behind the whole portal (u_res, u_time, hash, noise, fbm, over): great brass
// gears turning at the edges, meshing; steam rising; a boiler's warm glow below. Premultiplied, see-through.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.9, 0.45, 0.15), smoothstep(0.35, 0.0, uv.y) * 0.18);
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 centre = vec2(fk < 1.5 ? (fk < 0.5 ? 0.05 : 0.22) : (fk < 2.5 ? aspect - 0.08 : aspect - 0.26), fk < 0.5 ? 0.12 : (fk < 1.5 ? 0.02 : (fk < 2.5 ? 0.9 : 1.0)));
    float rad = fk < 0.5 || fk > 1.5 && fk < 2.5 ? 0.17 : 0.11;
    float dir = mod(fk, 2.0) < 0.5 ? 1.0 : -1.0;
    vec2 q = c - centre;
    float a = atan(q.y, q.x) + dir * t * (0.25 / rad) * 0.1;
    float r = length(q);
    float teeth = rad + 0.018 * step(0.0, sin(a * (rad * 90.0)));
    float body = smoothstep(0.003, 0.0, r - teeth) - smoothstep(0.003, 0.0, r - rad * 0.32);
    float spokes = smoothstep(0.012, 0.0, abs(sin(a * 3.0)) * r) * step(r, rad * 0.8);
    float hole = smoothstep(0.003, 0.0, abs(r - rad * 0.8) - 0.004);
    float gear = clamp(body - smoothstep(0.003, 0.0, r - rad * 0.78) + spokes + hole, 0.0, 1.0);
    vec3 brass = mix(vec3(0.55, 0.36, 0.12), vec3(0.85, 0.62, 0.28), 0.5 + 0.5 * sin(a * 2.0 + 1.0));
    o = over(o, brass * 0.8, gear * 0.55);
  }
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float life = fract(t * 0.05 + fk * 0.21);
    vec2 sp = vec2((0.1 + fk * 0.2) * aspect, life * 1.2 - 0.1);
    float puff = fbm((c - sp) * 6.0 + t * 0.1) * smoothstep(0.18, 0.0, length((c - sp) * vec2(1.0, 0.7)));
    o = over(o, vec3(0.85, 0.82, 0.78), puff * 0.25 * smoothstep(1.0, 0.6, life));
  }
  gl_FragColor = o;
}
