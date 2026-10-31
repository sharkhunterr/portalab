// Nitrate — the booster stage: a silent film's black lacquer, a sepia Art Deco sunburst rising from the foot,
  // silver hairlines with cut corners, the projector's beam from above where dust drifts, its flicker and the
  // print's scratches (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.05, 0.04, 0.035, 1.0);
  vec2 sb = c - vec2(0.0, -0.62);
  float ang = atan(sb.x, sb.y);
  float rays = step(0.5, fract(ang * 7.0 + t * 0.02));
  float fanMask = smoothstep(1.05, 0.2, length(sb));
  o = over(o, mix(vec3(0.36, 0.25, 0.15), vec3(0.66, 0.5, 0.32), rays), fanMask * 0.85);
  for (int k = 0; k < 4; k++) {
    float r = 0.42 + float(k) * 0.07;
    o = over(o, vec3(0.86, 0.84, 0.8), smoothstep(0.004, 0.0, abs(length(sb) - r)) * 0.5 * step(0.0, sb.y));
  }
  // the hairlines: a double frame with cut corners
  vec2 a = abs(c) - vec2(asp * 0.5 - 0.05, 0.45);
  float fr1 = max(a.x, a.y), cut = (abs(c.x) + abs(c.y)) - (asp * 0.5 + 0.45 - 0.12);
  float frame = max(fr1, cut);
  o = over(o, vec3(0.86, 0.84, 0.8), smoothstep(0.003, 0.0, abs(frame)) + smoothstep(0.003, 0.0, abs(frame + 0.02)));
  // the beam, the dust in it, the flicker, the scratches
  float beam = smoothstep(0.35 + (0.5 - c.y) * 0.3, 0.0, abs(c.x)) * smoothstep(-0.5, 0.5, c.y);
  o = over(o, vec3(0.97, 0.92, 0.8), beam * 0.1);
  for (int k = 0; k < 24; k++) {
    float fk = float(k);
    vec2 dp = vec2((hash(vec2(fk, 1.0)) - 0.5) * 0.6, fract(hash(vec2(fk, 2.0)) - t * 0.015 * (1.0 + hash(vec2(fk, 3.0)))) - 0.5);
    o = over(o, vec3(0.97, 0.92, 0.8), exp(-length(c - dp) * 700.0) * beam * 2.5);
  }
  float fl = floor(t * 12.0);
  float sx = (hash(vec2(fl, 4.0)) - 0.5) * asp;
  o = over(o, vec3(0.97, 0.92, 0.8), smoothstep(0.0015, 0.0, abs(c.x - sx)) * 0.35 * step(0.6, hash(vec2(fl, 5.0))));
  o.rgb *= 0.92 + 0.08 * hash(vec2(fl, 6.0));
