// An epic card turned: a spiral of rainbow bricks rising round it, turning (the near turn bright, the far one
  // dim), sparks flying off, a glow behind (u_age, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.1, age);
  o = over(o, vec3(1.0, 0.85, 1.0), exp(-length(c) * 4.0) * 0.35 * fade);
  for (int k = 0; k < 26; k++) {
    float fk = float(k);
    float rise = -0.55 + fk * 0.045 + age * 0.25;
    float turn = fk * 0.7 + age * 3.0;
    vec2 at = vec2(sin(turn) * 0.42, rise);
    float near = cos(turn);
    vec2 q = (c - at) / (0.75 + 0.25 * near);
    float body = step(abs(q.x), 0.032) * step(abs(q.y), 0.014);
    float studs = step(0.014, q.y) * step(q.y, 0.021) * step(abs(q.x), 0.032) * step(abs(fract(q.x / 0.016 + 0.5) - 0.5), 0.3);
    vec3 bc = 0.5 + 0.5 * cos(6.2832 * (fk / 26.0 + vec3(0.0, 0.33, 0.67)));
    float shown = step(0.0, age - fk * 0.03) * smoothstep(0.6, 0.4, abs(rise));
    o = over(o, bc * (0.6 + 0.5 * step(0.0, near)), clamp(body + studs, 0.0, 1.0) * shown * mix(0.45, 1.0, step(0.0, near)) * fade);
    o = over(o, vec3(1.0), exp(-length(c - at - vec2(0.0, 0.03)) * 180.0) * step(0.9, sin(age * 9.0 + fk)) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
