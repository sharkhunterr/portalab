// DVD — the booster stage: a wine damask, a rose window of stained glass glowing high in the dark, its light
  // falling in rays, embers rising (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.18, 0.025, 0.06, 1.0);
  vec2 dm = fract(c * vec2(9.0, 7.0) + vec2(0.0, 0.5) * step(0.5, fract(c.x * 4.5))) - 0.5;
  o = over(o, vec3(0.32, 0.06, 0.11), step(abs(dm.x) * 1.8 + abs(dm.y), 0.32));
  o.rgb *= 0.55 + 0.45 * smoothstep(1.0, 0.0, length(c - vec2(0.0, 0.25)));
  vec2 w = c - vec2(0.0, 0.2);
  float r = length(w), a = atan(w.y, w.x) + t * 0.05;
  float ringI = r < 0.06 ? 0.0 : r < 0.14 ? 1.0 : r < 0.22 ? 2.0 : 3.0;
  float seg = floor(a / 6.2832 * (ringI * 8.0 + 1.0)) + ringI * 3.0;
  float m = mod(seg, 5.0);
  vec3 glass = m < 1.0 ? vec3(0.85, 0.1, 0.18) : m < 2.0 ? vec3(0.15, 0.3, 0.85) : m < 3.0 ? vec3(0.1, 0.62, 0.35) : m < 4.0 ? vec3(1.0, 0.62, 0.12) : vec3(0.5, 0.2, 0.75);
  float lead = smoothstep(0.004, 0.0, abs(fract(a / 6.2832 * (ringI * 8.0 + 1.0)) - 0.0) * r * 6.0) + smoothstep(0.004, 0.0, abs(r - 0.06)) + smoothstep(0.004, 0.0, abs(r - 0.14)) + smoothstep(0.004, 0.0, abs(r - 0.22));
  float pulse = 0.85 + 0.15 * sin(t * 1.3 + seg);
  o = over(o, glass * pulse, step(r, 0.3));
  o = over(o, vec3(0.88, 0.68, 0.28), clamp(lead, 0.0, 1.0) * step(r, 0.3) + smoothstep(0.012, 0.0, abs(r - 0.305)));
  float ray = pow(0.5 + 0.5 * sin(atan(c.x, 0.5 - c.y) * 30.0 + t * 0.3), 6.0) * smoothstep(0.3, -0.5, c.y) * step(c.y, 0.0);
  o = over(o, vec3(1.0, 0.95, 0.82), ray * 0.12 * smoothstep(0.5, 0.0, abs(c.x)));
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    vec2 ep = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp + 0.03 * sin(t + fk), fract(hash(vec2(fk, 2.0)) + t * 0.06 * (0.5 + hash(vec2(fk, 3.0)))) - 0.5);
    o = over(o, vec3(1.0, 0.62, 0.12), exp(-length(c - ep) * 400.0) * 1.2);
  }
  vec2 fc = abs(c) - vec2(asp * 0.5 - 0.1, 0.4);
  o = over(o, vec3(0.88, 0.68, 0.28), smoothstep(0.004, 0.0, abs(length(fc) - 0.05)) * step(0.0, fc.x + 0.05) * step(0.0, fc.y + 0.05));
