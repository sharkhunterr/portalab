// Noël — round the gift: a warm glow and little lights twinkling around it, a few snowflakes landing on it
  // (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.6, 0.35), exp(-dot(c * vec2(1.5, 1.0), c * vec2(1.5, 1.0)) * 10.0) * 0.25);
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float ang = fk / 18.0 * 6.2832;
    vec2 b = vec2(cos(ang) * 0.27, sin(ang) * 0.36);
    float on = pow(0.5 + 0.5 * sin(t * 3.0 + fk * 2.4), 3.0);
    vec3 col = mix(vec3(1.0, 0.85, 0.4), vec3(1.0, 0.35, 0.3), step(0.5, hash(vec2(fk, 1.0))));
    o = over(o, col, exp(-length(c - b) * 70.0) * on);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
