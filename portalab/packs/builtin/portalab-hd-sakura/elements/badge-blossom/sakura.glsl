// Portalab — badge/sakura: the « sakura » effect (spec 028, B2)
  vec3 body = mix(vec3(0.3, 0.06, 0.17), vec3(0.75, 0.32, 0.5), 0.5 + 0.5 * sin(p.x * 1.5 + t * 0.5) * fbm(p * 2.0));
  body += vec3(1.0, 0.8, 0.9) * smoothstep(-0.2, 0.0, d) * 0.5;
  o = over(o, vec3(1.0, 0.6, 0.8), exp(-max(d, 0.0) * 4.0) * 0.3 * step(0.0, d));
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 10; i++) {
    float fi = float(i);
    float life = fract(t * 0.12 * (1.0 + hash(vec2(fi, 31.0))) + hash(vec2(fi, 32.0)));
    vec2 pos = vec2(-ax - 1.0 + life * (2.0 * ax + 2.0), 1.4 - life * 2.8 + 0.3 * sin(life * 6.0 + fi));
    float rot = t * 2.0 + fi;
    vec2 q = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * (p - pos) / 0.14;
    float petal = smoothstep(1.0, 0.75, length(q * vec2(1.0, 1.8))) * smoothstep(-0.1, 0.25, q.x + abs(q.y) * 1.2);
    o = over(o, mix(vec3(1.0, 0.72, 0.85), vec3(0.95, 0.45, 0.65), smoothstep(-0.8, 0.8, q.x)), petal * 0.95);
  }
