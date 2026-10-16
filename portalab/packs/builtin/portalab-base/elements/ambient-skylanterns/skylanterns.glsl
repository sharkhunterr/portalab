// Portalab — ambient/skylanterns: the « skylanterns » ambience (spec 028, B2)
vec4 lantern(vec2 p, vec2 c, float size, float flick, vec4 o, float alpha) {
  vec2 q = (p - c) / size;
  float half_ = 0.55 + 0.16 * q.y;
  float body = smoothstep(0.08, 0.0, abs(q.x) - half_) * smoothstep(0.08, 0.0, abs(q.y) - 1.0);
  vec3 col = mix(vec3(1.0, 0.86, 0.5), vec3(0.95, 0.42, 0.15), (q.y + 1.0) * 0.5) * flick;
  float glow = exp(-length(q * vec2(1.0, 0.8)) * 1.1) * 0.35;
  float flame = smoothstep(0.35, 0.0, length((q - vec2(0.0, -0.75)) * vec2(1.4, 0.9)));
  o = over(o, vec3(1.0, 0.6, 0.25), glow * alpha * flick);
  o = over(o, col, body * alpha * 0.95);
  o = over(o, vec3(0.6, 0.25, 0.1), body * smoothstep(0.75, 1.0, q.y) * alpha * 0.6);
  o = over(o, vec3(1.0, 0.97, 0.8), flame * alpha);
  return o;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float horizon = 0.22;
  vec3 sky = mix(vec3(1.0, 0.55, 0.3), vec3(0.4, 0.22, 0.5), smoothstep(horizon, 0.6, uv.y));
  sky = mix(sky, vec3(0.07, 0.07, 0.2), smoothstep(0.55, 1.0, uv.y));
  o = over(o, sky, step(horizon, uv.y) * 0.4);
  vec2 sg = p * 110.0;
  float st = step(0.995, hash(floor(sg))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + hash(floor(sg)) * 50.0));
  o = over(o, vec3(1.0, 0.95, 0.85), st * smoothstep(0.6, 0.9, uv.y));
  float shore = horizon + 0.02 + 0.025 * noise(vec2(p.x * 3.0, 1.0)) + 0.015 * sin(p.x * 1.7);
  o = over(o, vec3(0.12, 0.08, 0.17), step(horizon, uv.y) * step(uv.y, shore) * 0.95);
  float depth = (horizon - uv.y) / horizon;
  vec3 water = mix(vec3(0.55, 0.3, 0.35), vec3(0.06, 0.06, 0.16), depth);
  float wave = noise(vec2(p.x * 4.0, uv.y * 140.0 / (0.3 + depth) + t * 0.6));
  o = over(o, water + vec3(0.2, 0.12, 0.08) * smoothstep(0.6, 0.9, wave) * (1.0 - depth), step(uv.y, horizon) * 0.85);
  for (int i = 0; i < 22; i++) {
    float fi = float(i);
    float near = hash(vec2(fi, 1.0));
    near = near * near;
    float size = 0.006 + 0.022 * near;
    float speed = 0.012 + 0.03 * near;
    float ph = fract(hash(vec2(fi, 2.0)) + t * speed);
    vec2 c = vec2(aspect * hash(vec2(fi, 3.0)) + sin(t * 0.3 + fi) * 0.02 + ph * 0.12 * (hash(vec2(fi, 4.0)) - 0.3), horizon + 0.03 + ph * 0.95);
    float flick = 0.85 + 0.15 * noise(vec2(t * 4.0, fi));
    float alpha = smoothstep(0.0, 0.08, ph) * smoothstep(1.0, 0.75, ph) * (0.55 + 0.45 * near);
    o = lantern(p, c, size, flick, o, alpha * step(horizon, uv.y));
    // its reflection in the lake, broken by the ripples
    vec2 rp = vec2(p.x + sin(uv.y * 260.0 + t * 2.0) * 0.004, 2.0 * horizon - p.y);
    o = lantern(rp, c, size, flick, o, alpha * 0.35 * step(uv.y, horizon) * smoothstep(0.0, 0.3, horizon - (c.y - horizon)));
  }
  gl_FragColor = o;
}