// Gold studs behind the art: each lit and shadowed, glints racing over them in waves, a rainbow sheen passing
  // diagonally, sparkles popping on the domes.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec3 base = vec3(0.92, 0.68, 0.18);
  vec2 g = c * 6.0 + 0.5;
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
  vec2 cell = floor(g);
  float wave = exp(-abs(fract((cell.x + cell.y) * 0.12 - t * 0.35) - 0.5) * 18.0);
  col += vec3(1.0, 0.95, 0.75) * wave * studTop * 0.6;
  float diag = c.x * 0.8 + c.y - mod(t * 0.4, 3.0) + 1.5;
  vec3 rainbow = 0.5 + 0.5 * cos(6.2832 * (diag * 2.0 + vec3(0.0, 0.33, 0.67)));
  col = mix(col, col + rainbow * 0.35, smoothstep(0.25, 0.0, abs(diag)));
  col += vec3(1.0) * step(0.985, hash(cell + floor(t * 4.0))) * studTop;
  o = vec4(col, 1.0);
