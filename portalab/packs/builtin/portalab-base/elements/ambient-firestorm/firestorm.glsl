// Portalab — ambient/firestorm: the « firestorm » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float gust = 0.55 + 0.3 * sin(t * 0.4) + 0.15 * sin(t * 1.3) + 0.25 * smoothstep(0.7, 1.0, noise(vec2(t * 0.5, 2.0)));
  vec4 o = vec4(0.0);
  // smoke rolling to the side, thick and slow, lit from below
  vec2 r = vec2(p.x * 1.4 - t * 0.2 * gust, uv.y * 2.4);
  vec2 wr = vec2(fbm(r * 1.2 + t * 0.06), fbm(r * 1.2 + vec2(3.1, -t * 0.04)));
  float sm = fbm(r + wr * 2.0);
  float smoke = smoothstep(0.4, 0.85, sm) * smoothstep(0.25, 0.6, uv.y);
  vec3 grey = mix(vec3(0.12, 0.1, 0.1), vec3(0.36, 0.31, 0.3), sm);
  grey += vec3(0.6, 0.2, 0.04) * smoothstep(0.75, 0.3, uv.y) * smoothstep(0.4, 0.85, sm) * gust;
  o = over(o, grey, smoke * 0.72);
  // the burning treeline: trunks and crowns in silhouette against the fire
  float trees = 0.0;
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float x0 = (fi + hash(vec2(fi, 1.0)) * 0.6) / 14.0 * u_res.x / u_res.y;
    float h = 0.16 + 0.1 * hash(vec2(fi, 2.0));
    float lean = (uv.y - 0.08) * 0.12 * gust;
    float y = (uv.y - 0.08) / h;
    // a fir: tiers of jagged branches narrowing to the top
    float tier = fract(y * 5.0);
    float w = (0.05 + 0.02 * hash(vec2(fi, 3.0))) * (1.0 - y) * (0.65 + 0.35 * (1.0 - tier));
    w *= 0.75 + 0.5 * noise(vec2(uv.y * 90.0, fi * 7.0));
    trees += smoothstep(0.003, 0.0, abs(p.x - x0 - lean) - max(w, 0.0)) * step(0.08, uv.y) * step(uv.y, 0.08 + h);
    trees += step(abs(p.x - x0), 0.005) * step(uv.y, 0.1);
  }
  // flames behind and among the trees, leaning with the wind
  vec2 q = vec2(p.x * 2.4 - uv.y * 1.6 * gust - t * 0.5, p.y * 1.7 - t * 1.3);
  vec2 warp = vec2(fbm(q * 1.3 + vec2(0.0, -t * 0.6)), fbm(q * 1.6 + vec2(5.2, -t * 0.9)));
  float n = fbm(q + warp * 1.8) + (1.0 - abs(noise(vec2(p.x * 10.0, p.y * 3.0 - t * 2.6)) * 2.0 - 1.0)) * 0.15;
  float f = clamp((n * 1.5 + (0.24 - uv.y * 1.8) - 0.4 + gust * 0.08) * 2.6, 0.0, 1.0);
  vec3 fire = mix(vec3(0.45, 0.03, 0.0), vec3(1.0, 0.4, 0.04), smoothstep(0.05, 0.5, f));
  fire = mix(fire, vec3(1.0, 0.72, 0.3), smoothstep(0.65, 1.0, f));
  fire *= 0.7 + 0.45 * fbm(q * 3.0 + t);
  o = over(o, fire, smoothstep(0.02, 0.4, f) * 0.85);
  o = over(o, vec3(0.03, 0.01, 0.0), clamp(trees, 0.0, 1.0) * 0.92);
  o = over(o, vec3(0.8, 0.25, 0.02), smoothstep(0.5, 0.0, uv.y) * 0.15 * gust);
  gl_FragColor = o;
}