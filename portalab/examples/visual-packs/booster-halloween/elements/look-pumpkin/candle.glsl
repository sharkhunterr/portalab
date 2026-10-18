// Halloween — round the jack-o'-lantern: an orange glow breathing with the candle's flicker, a few embers
  // rising (a stage over the booster's place: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float flicker = 0.75 + 0.15 * sin(t * 13.0) + 0.1 * sin(t * 23.0 + 1.3) + 0.08 * noise(vec2(t * 6.0, 0.0));
  o = over(o, vec3(1.0, 0.55, 0.12), exp(-dot(c * vec2(1.2, 1.0), c * vec2(1.2, 1.0)) * 8.0) * 0.35 * flicker);
  for (int k = 0; k < 10; k++) {
    float fk = float(k);
    float life = fract(t * (0.2 + 0.1 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 e = vec2((hash(vec2(fk, 3.0)) - 0.5) * 0.3 + 0.03 * sin(life * 12.0 + fk), -0.05 + life * 0.5);
    o = over(o, vec3(1.0, 0.6, 0.2), exp(-length(c - e) * 160.0) * smoothstep(1.0, 0.6, life) * smoothstep(0.0, 0.1, life));
  }
  // a thin smoke curling up from round the stalk
  vec2 sm = c - vec2(0.02, 0.2);
  float curl = fbm(vec2(sm.x * 9.0 + 0.6 * sin(sm.y * 8.0 - t * 0.9), sm.y * 4.0 - t * 0.6));
  float plume = smoothstep(0.06, 0.0, abs(sm.x - 0.03 * sin(sm.y * 9.0 - t * 1.3)) - sm.y * 0.12) * step(0.0, sm.y) * smoothstep(0.35, 0.05, sm.y);
  o = over(o, vec3(0.55, 0.5, 0.6), plume * smoothstep(0.45, 0.75, curl) * 0.35);
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.5, 0.1), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
