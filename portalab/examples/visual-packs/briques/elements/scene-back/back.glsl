// Face down: a blue studded plate seen from above, each stud lit from the top left, a gleam sweeping over it
  // now and then — every card alike (a back never tells the rarity).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec3 base = vec3(0.12, 0.4, 0.82);
  vec2 g = c * 9.0 + 0.5;
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
  col += vec3(1.0) * exp(-abs(c.x + c.y - mod(t * 0.5, 4.0) + 2.0) * 8.0) * 0.25;
  o = vec4(col, 1.0);
