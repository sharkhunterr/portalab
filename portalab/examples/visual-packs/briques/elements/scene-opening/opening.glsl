// Bricks — the opening (u_age: seconds, 3.0 s): the giant brick's four studs lighting up one by one over its
  // top, then at 1.85 s the burst — a flash, a ring, little bricks of every colour thrown out spinning and falling
  // back with gravity, white sparkles.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float boom = 1.85;
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 at = vec2(-0.105 + fk * 0.07, 0.24);
    float on = smoothstep(0.4 + fk * 0.3, 0.5 + fk * 0.3, age) * step(age, boom);
    o = over(o, vec3(1.0, 0.9, 0.6), exp(-length(c - at) * 40.0) * on * 0.8);
  }
  if (age > boom) {
    float s = age - boom;
    float fade = smoothstep(1.15, 0.7, s);
    o = over(o, vec3(1.0, 0.98, 0.9), exp(-length(c) * 4.0) * smoothstep(0.3, 0.0, s));
    o = over(o, vec3(1.0, 0.9, 0.6), smoothstep(0.02, 0.0, abs(length(c) - s * 0.9)) * fade);
    for (int k = 0; k < 36; k++) {
      float fk = float(k);
      float ang = hash(vec2(fk, 1.0)) * 6.2832;
      float speed = 0.5 + 0.7 * hash(vec2(fk, 2.0));
      vec2 at = vec2(cos(ang), sin(ang) * 0.8 + 0.5) * speed * s + vec2(0.0, -0.9 * s * s);
      float spin = s * (4.0 + 6.0 * hash(vec2(fk, 3.0))) + fk;
      vec2 q = mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * (c - at);
      float w = 0.022 + 0.022 * step(0.5, hash(vec2(fk, 4.0)));
      float body = step(abs(q.x), w) * step(abs(q.y), 0.012);
      float studs = step(0.012, q.y) * step(q.y, 0.019) * step(abs(q.x), w) * step(abs(fract(q.x / 0.011 + 0.5) - 0.5), 0.3);
      float hh = hash(vec2(fk, 5.0));
      vec3 bc = hh < 0.25 ? vec3(0.84, 0.16, 0.16) : (hh < 0.5 ? vec3(0.97, 0.77, 0.12) : (hh < 0.75 ? vec3(0.12, 0.44, 0.84) : vec3(0.16, 0.62, 0.29)));
      o = over(o, bc * (0.75 + 0.35 * smoothstep(-0.012, 0.012, q.y)), clamp(body + studs, 0.0, 1.0) * fade);
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
