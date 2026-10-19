// Studded plate frame HD — the shape's frame (a rounded box): p, d (< 0 inside), ax, t; writes into o. A plate
  // round the avatar, a grid of studs on it (only where a stud's centre lies on the band), each lit from the top
  // left, a gleam running over the plastic, its colour turning slowly through the primaries.
  float band = step(-0.01, d) * step(d, 0.24);
  float hue = fract(t * 0.03);
  vec3 base = hue < 0.33 ? vec3(0.84, 0.16, 0.16) : (hue < 0.66 ? vec3(0.12, 0.44, 0.84) : vec3(0.97, 0.72, 0.1));
  vec2 g = p * 6.5;
  float dc = badge((floor(g) + 0.5) / 6.5, ax);
  float onBand = step(0.0, dc) * step(dc, 0.2);
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
  col = mix(base * 0.9, col, onBand);
  col += vec3(1.0) * exp(-abs(p.x + p.y - mod(t * 0.8, 6.0) + 3.0) * 4.0) * 0.25;
  o = over(o, col, band);
  o = over(o, base * 0.6, smoothstep(0.02, 0.0, abs(d - 0.24)) * 0.8);
