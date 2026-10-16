// Portalab — ambient/autumnlane: the « autumnlane » ambience (spec 028, B2)
vec3 leafColor(float h) {
  return h < 0.25 ? vec3(0.85, 0.25, 0.08) : h < 0.5 ? vec3(0.95, 0.55, 0.1) : h < 0.75 ? vec3(0.95, 0.75, 0.2) : vec3(0.6, 0.18, 0.08);
}
float maple(vec2 q, out float vein) {
  float r = length(q);
  float a = atan(q.x, q.y);
  float R = 0.55 + 0.25 * cos(5.0 * a) + 0.05 * abs(sin(a * 20.0));
  float leaf = smoothstep(0.03, 0.0, r - R * 0.9);
  vein = leaf * smoothstep(0.05, 0.0, abs(fract(a * 5.0 / 6.2831 + 0.5) - 0.5) * r * 2.0) * step(0.08, r);
  float stem = smoothstep(0.04, 0.0, abs(q.x)) * step(q.y, -0.2) * step(-0.85, q.y);
  return clamp(leaf + stem, 0.0, 1.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.65, 0.3), 0.04 + 0.12 * smoothstep(1.2, 0.0, length(uv - vec2(0.0, 1.0))));
  // the branch at the top-right corner, its leaves stirring
  vec2 bq = p - vec2(aspect, 1.0);
  float branch = smoothstep(0.003, 0.0, abs(bq.y + 0.06 + bq.x * 0.25 + 0.04 * sin(bq.x * 8.0)) - 0.003 * (1.0 - bq.x * 4.0)) * step(-0.55, bq.x);
  float crown = fbm(p * 9.0 + vec2(sin(t * 0.6) * 0.15, 0.0));
  float canopy = smoothstep(0.3, 0.0, length(bq * vec2(0.8, 1.6)) - 0.12 - crown * 0.18);
  float clump = smoothstep(0.5, 0.56, crown) * canopy;
  o = over(o, vec3(0.2, 0.1, 0.05), branch);
  vec3 crownc = mix(vec3(0.8, 0.22, 0.07), vec3(0.98, 0.7, 0.18), smoothstep(0.3, 0.7, noise(p * 14.0)));
  crownc *= 0.7 + 0.45 * smoothstep(0.5, 0.75, crown);
  o = over(o, crownc, clump * 0.95);
  // falling leaves
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float life = 8.0 + 5.0 * hash(vec2(fi, 1.0));
    float tt = t + hash(vec2(fi, 2.0)) * life;
    float slot = floor(tt / life);
    float ph = fract(tt / life);
    float size = 0.022 + 0.022 * hash(vec2(slot, fi + 3.0));
    float swing = sin(ph * 12.0 + fi);
    vec2 c = vec2(aspect * (0.1 + 0.95 * hash(vec2(slot, fi + 4.0))) - ph * 0.25 + swing * 0.06, 1.08 - ph * 1.2 + abs(swing) * 0.015);
    float rot = swing * 0.9 + fi;
    vec2 q = (p - c) / size;
    q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * q;
    q.x /= max(0.4, abs(cos(t * (0.6 + 0.6 * hash(vec2(fi, 5.0))) + fi)));
    float vein;
    float m = maple(q, vein);
    vec3 col = leafColor(hash(vec2(slot, fi + 6.0)));
    col *= 0.85 + 0.25 * smoothstep(-0.6, 0.6, q.x + q.y);
    o = over(o, col, m * 0.95);
    o = over(o, col * 0.55, vein * 0.6);
  }
  // the bed of fallen leaves along the bottom
  float top = 0.05 + 0.02 * noise(vec2(p.x * 6.0, 1.0)) + 0.01 * sin(p.x * 3.0);
  float bed = smoothstep(0.005, 0.0, p.y - top);
  o = over(o, vec3(0.22, 0.1, 0.05), bed * 0.95);
  for (int l = 0; l < 3; l++) {
    float fl = float(l);
    vec2 lg = p * 42.0 + vec2(fl * 0.37, fl * 0.61);
    vec2 lid = floor(lg);
    float a = hash(lid + fl) * 6.2831;
    vec2 lq = mat2(cos(a), -sin(a), sin(a), cos(a)) * (fract(lg) - 0.5 - (vec2(hash(lid + 2.0), hash(lid + 3.0)) - 0.5) * 0.3) / 0.62;
    float lv;
    float lm = maple(lq, lv);
    vec3 lc = leafColor(hash(lid + 5.0 + fl)) * (0.6 + 0.3 * fl / 2.0 + 0.2 * hash(lid + 6.0));
    o = over(o, lc, lm * bed);
    o = over(o, lc * 0.6, lv * bed * 0.5);
  }
  gl_FragColor = o;
}