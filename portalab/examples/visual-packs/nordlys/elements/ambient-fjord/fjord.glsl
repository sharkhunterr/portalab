// Fjord — an ambience behind the whole portal. Portalab puts its common helpers first (u_res, u_time, hash,
// noise, fbm, over); the shader writes premultiplied colour: what is not lit stays see-through.
float ridge(float x, float seed) {
  return 0.12 * fbm(vec2(x * 2.2 + seed, seed)) + 0.06 * sin(x * 3.0 + seed);
}
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  float horizon = 0.36;
  // the sky and its northern lights (mirrored below the horizon)
  float sky = uv.y > horizon ? uv.y : 2.0 * horizon - uv.y;
  float mirror = uv.y > horizon ? 1.0 : 0.45;
  vec3 col = mix(vec3(0.01, 0.03, 0.07), vec3(0.02, 0.07, 0.12), sky);
  o = over(o, col, 0.85);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float x = c.x * (0.9 + fk * 0.4) + fk * 3.0;
    float edge = 0.62 + fk * 0.08 + 0.08 * sin(x * 1.7 + t * 0.15) + 0.06 * (fbm(vec2(x, t * 0.05 + fk)) - 0.5);
    float below = edge - sky;
    float rays = 0.5 + 0.5 * fbm(vec2(x * 8.0, t * 0.2 + fk * 4.0));
    float curtain = smoothstep(-0.02, 0.02, below) * exp(-max(below, 0.0) * 6.0) * rays;
    vec3 aurora = mix(vec3(0.2, 0.95, 0.55), vec3(0.6, 0.35, 1.0), smoothstep(0.0, 0.2, -below + 0.15 + fk * 0.1));
    float ripple = uv.y > horizon ? 1.0 : 0.7 + 0.3 * sin(uv.y * 160.0 + t * 1.2 + fbm(c * 20.0) * 4.0);
    o = over(o, aurora, curtain * (0.45 - fk * 0.15) * mirror * ripple);
  }
  // stars above, mountains in silhouette, the water's dark line
  vec2 sg = c * 90.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(0.9, 0.95, 1.0), step(0.992, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * step(horizon + 0.15, uv.y) * (0.5 + 0.5 * sin(t * 2.0 + sh * 40.0)));
  float far = horizon + 0.1 + ridge(c.x, 1.0);
  float near = horizon + 0.04 + ridge(c.x * 1.4, 7.0) * 1.3;
  o = over(o, vec3(0.03, 0.05, 0.09), step(uv.y, far) * step(horizon, uv.y));
  o = over(o, vec3(0.01, 0.02, 0.04), step(uv.y, near) * step(horizon, uv.y));
  float far2 = horizon - (far - horizon) * 0.8;
  o = over(o, vec3(0.02, 0.04, 0.07), step(far2, uv.y) * step(uv.y, horizon) * 0.8);
  // snow falling softly
  for (int i = 0; i < 30; i++) {
    float fi = float(i);
    vec2 pos = vec2(hash(vec2(fi, 3.0)) * aspect + sin(t * 0.3 + fi) * 0.02, 1.0 - fract(hash(vec2(fi, 4.0)) + t * (0.02 + 0.02 * hash(vec2(fi, 5.0)))));
    o = over(o, vec3(0.9, 0.95, 1.0), smoothstep(0.004, 0.0, length(c - pos)) * 0.7);
  }
  gl_FragColor = o;
}
