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
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.65, 0.35), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
