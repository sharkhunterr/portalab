// Gold brick badge HD — the shape (p, d < 0 inside, ax, t; into o): gold plastic with a grid of studs lit from
  // the top left, a glint running across now and then, a soft glow round it.
  vec3 base = vec3(0.95, 0.72, 0.18);
  vec2 g = p * 2.2 + 0.5;
  vec2 sf = fract(g) - 0.5;
  float sr = length(sf);
  float studTop = smoothstep(0.31, 0.28, sr);
  float sshadow = smoothstep(0.4, 0.3, length(sf - vec2(0.06, -0.07)));
  float srim = smoothstep(0.31, 0.27, sr) - smoothstep(0.27, 0.22, sr);
  float slight = dot(sf / max(sr, 0.0001), vec2(-0.6, 0.8));
  vec3 col = base * (1.0 - 0.3 * sshadow * (1.0 - studTop));
  col = mix(col, base * 1.07, studTop);
  col += vec3(1.0) * srim * max(slight, 0.0) * 0.4;
  col -= base * srim * max(-slight, 0.0) * 0.35;
  col += vec3(1.0, 0.95, 0.75) * exp(-abs(p.x - p.y - mod(t * 1.2, 8.0) + 4.0) * 6.0) * 0.5;
  o = over(o, vec3(1.0, 0.8, 0.3), exp(-max(d, 0.0) * 4.0) * 0.4 * step(0.0, d));
  o = over(o, col, smoothstep(0.03, -0.03, d));
