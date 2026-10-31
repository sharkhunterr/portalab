// Insomnie — the booster stage: a city at night in the rain, neon signs buzzing red and blue, lit windows,
  // the wet street mirroring them, rain streaking down (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.02, 0.025, 0.05), vec3(0.07, 0.06, 0.12), smoothstep(-0.2, 0.5, c.y)), 1.0);
  float street = -0.28;
  vec2 q = c.y < street ? vec2(c.x, 2.0 * street - c.y + 0.01 * sin(c.x * 60.0 + t * 3.0)) : c;
  float mirror = c.y < street ? 0.45 : 1.0;
  // towers and their windows
  float col = floor((q.x + asp) * 9.0);
  float h = 0.05 + 0.4 * hash(vec2(col, 1.0));
  float tower = step(q.y, h) * step(street, q.y);
  o = over(o, vec3(0.015, 0.015, 0.025), tower * mirror + (1.0 - mirror) * 0.0);
  vec2 win = fract(vec2((q.x + asp) * 9.0 * 5.0, q.y * 45.0));
  float lit = step(0.72, hash(floor(vec2((q.x + asp) * 45.0, q.y * 45.0)))) * step(0.25, win.x) * step(win.x, 0.75) * step(0.3, win.y) * step(win.y, 0.7);
  o = over(o, vec3(1.0, 0.82, 0.5), tower * lit * 0.6 * mirror);
  // neon signs, buzzing
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 np = vec2((hash(vec2(fk, 4.0)) - 0.5) * asp * 0.9, -0.05 + 0.3 * hash(vec2(fk, 5.0)));
    vec3 nc = mod(fk, 2.0) < 1.0 ? vec3(1.0, 0.15, 0.25) : vec3(0.2, 0.45, 1.0);
    float on = step(0.08, hash(vec2(fk, floor(t * 8.0)))) ;
    vec2 d = (q - np) * vec2(1.0, 3.0);
    o = over(o, nc, (smoothstep(0.06, 0.05, max(abs(d.x), abs(d.y) * 0.5)) * 0.9 + exp(-length(d) * 6.0) * 0.5) * on * mirror);
  }
  // the street's sheen
  o = over(o, vec3(0.3, 0.32, 0.4), step(c.y, street) * 0.08);
  // rain
  for (int k = 0; k < 60; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 9.0));
    float y = 0.6 - fract(t * (1.2 + h1) + h1) * 1.3;
    float x = (hash(vec2(fk, 10.0)) - 0.5) * asp * 1.1 - (y - 0.6) * 0.15;
    vec2 r = c - vec2(x, y);
    o = over(o, vec3(0.7, 0.75, 0.9), smoothstep(0.0025, 0.0, abs(r.x + r.y * 0.15)) * step(-0.05, r.y) * step(r.y, 0.0) * 0.5);
  }
