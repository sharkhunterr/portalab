// Nugget burst — a celebration (gl_FragCoord, u_res, u_age, 3 s): gold nuggets thrown up from the reward,
  // glinting, falling back into a cloud of dust.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.1, age);
  float dustline = fbm(vec2(c.x * 5.0 + age, c.y * 6.0)) * smoothstep(-0.05, -0.35, c.y) * smoothstep(0.0, 0.6, age);
  o = over(o, vec3(0.75, 0.55, 0.3), dustline * 0.6 * fade);
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    float ang = 1.5708 + (hash(vec2(fk, 1.0)) - 0.5) * 2.4;
    float speed = 0.5 + 0.6 * hash(vec2(fk, 2.0));
    vec2 at = vec2(0.0, -0.1) + vec2(cos(ang), sin(ang)) * speed * age + vec2(0.0, -0.6 * age * age);
    vec2 q = c - at;
    float size = 0.01 + 0.012 * hash(vec2(fk, 3.0));
    float lump = size * (0.8 + 0.4 * noise(vec2(atan(q.y, q.x) * 2.0, fk)));
    float nugget = smoothstep(0.002, 0.0, length(q) - lump);
    o = over(o, mix(vec3(0.75, 0.5, 0.1), vec3(1.0, 0.85, 0.35), clamp(dot(normalize(q + 0.0001), vec2(-0.6, 0.8)) * 0.5 + 0.5, 0.0, 1.0)), nugget * fade);
    o = over(o, vec3(1.0, 0.98, 0.85), exp(-length(q - vec2(-0.3, 0.3) * size) * 600.0) * step(0.7, sin(age * 12.0 + fk) * 0.5 + 0.5) * fade);
  }
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
