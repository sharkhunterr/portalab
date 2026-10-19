// Cinema — round the clapperboard: a set light shining down on it in a soft cone, dust turning in its light,
  // its warm pool on the floor (a stage over its place).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float along = clamp((0.55 - c.y) / 1.0, 0.0, 1.0);
  float cone = smoothstep(0.08 + along * 0.35, 0.03 + along * 0.2, abs(c.x)) * step(c.y, 0.55);
  o = over(o, vec3(1.0, 0.92, 0.75), cone * 0.12);
  o = over(o, vec3(1.0, 0.85, 0.6), exp(-length((c - vec2(0.0, -0.36)) * vec2(1.0, 4.0)) * 4.0) * 0.25);
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    vec2 at = vec2((hash(vec2(fk, 1.0)) - 0.5) * 0.5, hash(vec2(fk, 2.0)) - 0.5) + vec2(noise(vec2(t * 0.2, fk)) - 0.5, noise(vec2(fk, t * 0.15)) - 0.5) * 0.1;
    float inCone = smoothstep(0.08 + clamp((0.55 - at.y), 0.0, 1.0) * 0.35, 0.0, abs(at.x));
    o = over(o, vec3(1.0, 0.95, 0.85), exp(-length(c - at) * 520.0) * inCone);
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(0.95, 0.9, 1.0), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
