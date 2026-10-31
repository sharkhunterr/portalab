// Super 8 — the booster stage: a psychedelic poster come alive, op-art rings rippling out of a radiating sun,
  // its rays turning, the colours melting at the top and the foot (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c), a = atan(c.y, c.x);
  float wob = r + 0.025 * sin(a * 7.0 + t * 0.8) + 0.015 * sin(a * 3.0 - t * 0.5);
  float band = floor(wob * 14.0 - t * 0.6);
  float m = mod(band, 4.0);
  vec3 ring = m < 1.0 ? vec3(1.0, 0.46, 0.08) : m < 2.0 ? vec3(0.22, 0.04, 0.36) : m < 3.0 ? vec3(1.0, 0.27, 0.6) : vec3(0.45, 0.12, 0.62);
  o = vec4(ring, 1.0);
  float rays = step(0.5, fract(a / 6.2832 * 16.0 + t * 0.03));
  o = over(o, mix(vec3(1.0, 0.86, 0.2), vec3(1.0, 0.95, 0.85), rays), step(wob, 0.22));
  o = over(o, vec3(1.0, 0.86, 0.2), step(r, 0.08 + 0.005 * sin(t * 3.0)));
  float melt = 0.42 - 0.03 * sin(c.x * 20.0 + t) - 0.05 * step(0.8, fract(c.x * 5.0)) * (0.6 + 0.4 * sin(t + c.x * 10.0));
  o = over(o, vec3(1.0, 0.27, 0.6), step(melt, c.y));
  o = over(o, vec3(0.32, 0.84, 0.45), step(c.y, -melt));
