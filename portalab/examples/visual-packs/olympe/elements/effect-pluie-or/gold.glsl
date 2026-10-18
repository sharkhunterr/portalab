// Shower of gold — a celebration (gl_FragCoord, u_res, u_age, 3 s): golden streaks falling like rain, each
  // flashing as it lands, laurel leaves whirling round the reward.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.15, age);
  for (int k = 0; k < 40; k++) {
    float fk = float(k);
    float x = (hash(vec2(fk, 1.0)) - 0.5) * 1.4;
    float y = 0.7 - fract(age * (0.8 + 0.6 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0))) * 1.4;
    vec2 q = c - vec2(x, y);
    float streak = smoothstep(0.003, 0.0, abs(q.x)) * smoothstep(0.06, 0.0, q.y) * step(0.0, q.y);
    o = over(o, vec3(1.0, 0.82, 0.3), streak * fade);
    o = over(o, vec3(1.0, 0.95, 0.75), exp(-length(q) * 300.0) * fade);
  }
  for (int k = 0; k < 10; k++) {
    float fk = float(k);
    float ang = age * 2.0 + fk * 0.628;
    vec2 at = vec2(cos(ang), sin(ang) * 0.6) * (0.25 + 0.05 * sin(age * 3.0 + fk));
    vec2 q = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * (c - at);
    o = over(o, vec3(0.45, 0.6, 0.25), smoothstep(1.0, 0.8, length(q / vec2(0.03, 0.01))) * 0.8 * fade);
  }
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
