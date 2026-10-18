// Céleste — round the sealed pack: a soft violet halo and three little moons on tilted orbits, passing in
  // front and behind (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(0.45, 0.35, 1.0), exp(-dot(c * vec2(1.4, 1.0), c * vec2(1.4, 1.0)) * 9.0) * 0.28);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float ang = t * (0.5 + 0.18 * fk) + fk * 2.1;
    float rx = 0.3 + 0.06 * fk;
    vec2 m = vec2(cos(ang) * rx, sin(ang) * rx * (0.22 + 0.08 * fk));
    float behind = step(0.0, sin(ang));
    float size = 0.012 + 0.004 * fk;
    float moon = smoothstep(size, size * 0.6, length(c - m));
    vec3 tint = mix(vec3(0.85, 0.9, 1.0), vec3(1.0, 0.85, 0.6), fk / 2.0);
    o = over(o, tint, moon * mix(1.0, 0.25, behind));
    o = over(o, tint, exp(-length(c - m) * 60.0) * 0.4 * mix(1.0, 0.3, behind));
    // the orbit's faint line
    vec2 e = c / vec2(rx, rx * (0.22 + 0.08 * fk));
    o = over(o, vec3(0.8, 0.75, 1.0), smoothstep(0.03, 0.0, abs(length(e) - 1.0)) * 0.08);
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(0.6, 0.5, 1.0), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
