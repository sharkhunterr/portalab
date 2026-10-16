// Portalab — ambient/windowrain: the « windowrain » ambience (spec 028, B2)
vec4 lights(vec2 p, float t, float aspect) {
  vec4 o = vec4(0.0);
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    vec2 c = vec2(hash(vec2(fi, 1.0)) * aspect, 0.03 + 0.75 * hash(vec2(fi, 2.0)));
    c.x += sin(t * 0.05 + fi) * 0.01;
    float rad = 0.05 + 0.09 * hash(vec2(fi, 3.0));
    float d = length(p - c);
    float pick = hash(vec2(fi, 4.0));
    vec3 col = pick < 0.5 ? vec3(1.0, 0.72, 0.35) : pick < 0.7 ? vec3(1.0, 0.45, 0.3) : pick < 0.85 ? vec3(0.45, 0.7, 1.0) : vec3(1.0, 0.9, 0.7);
    float on = 0.7 + 0.3 * sin(t * (0.3 + pick) + fi);
    o = over(o, col, smoothstep(rad, rad * 0.55, d) * 0.26 * on);
  }
  return o;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = lights(p, t, aspect);
  o = over(o, vec3(1.0, 0.7, 0.4), exp(-length((uv - vec2(0.0, 0.0)) * vec2(aspect, 1.0)) * 2.5) * 0.18);
  float mist = fbm(p * 3.0 + vec2(0.0, t * 0.01));
  o = over(o, vec3(0.62, 0.66, 0.75), (0.03 + 0.1 * smoothstep(0.45, 0.0, uv.y)) * smoothstep(0.3, 0.8, mist));
  // sliding drops in two depths: each column of cells falls at its own pace, in jerks
  for (int l = 0; l < 2; l++) {
    float s = l == 0 ? 7.0 : 12.0;
    vec2 g = p * vec2(s, s * 0.45);
    float col = floor(g.x);
    float hc = hash(vec2(col, s));
    float jerk = t * (0.35 + 0.5 * hc) + 0.15 * sin(t * (2.0 + hc * 3.0) + col);
    g.y += jerk + hc * 7.0;
    vec2 id = floor(g);
    vec2 f = fract(g) - vec2(0.5, 0.3);
    float h = hash(id + s);
    float present = step(0.62, h);
    float dx = (h - 0.5) * 0.5 + sin(g.y * 3.0 + h * 9.0) * 0.06;
    vec2 dp = vec2((f.x - dx) / s, f.y / (s * 0.45));
    float r0 = (0.11 + 0.08 * hash(id + 3.0)) / s;
    vec2 n = dp / r0;
    float body = smoothstep(1.0, 0.85, length(n * vec2(1.0, 0.85))) * present;
    float trail = smoothstep(r0 * 0.35, 0.0, abs(dp.x)) * step(0.0, dp.y) * smoothstep(0.3 / s, 0.0, dp.y) * present;
    vec4 seen = lights(p - n * 0.06 * vec2(1.0, -1.0) * 3.0, t, aspect);
    o = over(o, vec3(0.8, 0.85, 0.95), body * 0.12 + trail * 0.05);
    o = over(o, seen.rgb / max(seen.a, 0.01), body * clamp(seen.a * 3.0, 0.0, 0.8));
    o = over(o, vec3(0.05, 0.06, 0.1), body * smoothstep(0.55, 1.0, length(n)) * 0.35 * step(n.y, 0.2));
    o = over(o, vec3(1.0), body * smoothstep(0.3, 0.1, length(n - vec2(-0.35, 0.4))) * 0.8);
  }
  // still droplets scattered on the pane, appearing and drying
  vec2 sg = p * 55.0;
  vec2 sid = floor(sg);
  float sh = hash(sid + 9.0);
  float alive = sin(t * (0.1 + sh * 0.2) + sh * 40.0);
  vec2 sp = fract(sg) - 0.5 - (vec2(hash(sid + 1.0), hash(sid + 2.0)) - 0.5) * 0.5;
  float droplet = smoothstep(0.18, 0.1, length(sp)) * step(0.88, sh) * smoothstep(0.0, 0.3, alive);
  o = over(o, vec3(0.85, 0.88, 0.95), droplet * 0.3);
  o = over(o, vec3(1.0), droplet * smoothstep(0.08, 0.02, length(sp - vec2(-0.04, 0.05))) * 0.6);
  gl_FragColor = o;
}