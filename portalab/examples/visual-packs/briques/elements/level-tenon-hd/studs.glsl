// Studs level badge HD — the shape (p, d < 0 inside, ax, t; into o): a studded plate whose colour turns through
  // the primaries, darker in the middle where the level is written, a gleam running over it.
  float hue = fract(t * 0.05);
  vec3 base = mix(mix(vec3(0.84, 0.16, 0.16), vec3(0.12, 0.44, 0.84), smoothstep(0.2, 0.4, hue)), vec3(0.97, 0.72, 0.1), smoothstep(0.55, 0.75, hue));
  base = mix(base, vec3(0.84, 0.16, 0.16), smoothstep(0.85, 1.0, hue));
  vec2 g = p * 3.0 + 0.5;
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
  col *= mix(0.6, 1.0, smoothstep(0.2, 0.7, length(p / vec2(ax, 1.0))));
  col += vec3(1.0) * exp(-abs(p.x + p.y - mod(t, 6.0) + 3.0) * 5.0) * 0.25;
  o = over(o, col, smoothstep(0.03, -0.03, d));
