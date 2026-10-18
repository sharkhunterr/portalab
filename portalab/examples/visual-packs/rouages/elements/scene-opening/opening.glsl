// Cogwork — the safe unlocking (u_age: seconds, 2.8 s): valves letting off steam faster and faster, then at
  // 1.9 s a golden flash as the door swings, light pouring out with sparks.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float ang = fk * 1.047 + 0.4;
    vec2 dv = vec2(cos(ang), sin(ang));
    float along = dot(c, dv);
    float across = abs(dot(c, vec2(-dv.y, dv.x)));
    float on = step(0.3 + fk * 0.2, age) * step(age, 2.0) * step(0.4, fract(age * (2.0 + age) + fk * 0.3));
    float jet = smoothstep(0.02 + along * 0.2, 0.0, across) * step(0.18, along) * fbm(vec2(along * 8.0 - age * 6.0, across * 12.0 + fk));
    o = over(o, vec3(0.92, 0.9, 0.86), jet * on);
  }
  if (age > 1.9) {
    float s = age - 1.9;
    o = over(o, vec3(1.0, 0.85, 0.5), exp(-length(c) * 4.0) * smoothstep(0.6, 0.0, s));
    float a = atan(c.y, c.x);
    o = over(o, vec3(1.0, 0.8, 0.4), pow(0.5 + 0.5 * sin(a * 12.0), 8.0) * smoothstep(0.7, 0.1, length(c)) * smoothstep(0.9, 0.2, s) * 0.6);
    for (int k = 0; k < 20; k++) {
      float fk = float(k);
      float ang = hash(vec2(fk, 1.0)) * 6.2832;
      vec2 sp = vec2(cos(ang), sin(ang)) * s * (0.4 + 0.4 * hash(vec2(fk, 2.0)));
      o = over(o, vec3(1.0, 0.8, 0.4), exp(-length(c - sp) * 250.0) * smoothstep(0.9, 0.3, s));
    }
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
