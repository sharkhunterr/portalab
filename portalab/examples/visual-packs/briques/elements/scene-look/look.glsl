// Bricks — round the giant brick: warm light falling on it, and little bricks turning round it in an orbit,
  // the near ones over, the far ones dimmer (a stage over its place).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-dot(c * vec2(1.2, 1.0), c * vec2(1.2, 1.0)) * 6.0) * 0.18);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float ang = t * 0.6 + fk * 0.785;
    vec2 at = vec2(cos(ang) * 0.42, sin(ang) * 0.1 - 0.02);
    float near = 0.5 + 0.5 * sin(ang);
    float spin = t * (1.0 + 0.3 * fk);
    vec2 q = mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * (c - at) / (0.7 + 0.3 * near);
    float body = step(abs(q.x), 0.03) * step(abs(q.y), 0.014);
    float studs = step(0.014, q.y) * step(q.y, 0.021) * step(abs(q.x), 0.03) * step(abs(fract(q.x / 0.015 + 0.5) - 0.5), 0.3);
    float hh = hash(vec2(fk, 2.0));
    vec3 bc = hh < 0.33 ? vec3(0.97, 0.77, 0.12) : (hh < 0.66 ? vec3(0.12, 0.44, 0.84) : vec3(0.16, 0.62, 0.29));
    o = over(o, bc * (0.6 + 0.5 * near), clamp(body + studs, 0.0, 1.0) * (0.55 + 0.45 * near));
  }
  // tension: the glow swells with the pack's double heartbeat (3.4 s), a held breath between
  float beatph = fract(t / 3.4);
  float beat = exp(-pow((beatph - 0.66) * 30.0, 2.0)) + 1.3 * exp(-pow((beatph - 0.77) * 26.0, 2.0));
  vec2 bc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, vec3(1.0, 0.85, 0.6), exp(-dot(bc * vec2(1.3, 1.0), bc * vec2(1.3, 1.0)) * 7.0) * 0.22 * beat);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
