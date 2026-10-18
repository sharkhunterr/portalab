// Cogwork — round the safe: steam leaking from its seams, a warm glow (a stage over the booster's place).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.65, 0.3), exp(-dot(c * vec2(1.3, 1.0), c * vec2(1.3, 1.0)) * 8.0) * 0.2);
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 seam = vec2(fk < 1.5 ? -0.15 : 0.15, 0.2 - mod(fk, 2.0) * 0.4);
    vec2 q = c - seam;
    float wisp = fbm(vec2(q.x * 8.0, q.y * 6.0 - t * 1.5 + fk)) * smoothstep(0.12, 0.0, length(q * vec2(1.0, 0.5))) * step(0.5, fract(t * 0.3 + fk * 0.27));
    o = over(o, vec3(0.9, 0.88, 0.84), wisp * 0.6);
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.7, 0.35), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
