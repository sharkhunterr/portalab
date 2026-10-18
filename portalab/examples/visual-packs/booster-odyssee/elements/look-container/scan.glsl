// Odyssée — round the container: a scan beam sweeping it up and down, holographic rings turning round it,
  // status lights blinking (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float sweep = sin(t * 1.2) * 0.22;
  float beam = smoothstep(0.012, 0.0, abs(c.y - sweep)) * step(abs(c.x), 0.17);
  o = over(o, vec3(0.4, 0.95, 1.0), beam * 0.7);
  o = over(o, vec3(0.3, 0.85, 1.0), exp(-abs(c.y - sweep) * 30.0) * step(abs(c.x), 0.17) * 0.15);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 e = c / vec2(0.32 + fk * 0.05, 0.08 + fk * 0.02);
    float ang = atan(e.y, e.x) + t * (0.8 - fk * 1.4);
    float ring = smoothstep(0.06, 0.0, abs(length(e) - 1.0)) * step(0.4, fract(ang / 6.2832 * 6.0));
    o = over(o, vec3(0.3, 0.9, 1.0), ring * 0.55);
  }
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 lp = vec2(-0.15 + fk * 0.1, -0.24);
    o = over(o, mix(vec3(1.0, 0.3, 0.2), vec3(0.3, 1.0, 0.5), step(1.5, fk)), exp(-length(c - lp) * 140.0) * step(0.5, fract(t * (0.7 + fk * 0.3))));
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(0.3, 0.9, 1.0), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
