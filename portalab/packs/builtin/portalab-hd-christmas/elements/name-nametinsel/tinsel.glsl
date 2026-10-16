// Portalab — name_style/nametinsel: the « tinsel » effect (spec 028, B2)
  float s = atan(p.y, p.x / max(ax, 0.001));
  float band = exp(-pow(max(d, 0.0) * 6.0 - 0.35, 2.0) * 6.0) * step(0.0, d);
  float twist = 0.5 + 0.5 * sin(s * 18.0 + d * 40.0 - t * 2.5);
  vec3 col = mix(vec3(0.95, 0.75, 0.2), vec3(0.15, 0.75, 0.35), step(0.5, fract(s * 1.4 + t * 0.05)));
  o = over(o, col, band * (0.45 + 0.55 * twist));
  vec2 g = p * 14.0;
  float glint = step(0.9, hash(floor(g) + floor(t * 6.0))) * smoothstep(0.35, 0.0, length(fract(g) - 0.5));
  o = over(o, vec3(1.0, 0.97, 0.8), glint * band * 1.5);
  o = over(o, vec3(1.0, 0.85, 0.35), exp(-max(d, 0.0) * 5.0) * 0.25 * step(0.0, d));
  vec3 body = mix(vec3(0.35, 0.03, 0.06), vec3(0.6, 0.12, 0.1), fbm(p * 2.5 + t * 0.2));
  body += vec3(1.0, 0.8, 0.3) * smoothstep(-0.18, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d));
