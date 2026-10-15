  // Bioluminescent rise — a level-up over the whole stage: the deep's dark, jellyfish rising and pulsing,
  // a ring of bubbles bursting round the new level. Writes its colour into o (u_age: seconds since it began).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.8, 5.6, tl);
  vec3 deep = mix(vec3(0.0, 0.015, 0.04), vec3(0.0, 0.06, 0.1), smoothstep(-0.5, 0.6, c.y));
  o = over(o, deep, 0.85 * fade);
  // light dust drifting
  vec2 dg = c * vec2(26.0, 26.0) + vec2(0.0, tl * 0.4);
  float dh = hash(floor(dg));
  o = over(o, vec3(0.5, 0.9, 1.0), step(0.97, dh) * smoothstep(0.35, 0.0, length(fract(dg) - 0.5)) * 0.5 * fade);
  // jellyfish: a glowing bell, its rim brighter, tentacles swaying below; rising slowly, pulsing
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    vec2 at = vec2((hash(vec2(fk, 3.0)) - 0.5) * aspect * 0.9, -0.75 + mod(tl * (0.08 + 0.03 * fk) + hash(vec2(fk, 4.0)) * 1.5, 1.6));
    float pulse = 0.85 + 0.15 * sin(tl * 3.0 + fk * 1.7);
    float size = (0.05 + 0.03 * hash(vec2(fk, 5.0))) * pulse;
    vec2 q = (c - at) / size;
    float bell = smoothstep(1.0, 0.85, length(q * vec2(1.0, 1.35))) * step(-0.2, q.y);
    float rim = exp(-abs(length(q * vec2(1.0, 1.35)) - 0.95) * 12.0) * step(-0.25, q.y);
    float tentacles = 0.0;
    for (int j = 0; j < 4; j++) {
      float fj = float(j);
      float x0 = -0.6 + fj * 0.4;
      float sway = 0.18 * sin(q.y * 2.5 + tl * 2.0 + fj + fk);
      tentacles += smoothstep(0.08, 0.0, abs(q.x - x0 - sway)) * step(q.y, -0.1) * smoothstep(-3.2, -0.2, q.y);
    }
    vec3 glow = mix(vec3(0.2, 0.95, 0.85), vec3(0.65, 0.45, 1.0), hash(vec2(fk, 6.0)));
    o = over(o, glow, (bell * 0.35 + rim * 0.8 + tentacles * 0.4) * fade);
    o = over(o, glow, exp(-length(c - at) / size * 0.9) * 0.18 * fade);
  }
  // the ring of bubbles your level appears in
  float burst = smoothstep(2.0, 2.9, tl);
  float r = length(c);
  for (int i = 0; i < 36; i++) {
    float fi = float(i);
    float a = fi / 36.0 * 6.2832 + 0.3 * sin(tl + fi);
    float rad = 0.12 + 0.2 * burst + 0.02 * sin(tl * 4.0 + fi);
    vec2 bp = vec2(cos(a), sin(a)) * rad + vec2(0.0, 0.06 * burst * fract(fi * 0.37));
    float s = 0.006 + 0.008 * hash(vec2(fi, 9.0));
    float ring = smoothstep(s * 1.6, s * 0.9, length(c - bp)) - smoothstep(s * 0.9, s * 0.4, length(c - bp)) * 0.7;
    o = over(o, vec3(0.75, 1.0, 1.0), clamp(ring, 0.0, 1.0) * burst * fade);
  }
  o = over(o, vec3(0.3, 1.0, 0.9), exp(-r * 7.0) * burst * 0.35 * fade);
  o = over(o, vec3(0.9, 1.0, 1.0), exp(-abs(tl - 2.4) * 9.0) * 0.25 * fade);
