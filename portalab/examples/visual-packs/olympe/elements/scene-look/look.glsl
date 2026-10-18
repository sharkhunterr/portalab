// Olympus — round the amphora: a soft golden halo, specks of gold dust rising slowly round it.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.85, 0.45), exp(-dot(c * vec2(1.3, 1.0), c * vec2(1.3, 1.0)) * 6.0) * 0.25);
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    float life = fract(t * 0.12 + hash(vec2(fk, 1.0)));
    vec2 at = vec2((hash(vec2(fk, 2.0)) - 0.5) * 0.7 + 0.03 * sin(t + fk), -0.4 + life * 0.9);
    o = over(o, vec3(1.0, 0.85, 0.4), exp(-length(c - at) * 260.0) * sin(life * 3.1416));
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.85, 0.45), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
