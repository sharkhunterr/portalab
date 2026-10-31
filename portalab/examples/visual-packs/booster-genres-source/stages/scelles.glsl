// Scellés — the booster stage: a street at night cordoned off, police lights turning red and blue over the wet
  // asphalt, the tape across the top, a chalk outline glimpsed on the ground (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.05, 0.06, 0.09), vec3(0.11, 0.11, 0.13), smoothstep(0.2, -0.5, c.y)), 1.0);
  float ph = fract(t * 0.8);
  vec2 lr = vec2(-asp * 0.35, 0.25), lb = vec2(asp * 0.35, 0.25);
  o = over(o, vec3(0.9, 0.1, 0.08), exp(-length(c - lr) * 2.5) * 0.55 * step(ph, 0.5));
  o = over(o, vec3(0.2, 0.42, 1.0), exp(-length(c - lb) * 2.5) * 0.55 * step(0.5, ph));
  // wet asphalt: the lights streaked in it
  float wet = smoothstep(0.0, -0.4, c.y) * (0.6 + 0.4 * fbm(c * vec2(3.0, 18.0)));
  o = over(o, vec3(0.9, 0.1, 0.08), wet * exp(-abs(c.x - lr.x) * 6.0) * 0.35 * step(ph, 0.5));
  o = over(o, vec3(0.2, 0.42, 1.0), wet * exp(-abs(c.x - lb.x) * 6.0) * 0.35 * step(0.5, ph));
  // the chalk outline, faint
  vec2 b = (c - vec2(0.15, -0.3)) * vec2(1.0, 2.2);
  float body = abs(length(b * vec2(1.0, 0.55)) - 0.12) + 0.0;
  o = over(o, vec3(0.9, 0.9, 0.88), smoothstep(0.006, 0.0, body) * 0.35);
  // the tape across the top, its chevrons, swaying a little
  float ty = 0.38 + 0.02 * sin(c.x * 3.0 + t);
  float band = step(abs(c.y - ty), 0.035);
  float chev = step(0.5, fract((c.x + (c.y - ty) * 0.6) * 9.0 + t * 0.3));
  o = over(o, mix(vec3(0.96, 0.77, 0.0), vec3(0.11, 0.1, 0.09), chev * 0.9), band);
  o.rgb *= smoothstep(1.3, 0.4, length(c));
