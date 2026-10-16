// Portalab — name_style/nameblaze: the « blaze » effect (spec 028, B2)
  vec2 q = vec2(p.x * 1.5, p.y * 1.1 - t * 2.4);
  float n = fbm(q + vec2(0.0, fbm(q * 1.7 + t * 0.6)) * 0.8);
  float reach = 0.25 + 1.1 * smoothstep(-1.0, 1.4, p.y);
  float f = 1.25 - max(d, 0.0) / (reach * (0.45 + 1.1 * n)) - 0.15 * noise(vec2(p.x * 4.0, t * 6.0));
  f *= smoothstep(-0.2, 0.05, d) * step(-1.6, p.y);
  vec3 fire = mix(vec3(0.75, 0.08, 0.02), vec3(1.0, 0.5, 0.05), smoothstep(0.25, 0.6, f));
  fire = mix(fire, vec3(1.0, 0.88, 0.45), smoothstep(0.65, 0.95, f));
  fire = mix(fire, vec3(1.0, 0.98, 0.9), smoothstep(0.95, 1.15, f));
  o = over(o, fire, smoothstep(0.18, 0.5, f));
  float ember = fbm(p * 3.0 + vec2(t * 0.3, -t * 0.5));
  vec3 body = mix(vec3(0.22, 0.03, 0.01), vec3(0.75, 0.16, 0.02), smoothstep(0.35, 0.75, ember));
  body = mix(body, vec3(1.0, 0.55, 0.1), smoothstep(0.7, 0.9, ember) * 0.8);
  body += vec3(1.0, 0.45, 0.08) * smoothstep(-0.25, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d));
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float life = fract(t * (0.5 + 0.3 * hash(vec2(fi, 1.0))) + hash(vec2(fi, 2.0)));
    vec2 s = vec2((hash(vec2(fi, 3.0)) - 0.5) * 2.0 * ax + sin(life * 6.0 + fi) * 0.2, 0.6 + life * 2.6);
    o = over(o, vec3(1.0, 0.7, 0.25), smoothstep(0.08, 0.0, length(p - s)) * (1.0 - life));
  }
