// The marquee's inside: red velvet curtains in folds swaying, lit from below by the footlights, a gold art
  // deco sun rising and turning behind the art, its rays and rings, dust glittering in the light.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float folds = 0.55 + 0.45 * sin(c.x * 38.0 + sin(c.y * 4.0 + t * 0.8) * 1.6 + sin(t * 0.5) * 0.6);
  float foot = smoothstep(0.55, -0.5, c.y);
  vec3 col = vec3(0.45, 0.03, 0.08) * (0.35 + 0.65 * folds) * (0.45 + 0.9 * foot);
  col += vec3(1.0, 0.55, 0.2) * smoothstep(-0.25, -0.5, c.y) * 0.35;
  vec2 sq = c - vec2(0.0, -0.52);
  float sr = length(sq);
  float sa = atan(sq.x, sq.y);
  float rays = smoothstep(0.35, 0.65, abs(fract(sa * 4.5 / 3.1416 + t * 0.05) - 0.5) * 2.0) * step(abs(sa), 1.45);
  float sun = smoothstep(0.85, 0.2, sr) * step(0.12, sr);
  col = mix(col, mix(vec3(0.7, 0.42, 0.08), vec3(1.0, 0.85, 0.45), rays), sun * (0.25 + 0.45 * rays) * 0.75);
  col += vec3(1.0, 0.8, 0.4) * smoothstep(0.006, 0.0, abs(fract(sr * 7.0 - t * 0.2) - 0.5) - 0.44) * step(sr, 0.85) * 0.25;
  col += vec3(1.0, 0.9, 0.6) * exp(-sr * 6.0) * 0.6;
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    vec2 at = vec2(hash(vec2(fk, 1.0)) - 0.5, hash(vec2(fk, 2.0)) - 0.5) * vec2(0.6, 0.9) + vec2(0.0, 0.03 * sin(t + fk));
    col += vec3(1.0, 0.9, 0.6) * exp(-length(c - at) * 260.0) * (0.5 + 0.5 * sin(t * 3.0 + fk * 2.0));
  }
  o = vec4(col, 1.0);
