// Impact — the booster stage: a black stage with a violet glow at its heart, pink and white speed lines
  // streaking across it on a slant, pink halftone dots swelling into two corners, four-pointed stars twinkling
  // and now and then a crosshair glint (a stage: gl_FragCoord, u_res, t; into o).
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.014, 0.006, 0.03, 1.0);
  o = over(o, vec3(0.32, 0.04, 0.42), exp(-length(c * vec2(0.8, 1.2)) * 2.6) * 0.45);
  // the speed lines, on a slant: lanes across the slant, a streak sliding along each one, its tail fading
  float slant = 0.6;
  vec2 q = vec2(c.x * cos(slant) + c.y * sin(slant), -c.x * sin(slant) + c.y * cos(slant));
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float lanes = 26.0 + fk * 22.0;
    float ly = q.y * lanes + fk * 0.37;
    float id = floor(ly);
    float across = fract(ly) - 0.5;
    float h1 = hash(vec2(id, 1.0 + fk));
    float h2 = hash(vec2(id, 2.0 + fk));
    float h3 = hash(vec2(id, 3.0 + fk));
    float speed = 0.5 + 1.4 * h2;
    float len = 0.25 + 0.6 * h3;
    float head = fract(t * speed * 0.3 + h1 * 7.0) * (asp + 2.0) - (asp * 0.5 + 1.0);
    float behind = head - q.x;
    float tail = step(0.0, behind) * step(behind, len) * (1.0 - behind / len);
    float thin = smoothstep(0.1 + 0.12 * h2, 0.0, abs(across));
    vec3 col = mix(vec3(1.0, 0.96, 0.98), vec3(1.0, 0.16, 0.52), step(0.55, h2));
    o = over(o, col, step(0.45, h1) * tail * thin * (0.75 - fk * 0.3));
  }
  // halftone dots, on a diagonal grid, swelling into the top-left and bottom-right corners
  vec2 g = gl_FragCoord.xy / (u_res.y * 0.021);
  g = vec2(g.x + g.y, g.y - g.x) * 0.7071;
  vec2 cell = fract(g) - 0.5;
  float near = max(smoothstep(0.62, 0.0, length((uv - vec2(0.0, 1.0)) * vec2(asp, 1.0) * 0.8)),
                   smoothstep(0.55, 0.0, length((uv - vec2(1.0, 0.0)) * vec2(asp, 1.0) * 0.8)));
  float radius = 0.48 * near;
  o = over(o, vec3(1.0, 0.1, 0.5), smoothstep(radius, radius - 0.08, length(cell)) * step(0.04, near) * 0.85);
  // four-pointed stars twinkling
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 7.0)) - 0.5) * asp * 0.96, (hash(vec2(fk, 8.0)) - 0.5) * 0.92);
    vec2 dd = c - sp;
    float size = 0.012 + 0.028 * hash(vec2(fk, 10.0));
    float twinkle = pow(0.5 + 0.5 * sin(t * (1.2 + 2.2 * hash(vec2(fk, 9.0))) + fk * 3.1), 5.0);
    float rays = exp(-abs(dd.x) * 900.0) * exp(-abs(dd.y) / size * 2.2) + exp(-abs(dd.y) * 900.0) * exp(-abs(dd.x) / size * 2.2);
    float core = exp(-length(dd) * 260.0);
    vec3 col = mix(vec3(1.0, 0.97, 1.0), vec3(1.0, 0.35, 0.65), step(0.6, hash(vec2(fk, 11.0))));
    o = over(o, col, clamp(rays + core, 0.0, 1.0) * twinkle);
  }
  // now and then, a crosshair glint lighting up somewhere and going out
  float cycle = floor(t / 4.5);
  float phase = fract(t / 4.5);
  vec2 cp = vec2((hash(vec2(cycle, 20.0)) - 0.5) * asp * 0.8, (hash(vec2(cycle, 21.0)) - 0.5) * 0.7);
  float rr = length(c - cp);
  float lit = smoothstep(0.0, 0.08, phase) * smoothstep(0.42, 0.22, phase);
  float ring = smoothstep(0.004, 0.0, abs(rr - 0.055));
  vec2 cd = c - cp;
  float hair = (exp(-abs(cd.x) * 700.0) * step(abs(cd.y), 0.09) + exp(-abs(cd.y) * 700.0) * step(abs(cd.x), 0.09)) * step(0.025, rr);
  o = over(o, vec3(1.0, 0.3, 0.6), clamp(ring + hair * 0.8, 0.0, 1.0) * lit);
  o = over(o, vec3(1.0), exp(-rr * 90.0) * lit);
