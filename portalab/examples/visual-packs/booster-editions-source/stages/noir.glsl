// Noir — the booster stage: a detective's office at night, the light of a sign through the venetian blinds
  // sliding on the wall, rain running down the window, the desk lamp's glow, lightning now and then (a stage:
  // gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.03, 0.03, 0.045, 1.0);
  // the window's light: slanted bars, in a soft shape
  float slant = c.y - c.x * 0.35;
  float bars = step(0.55, fract(slant * 11.0 + t * 0.03));
  float win = smoothstep(0.7, 0.1, length((c - vec2(asp * 0.15, 0.05)) * vec2(0.8, 1.1)));
  o = over(o, vec3(0.96, 0.9, 0.76), bars * win * 0.32);
  // rain on the glass: drops falling in columns
  vec2 rq = vec2(c.x * 60.0, c.y * 6.0 + t * 2.5);
  float col = floor(rq.x);
  float drop = fract(rq.y + hash(vec2(col, 1.0)) * 10.0);
  float streak = smoothstep(0.08, 0.0, abs(fract(rq.x) - 0.5) - 0.02) * smoothstep(0.0, 0.25, drop) * smoothstep(0.35, 0.25, drop);
  o = over(o, vec3(0.75, 0.78, 0.85), streak * 0.18 * step(0.5, hash(vec2(col, 2.0))));
  // the lamp
  vec2 lp = c - vec2(-asp * 0.32, -0.36);
  o = over(o, vec3(1.0, 0.8, 0.45), exp(-length(lp * vec2(1.0, 1.6)) * 5.0) * 0.55);
  o = over(o, vec3(0.01, 0.01, 0.015), step(abs(lp.x), 0.12 - (lp.y - 0.02) * 0.8) * step(0.02, lp.y) * step(lp.y, 0.1));
  // a red string of clues on a pinned board, faint
  o = over(o, vec3(0.8, 0.06, 0.07), smoothstep(0.0025, 0.0, abs(c.y - 0.28 - 0.08 * sin(c.x * 6.0))) * step(c.x, -asp * 0.12) * 0.5);
  // lightning, once in a while
  float lt = fract(t / 6.0);
  o.rgb += vec3(0.6, 0.65, 0.8) * (smoothstep(0.62, 0.63, lt) - smoothstep(0.63, 0.66, lt)) * win;
