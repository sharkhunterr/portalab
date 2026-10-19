// An epic card turned: a gold art deco fan unfolding behind it, rays and rings; a marquee of bulbs round it
  // lighting up one by one from the top, then chasing, each with its bloom; two film ribbons coiling round it
  // (a helix: the near turn bright, the far one dim, their sprocket holes running); gold sparks rising
  // (u_age, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.1, age);
  float r = length(c);
  float up = atan(c.x, c.y);
  float unfold = smoothstep(0.0, 0.55, age);
  float fan = smoothstep(1.75 * unfold + 0.25, 1.75 * unfold - 0.1, abs(up)) * smoothstep(0.26, 0.36, r) * smoothstep(0.95, 0.5, r);
  float rays = smoothstep(0.35, 0.65, abs(fract(up * 6.0 / 3.1416) - 0.5) * 2.0);
  float rings = smoothstep(0.006, 0.0, abs(fract(r * 9.0 - age * 0.6) - 0.5) - 0.42);
  o = over(o, mix(vec3(0.75, 0.48, 0.12), vec3(1.0, 0.86, 0.45), rays), fan * (0.32 + 0.25 * rays + 0.3 * rings) * fade);
  o = over(o, vec3(1.0, 0.85, 0.5), exp(-r * 4.0) * 0.35 * fade);
  // the marquee's bulbs, on a rounded frame round the card
  vec2 hb = vec2(0.34, 0.47);
  for (int k = 0; k < 44; k++) {
    float fk = float(k);
    float along = fk / 44.0;
    float ang = along * 6.2832 + 1.5708;
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 at = dir / max(abs(dir.x) / hb.x, abs(dir.y) / hb.y);
    float order = min(along, 1.0 - along);
    float lit = smoothstep(order * 1.6, order * 1.6 + 0.05, age - 0.15);
    float chase = 0.55 + 0.45 * step(0.5, fract(fk * 0.5 + floor(age * 6.0) * 0.5));
    float on = lit * mix(1.0, chase, smoothstep(0.95, 1.15, age));
    float dl = length(c - at);
    o = over(o, vec3(1.0, 0.98, 0.85), smoothstep(0.016, 0.01, dl) * on * fade);
    o = over(o, vec3(1.0, 0.72, 0.28), exp(-dl * 45.0) * 0.7 * on * fade);
  }
  // two film ribbons coiling round the card
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float turn = c.y * 7.0 - age * 5.0 + fk * 3.1416;
    float x = 0.42 * sin(turn);
    float near = cos(turn);
    float w = 0.032;
    float on = smoothstep(0.35, 0.6, age) * smoothstep(0.62, 0.45, abs(c.y));
    float strip = smoothstep(w, w - 0.004, abs(c.x - x));
    float holes = step(0.6, fract((c.y - age * 0.4) * 55.0)) * smoothstep(0.012, 0.008, abs(abs(c.x - x) - w * 0.72));
    vec3 film = mix(vec3(0.35, 0.22, 0.06), vec3(0.95, 0.75, 0.3), 0.5 + 0.5 * near);
    o = over(o, film, clamp(strip - holes, 0.0, 1.0) * on * mix(0.35, 0.95, step(0.0, near)) * fade);
  }
  for (int k = 0; k < 24; k++) {
    float fk = float(k);
    float life = fract(age * (0.6 + 0.5 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 at = vec2((hash(vec2(fk, 3.0)) - 0.5) * 0.9 + 0.04 * sin(life * 9.0 + fk), -0.5 + life * 1.0);
    o = over(o, vec3(1.0, 0.85, 0.4), exp(-length(c - at) * 420.0) * sin(life * 3.1416) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
