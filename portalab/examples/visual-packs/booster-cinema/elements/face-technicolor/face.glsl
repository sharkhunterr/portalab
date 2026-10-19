// Technicolor behind the art: the three strips' dyes — red, green, blue — swirling into each other (warped
  // noise), a light leak passing, film grain.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec2 q = c * 2.4 + vec2(t * 0.05, -t * 0.03);
  float w1 = fbm(q + fbm(q * 1.3 + t * 0.08) * 1.4);
  float w2 = fbm(q * 1.2 + vec2(5.2, 1.3) + fbm(q * 0.9 - t * 0.06) * 1.6);
  vec3 col = mix(vec3(0.85, 0.08, 0.2), vec3(0.05, 0.6, 0.55), smoothstep(0.3, 0.7, w1));
  col = mix(col, vec3(0.12, 0.2, 0.85), smoothstep(0.45, 0.75, w2) * 0.7);
  col = mix(col, vec3(1.0, 0.75, 0.2), smoothstep(0.62, 0.8, w1 * w2 * 1.8) * 0.6);
  col *= 0.55 + 0.45 * smoothstep(0.7, 0.1, length(c));
  float leak = exp(-length((c - vec2(0.6 * sin(t * 0.35), 0.3)) * vec2(1.0, 0.6)) * 3.0);
  col += vec3(1.0, 0.55, 0.25) * leak * 0.45;
  col += (hash(gl_FragCoord.xy + floor(t * 24.0)) - 0.5) * 0.06;
  o = vec4(col, 1.0);
