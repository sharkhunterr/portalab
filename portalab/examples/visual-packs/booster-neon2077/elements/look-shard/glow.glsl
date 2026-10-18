// Néon 2077 — round the shard: a pink and cyan neon halo breathing, glyph columns streaming down at its sides,
  // a slice of glitch now and then (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c * vec2(1.4, 1.0));
  o = over(o, vec3(1.0, 0.15, 0.6), smoothstep(0.03, 0.0, abs(r - 0.36)) * (0.4 + 0.3 * sin(t * 2.0)));
  o = over(o, vec3(0.1, 0.95, 1.0), smoothstep(0.02, 0.0, abs(r - 0.4)) * (0.35 + 0.3 * sin(t * 2.0 + 2.0)));
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float x = (fk < 2.5 ? -0.32 : 0.32) + (mod(fk, 3.0) - 1.0) * 0.03;
    vec2 g = vec2((c.x - x) * 90.0, c.y * 30.0 + t * (3.0 + fk));
    float glyph = step(abs(c.x - x), 0.008) * step(0.45, hash(floor(g) + fk)) * smoothstep(0.5, 0.0, abs(c.y));
    o = over(o, vec3(0.3, 1.0, 0.8), glyph * 0.6);
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.2, 0.7), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
