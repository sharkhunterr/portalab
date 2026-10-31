// Streaming — the booster stage: holo-tech, a neon grid floor running towards a magenta haze on the horizon,
  // a violet sun of scanlines, particles rising, a scan beam sweeping, a glitch now and then (a stage:
  // gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.015, 0.015, 0.06, 1.0);
  float hz = -0.06;
  vec2 su = c - vec2(0.0, hz);
  float sun = step(length(su), 0.32) * step(0.0, su.y) * step(0.35, fract(su.y * 30.0 - t * 0.5) + (0.3 - su.y) * 1.5);
  o = over(o, mix(vec3(1.0, 0.15, 0.6), vec3(0.45, 0.22, 1.0), su.y / 0.32), sun);
  o = over(o, vec3(1.0, 0.15, 0.6), exp(-abs(c.y - hz) * 18.0) * 0.6);
  if (c.y < hz) {
    float z = 0.12 / (hz - c.y);
    vec2 fl = vec2(c.x * z, z + t * 1.2);
    vec2 ff = abs(fract(fl) - 0.5);
    float line = smoothstep(0.03 * z, 0.0, min(ff.x, ff.y) - 0.0);
    o = over(o, vec3(0.2, 0.95, 1.0), line * smoothstep(8.0, 1.0, z));
  }
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    vec2 pp = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp, fract(hash(vec2(fk, 2.0)) + t * 0.05 * (0.5 + hash(vec2(fk, 3.0)))) - 0.5);
    vec2 q = abs(c - pp);
    o = over(o, vec3(0.2, 0.95, 1.0), step(max(q.x, q.y), 0.003) * 0.9);
  }
  float sx = fract(t / 4.0) * (asp + 0.4) - asp * 0.5 - 0.2;
  o = over(o, vec3(0.2, 0.95, 1.0), exp(-abs(c.x - sx) * 60.0) * 0.25);
  float gl = step(0.92, hash(vec2(floor(t * 8.0), 1.0))) * step(abs(c.y - (hash(vec2(floor(t * 8.0), 2.0)) - 0.5)), 0.03);
  o = over(o, vec3(1.0, 0.15, 0.6), gl * 0.5);
