// Portalab — name_style/namegold: the « aurum » effect (spec 028, B2)
  vec2 w = p * 1.4 + vec2(fbm(p * 1.2 + t * 0.25), fbm(p * 1.2 - t * 0.2)) * 0.9;
  float h = fbm(w * 1.5 + t * 0.15);
  float hx = fbm((w + vec2(0.05, 0.0)) * 1.5 + t * 0.15) - h;
  float hy = fbm((w + vec2(0.0, 0.05)) * 1.5 + t * 0.15) - h;
  vec3 n = normalize(vec3(-hx * 14.0, -hy * 14.0, 1.0));
  vec3 l = normalize(vec3(-0.4, 0.6, 0.7));
  float diff = clamp(dot(n, l), 0.0, 1.0);
  float spec = pow(clamp(dot(reflect(-l, n), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 20.0);
  vec3 gold = mix(vec3(0.42, 0.25, 0.04), vec3(1.0, 0.78, 0.28), diff) + vec3(1.0, 0.95, 0.8) * spec * 0.8;
  float sweep = smoothstep(0.3, 0.0, abs(p.x + p.y * 0.5 - mod(t * 1.6, 2.0 * ax + 6.0) + ax + 3.0));
  gold += vec3(1.0, 0.95, 0.75) * sweep * 0.6;
  gold += vec3(1.0, 0.85, 0.4) * smoothstep(-0.2, 0.0, d) * 0.4;
  o = over(o, vec3(1.0, 0.75, 0.2), exp(-max(d, 0.0) * 4.5) * 0.35 * step(0.0, d));
  o = over(o, gold, smoothstep(0.03, -0.03, d));
