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
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.5, 0.1), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
