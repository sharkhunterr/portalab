// Clear blue plastic behind the art: studs seen through the material, caustics rippling where the light
  // refracts, a cool glow.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec3 base = vec3(0.25, 0.55, 0.95);
  vec2 g = c * 7.0 + 0.5;
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
  vec2 cq = c * 6.0 + vec2(t * 0.2, -t * 0.15);
  float caust = pow(abs(sin(fbm(cq) * 9.0 + t * 0.8)), 8.0) + 0.6 * pow(abs(sin(fbm(cq * 1.7 + 3.0) * 7.0 - t * 0.6)), 10.0);
  col = mix(col, col * 0.7 + vec3(0.1, 0.25, 0.5), 0.35);
  col += vec3(0.75, 0.9, 1.0) * caust * 0.45;
  o = vec4(col, 1.0);
