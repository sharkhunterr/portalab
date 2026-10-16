// Portalab — effect/petalstorm: the « sakurastorm » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float aspect = u_res.x / u_res.y;
  float gust = smoothstep(0.0, 0.8, tl) * smoothstep(7.0, 5.5, tl);
  float ray = pow(max(0.0, sin(atan(c.y - 0.6, c.x + 0.6) * 10.0 + u_age * 0.3)), 8.0) * exp(-length(c - vec2(-0.6, 0.6)) * 1.2);
  o = over(o, vec3(1.0, 0.9, 0.85), ray * 0.25 * gust);
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    float speed = 0.2 + 0.25 * hash(vec2(fi, 71.0));
    float life = fract(u_age * speed + hash(vec2(fi, 72.0)));
    vec2 pos = vec2(-aspect * 0.6 + life * aspect * 1.2, 0.55 - life * 0.6 + (hash(vec2(fi, 73.0)) - 0.5) * 0.9 + 0.08 * sin(life * 8.0 + fi));
    float size = 0.012 + 0.02 * hash(vec2(fi, 74.0));
    float rot = u_age * (1.0 + hash(vec2(fi, 75.0)) * 3.0) + fi;
    vec2 q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * (c - pos) / size;
    q.x /= max(0.3, abs(cos(u_age * 2.0 + fi)));
    float petal = smoothstep(1.0, 0.7, length(q * vec2(1.0, 1.7))) * smoothstep(-0.2, 0.3, q.x + abs(q.y) * 1.2);
    o = over(o, mix(vec3(1.0, 0.75, 0.85), vec3(0.95, 0.5, 0.68), hash(vec2(fi, 76.0))), petal * gust);
  }
