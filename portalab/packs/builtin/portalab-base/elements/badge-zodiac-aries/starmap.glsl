// Portalab — badge/starmap: the « starmap » effect (spec 028, B2)
  vec3 chart = mix(vec3(0.02, 0.05, 0.16), vec3(0.04, 0.1, 0.26), smoothstep(-1.0, 1.0, p.y));
  float gx = abs(fract((p.x + 0.05 * p.y * p.y) * 2.0) - 0.5);
  float gy = abs(fract(p.y * 2.0 + 0.04 * p.x * p.x) - 0.5);
  chart += vec3(0.25, 0.45, 0.85) * (smoothstep(0.03, 0.0, gx) + smoothstep(0.03, 0.0, gy)) * 0.18;
  vec2 sg = p * 13.0;
  chart += vec3(0.8, 0.88, 1.0) * step(0.93, hash(floor(sg))) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * 0.6;
  float cyc = mod(t, 9.0);
  float shine = exp(-abs(cyc - 6.0) * 2.0);
  float fade = smoothstep(9.0, 7.8, cyc);
  float lines = 0.0;
  float stars = 0.0;
  vec2 prev = vec2(0.0);
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    // the Plough's seven stars, fitted to the shape
    vec2 s = fi < 0.5 ? vec2(-0.95, 0.35) : fi < 1.5 ? vec2(-0.55, 0.42) : fi < 2.5 ? vec2(-0.2, 0.28) : fi < 3.5 ? vec2(0.12, 0.12)
      : fi < 4.5 ? vec2(0.2, -0.38) : fi < 5.5 ? vec2(0.82, -0.3) : vec2(0.78, 0.2);
    s *= vec2(min(ax, 1.6), 1.0) * 0.82;
    float born = fi * 0.55;
    float on = smoothstep(born, born + 0.3, cyc) * fade;
    stars += exp(-length(p - s) * 30.0) * on * (1.0 + shine);
    if (i > 0) {
      vec2 ab = s - prev;
      float h = clamp(dot(p - prev, ab) / dot(ab, ab), 0.0, 1.0);
      float drawn = clamp((cyc - born + 0.55) / 0.55, 0.0, 1.0);
      float seg = smoothstep(0.022, 0.0, length(p - prev - ab * h)) * step(h, drawn);
      lines += seg * fade;
    }
    if (i == 6) {
      vec2 ab = vec2(0.12, 0.12) * vec2(min(ax, 1.6), 1.0) * 0.82 - s;
      float h = clamp(dot(p - s, ab) / dot(ab, ab), 0.0, 1.0);
      lines += smoothstep(0.022, 0.0, length(p - s - ab * h)) * smoothstep(3.6, 4.0, cyc) * fade;
    }
    prev = s;
  }
  chart += vec3(0.55, 0.8, 1.0) * lines * (0.55 + 0.45 * shine);
  chart += vec3(1.0, 0.97, 0.88) * stars;
  chart += vec3(0.4, 0.65, 1.0) * smoothstep(-0.2, 0.0, d) * 0.45;
  float ang = atan(p.y, p.x / max(ax, 0.001));
  float glint = pow(0.5 + 0.5 * sin(ang * 5.0 + t * 0.7), 18.0) * exp(-max(d, 0.0) * 6.0) * step(0.0, d);
  o = over(o, vec3(0.6, 0.8, 1.0), exp(-max(d, 0.0) * 4.0) * 0.22 * step(0.0, d) + glint * 0.6);
  o = over(o, chart, smoothstep(0.03, -0.03, d));
