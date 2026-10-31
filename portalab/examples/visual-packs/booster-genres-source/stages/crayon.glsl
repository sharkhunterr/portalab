// Crayonné — the booster stage: an animator's sheet of paper on a light table, its blue grid, pencil sketches
  // boiling as drawn lines do, patches of colour bleeding in and out (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(1.0, 0.97, 0.92, 1.0);
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    vec2 p = vec2((hash(vec2(fk, 3.0)) - 0.5) * asp, hash(vec2(fk, 4.0)) - 0.5) + 0.05 * vec2(sin(t * 0.4 + fk), cos(t * 0.3 + fk));
    vec3 col = mod(fk, 3.0) < 1.0 ? vec3(1.0, 0.62, 0.11) : mod(fk, 3.0) < 2.0 ? vec3(0.18, 0.88, 0.7) : vec3(0.48, 0.36, 1.0);
    o = over(o, col, smoothstep(0.22, 0.12, length(c - p) + 0.03 * fbm(c * 8.0 + t * 0.2)) * (0.18 + 0.1 * sin(t + fk)));
  }
  vec2 grid = abs(fract(c * 12.0) - 0.5);
  o = over(o, vec3(0.75, 0.84, 1.0), smoothstep(0.03, 0.0, min(grid.x, grid.y)) * 0.5);
  float frame = floor(t * 8.0);
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 p = vec2((fk - 1.5) * asp * 0.28, 0.12 * sin(fk * 2.0));
    float r = 0.12 + 0.04 * fk + 0.004 * (hash(vec2(fk, frame)) - 0.5);
    float wob = 0.006 * sin(atan(c.y - p.y, c.x - p.x) * 6.0 + frame + fk);
    o = over(o, vec3(0.23, 0.42, 1.0), smoothstep(0.004, 0.0, abs(length(c - p) - r - wob)) * 0.7);
  }
  o.rgb *= 0.97 + 0.03 * hash(c * 300.0);
