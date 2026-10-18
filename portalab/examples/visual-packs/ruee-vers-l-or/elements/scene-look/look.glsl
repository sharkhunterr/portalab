// Gold Rush — round the crate: the heat shimmering, a few sparks at the fuse's tip (a stage over its place).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.7, 0.35), exp(-dot(c * vec2(1.2, 1.0), c * vec2(1.2, 1.0)) * 7.0) * 0.15);
  vec2 tip = vec2(0.02, 0.36);
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float life = fract(t * 2.0 + fk * 0.17);
    vec2 sp = tip + vec2((hash(vec2(fk, 1.0)) - 0.5) * 0.06, 0.04) * life * 3.0;
    o = over(o, vec3(1.0, 0.8, 0.3), exp(-length(c - sp) * 300.0) * (1.0 - life) * step(0.5, fract(t * 0.25)));
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.65, 0.25), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
