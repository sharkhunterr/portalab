  // Marée — the booster stage in the deep: a few shafts of light from the far surface, motes drifting, the
  // water sinking into black the farther it goes (a stage: gl_FragCoord, u_res, t; the colour into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec3 deep = mix(vec3(0.0, 0.02, 0.05), vec3(0.01, 0.17, 0.25), smoothstep(-0.6, 0.65, c.y));
  o = over(o, deep, 1.0);
  float shafts = 0.0;
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float x = c.x + 0.25 * c.y + 0.4 * sin(t * 0.13 + fk * 1.7);
    shafts += smoothstep(0.08, 0.0, abs(fract(x * 1.3 + fk * 0.31) - 0.5)) * smoothstep(-0.5, 0.65, c.y)
      * (0.6 + 0.4 * sin(t * 0.4 + fk * 2.3));
  }
  o = over(o, vec3(0.45, 0.85, 0.95), 0.18 * shafts);
  // motes: one in a few cells, each placed and sized at random in it, glimmering
  vec2 g = c * 30.0 + vec2(0.0, t * 0.2);
  vec2 cell = floor(g);
  vec2 jitter = vec2(hash(cell + 3.1), hash(cell + 7.7)) - 0.5;
  float size = 0.1 + 0.15 * hash(cell + 1.3);
  float mote = step(0.965, hash(cell)) * smoothstep(size, 0.0, length(fract(g) - 0.5 - jitter * 0.6));
  o = over(o, vec3(0.7, 0.95, 1.0), (0.25 + 0.3 * sin(t * 1.5 + hash(cell) * 60.0)) * mote);
  // the deep: the farther from the middle, the darker, down to black at the edges
  float far = length(c * vec2(0.62, 0.95));
  o.rgb = mix(o.rgb, vec3(0.0, 0.006, 0.02), smoothstep(0.15, 0.75, far) * 0.9);
  o.rgb *= mix(0.15, 1.0, smoothstep(0.9, 0.15, far));
