vec2 c = floor(((gl_FragCoord.xy - 0.5 * u_res) / u_res.y) * 90.0) / 90.0;
  // Rétro — round the cartridge: pixel stars blinking in and out, a glow pulsing in steps (a stage over
  // the booster's place: gl_FragCoord, u_res, t; into o).
  float pulse = floor((0.5 + 0.5 * sin(t * 3.0)) * 4.0) / 4.0;
  o = over(o, vec3(0.5, 0.6, 1.0), step(length(c * vec2(1.3, 1.0)), 0.32) * step(0.25, length(c * vec2(1.3, 1.0))) * 0.15 * pulse);
  for (int k = 0; k < 12; k++) {
    float fk = float(k);
    vec2 sp = floor(vec2(hash(vec2(fk, 1.0)) - 0.5, hash(vec2(fk, 2.0)) - 0.5) * vec2(0.8, 0.9) * 90.0) / 90.0;
    float on = step(0.5, fract(t * (0.8 + hash(vec2(fk, 3.0))) + hash(vec2(fk, 4.0))));
    vec2 q = abs(c - sp) * 90.0;
    float star = step(q.x + q.y, 1.1) + step(q.x, 0.1) * step(q.y, 2.1) + step(q.y, 0.1) * step(q.x, 2.1);
    o = over(o, mix(vec3(1.0, 0.95, 0.4), vec3(0.6, 0.9, 1.0), step(0.5, hash(vec2(fk, 5.0)))), clamp(star, 0.0, 1.0) * on);
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.85, 0.3), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
