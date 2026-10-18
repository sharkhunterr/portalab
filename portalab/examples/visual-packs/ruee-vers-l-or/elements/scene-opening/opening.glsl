// Gold Rush — the fuse (u_age: seconds, 3.0 s): a spark running down the fuse, fizzling; at 2.05 s the blast —
  // a flash, a ring of dust, smoke billowing, gold nuggets thrown up and falling back.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float boom = 2.05;
  vec2 spark = mix(vec2(0.06, 0.42), vec2(0.0, 0.25), smoothstep(0.0, boom, age));
  o = over(o, vec3(1.0, 0.85, 0.4), (exp(-length(c - spark) * 120.0) + exp(-length(c - spark) * 30.0) * 0.3) * step(age, boom));
  for (int k = 0; k < 10; k++) {
    float fk = float(k);
    float life = fract(age * 4.0 + fk * 0.1);
    vec2 sp = spark + vec2(hash(vec2(fk, 1.0)) - 0.5, hash(vec2(fk, 2.0))) * 0.08 * life;
    o = over(o, vec3(1.0, 0.75, 0.3), exp(-length(c - sp) * 400.0) * (1.0 - life) * step(age, boom));
  }
  if (age > boom) {
    float s = age - boom;
    float fade = smoothstep(0.95, 0.5, s);
    float r = length(c);
    o = over(o, vec3(1.0, 0.95, 0.8), exp(-r * 5.0) * smoothstep(0.35, 0.0, s));
    o = over(o, vec3(0.7, 0.55, 0.4), fbm(c * 5.0 - s) * smoothstep(0.1 + s * 0.5, 0.0, r) * fade);
    o = over(o, vec3(0.85, 0.65, 0.4), smoothstep(0.02, 0.0, abs(r - s * 0.6)) * fade);
    for (int k = 0; k < 24; k++) {
      float fk = float(k);
      float ang = 1.5708 + (hash(vec2(fk, 3.0)) - 0.5) * 2.6;
      vec2 at = vec2(cos(ang), sin(ang)) * s * (0.5 + 0.5 * hash(vec2(fk, 4.0))) + vec2(0.0, -0.6 * s * s);
      o = over(o, vec3(1.0, 0.8, 0.3), smoothstep(0.012, 0.006, length(c - at)) * fade);
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
