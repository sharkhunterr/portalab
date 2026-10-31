// Idylle — the booster stage: a pink dusk, soft lights out of focus drifting, little hearts rising, a warm glow
  // low on the horizon (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(1.0, 0.7, 0.62), vec3(0.42, 0.14, 0.34), smoothstep(-0.4, 0.5, c.y)), 1.0);
  o = over(o, vec3(1.0, 0.85, 0.6), exp(-abs(c.y + 0.3) * 5.0) * 0.5);
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    vec2 p = vec2((hash(vec2(fk, 1.0)) - 0.5) * asp, (hash(vec2(fk, 2.0)) - 0.5)) + 0.04 * vec2(sin(t * 0.3 + fk), cos(t * 0.25 + fk));
    float r = 0.05 + 0.06 * hash(vec2(fk, 3.0));
    o = over(o, mix(vec3(1.0, 0.75, 0.8), vec3(1.0, 0.9, 0.7), hash(vec2(fk, 4.0))), smoothstep(r, r * 0.8, length(c - p)) * 0.25);
  }
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 5.0));
    float age = fract(t * (0.06 + 0.05 * h1) + h1);
    vec2 p = vec2((h1 - 0.5) * asp + 0.03 * sin(t + fk), -0.55 + age * 1.15);
    vec2 q = (c - p) * 42.0; q.y += 0.25;
    float a = q.x * q.x + q.y * q.y - 1.0;   // pow() of a negative number is undefined in GLSL
    float hrt = a * a * a - q.x * q.x * q.y * q.y * q.y;
    o = over(o, vec3(1.0, 0.35, 0.5), step(hrt, 0.0) * (1.0 - age) * 0.9);
  }
