// Portalab — ambient/christmasnight: the « christmasnight » ambience (spec 028, B2)
float fir(vec2 p, float x0, float h, float w, out float snow) {
  // a fir tree: four jagged tiers, snow along their lower edges, a little trunk
  float y = p.y / h;
  float tier = fract(y * 4.0 + 0.2);
  float half_ = w * (1.0 - y) * (0.5 + 0.55 * (1.0 - tier)) * (0.92 + 0.16 * noise(vec2(p.y * 160.0, x0 * 9.0)));
  float body = step(0.0, y) * step(y, 1.0) * smoothstep(0.002, 0.0, abs(p.x - x0) - half_);
  snow = body * smoothstep(0.82, 0.95, 1.0 - tier) * step(0.06, y);
  float trunk = step(-0.02, p.y) * step(p.y, 0.0) * step(abs(p.x - x0), w * 0.12);
  return clamp(body + trunk, 0.0, 1.0);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.03, 0.06, 0.16), vec3(0.08, 0.1, 0.25), uv.y), smoothstep(0.15, 1.0, uv.y) * 0.5);
  vec2 sg = p * 120.0;
  float sh = hash(floor(sg));
  float star = step(0.993, sh) * smoothstep(0.45, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(t * 2.0 + sh * 70.0));
  vec2 sg2 = p * 260.0;
  star += step(0.995, hash(floor(sg2) + 3.0)) * smoothstep(0.5, 0.0, length(fract(sg2) - 0.5)) * 0.5;
  o = over(o, vec3(1.0, 0.97, 0.88), star * smoothstep(0.3, 0.6, uv.y));
  // a shooting star, now and then
  float sslot = floor(t / 9.0);
  float sph = mod(t, 9.0);
  vec2 s0 = vec2(aspect * (0.2 + 0.6 * hash(vec2(sslot, 1.0))), 0.75 + 0.2 * hash(vec2(sslot, 2.0)));
  vec2 sdir = normalize(vec2(-0.8, -0.35));
  vec2 head = s0 + sdir * sph * 0.5;
  vec2 rel = p - head;
  float along = dot(rel, -sdir);
  float across = abs(dot(rel, vec2(-sdir.y, sdir.x)));
  float trail = smoothstep(0.0015, 0.0, across) * step(0.0, along) * exp(-along * 14.0) * step(sph, 0.7);
  o = over(o, vec3(0.9, 0.95, 1.0), trail * (1.0 - sph / 0.7) * step(0.3, hash(vec2(sslot, 3.0))));
  // the moon: a soft glow, its seas and craters
  vec2 moon = vec2(aspect * 0.78, 0.76);
  vec2 dmv = p - moon;
  float dm = length(dmv);
  o = over(o, vec3(0.95, 0.95, 0.85), exp(-dm * 9.0) * 0.32);
  float seas = fbm(dmv * 22.0 + 3.0);
  float crater = smoothstep(0.75, 0.9, noise(dmv * 120.0));
  vec3 moonc = vec3(1.0, 0.98, 0.9) * (0.9 - 0.18 * smoothstep(0.45, 0.7, seas) - 0.08 * crater) * (1.0 - 0.12 * smoothstep(0.03, 0.07, length(dmv + vec2(0.02, -0.015))));
  o = over(o, moonc, smoothstep(0.072, 0.066, dm));
  // a sleigh crossing the moon, now and then: a silhouette with its reindeer
  float pass = mod(t, 22.0) / 6.0;
  float sx = moon.x - 0.45 + pass * 0.9;
  vec2 q = p - vec2(sx, moon.y - 0.01 + sin(pass * 3.0) * 0.01);
  float sleigh = smoothstep(1.0, 0.8, length(q / vec2(0.03, 0.009)));
  sleigh += smoothstep(0.0025, 0.0, abs(q.y + 0.011)) * step(abs(q.x), 0.032);
  for (int i = 1; i < 5; i++) {
    float fi = float(i);
    vec2 r = q - vec2(0.04 + fi * 0.028, 0.012 + sin(t * 8.0 + fi) * 0.003);
    sleigh += smoothstep(1.0, 0.75, length(r / vec2(0.011, 0.0055)));
    sleigh += smoothstep(1.0, 0.7, length((r - vec2(0.011, 0.006)) / vec2(0.004, 0.0035)));
    sleigh += smoothstep(0.0012, 0.0, abs(r.x - 0.012)) * step(abs(r.y - 0.012), 0.004);
    sleigh += smoothstep(0.001, 0.0, abs(abs(r.x) - 0.006)) * step(abs(r.y + 0.008), 0.004);
  }
  o = over(o, vec3(0.02, 0.03, 0.06), clamp(sleigh, 0.0, 1.0) * step(pass, 1.0));
  // far hills with a forest of small firs, blue in the night
  float far = 0.2 + 0.04 * sin(p.x * 1.3 + 2.0) + 0.02 * noise(vec2(p.x * 4.0, 1.0));
  float fx = fract(p.x * 22.0);
  float fh = 0.025 + 0.02 * hash(vec2(floor(p.x * 22.0), 5.0));
  float farTrees = step(p.y, far + fh * (1.0 - abs(fx - 0.5) * 2.0) * step(0.3, hash(vec2(floor(p.x * 22.0), 6.0))));
  o = over(o, vec3(0.07, 0.1, 0.18), max(step(p.y, far), farTrees) * 0.95);
  o = over(o, vec3(0.45, 0.52, 0.68), step(p.y, far) * smoothstep(far - 0.03, far, p.y) * 0.5);
  float hill = 0.12 + 0.04 * sin(p.x * 2.0) + 0.02 * sin(p.x * 5.3 + 1.0);
  float ground = step(p.y, hill);
  // the near firs, leaving room for the cabin
  float cabinX = aspect * 0.64;
  float trees = 0.0;
  float snowEdge = 0.0;
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float x0 = (fi + 0.3 * hash(vec2(fi, 1.0))) / 9.0 * aspect;
    float keep = step(0.16, abs(x0 - cabinX)) * step(0.1, abs(x0 - aspect * 0.2));
    float h = 0.16 + 0.12 * hash(vec2(fi, 2.0));
    float sn;
    float tr = fir(vec2(p.x, p.y - hill + 0.01), x0, h, 0.045 + 0.02 * hash(vec2(fi, 3.0)), sn) * keep;
    trees = max(trees, tr);
    snowEdge = max(snowEdge, sn * keep);
  }
  o = over(o, vec3(0.02, 0.06, 0.05), trees);
  o = over(o, vec3(0.7, 0.78, 0.9), snowEdge * 0.8);
  // the decorated tree: a bigger fir hung with twinkling lights and a star on top
  float tx = aspect * 0.2;
  float tbase = 0.12 + 0.04 * sin(tx * 2.0) + 0.02 * sin(tx * 5.3 + 1.0);
  float dsn;
  float big = fir(vec2(p.x, p.y - tbase + 0.01), tx, 0.3, 0.085, dsn);
  o = over(o, vec3(0.02, 0.08, 0.05), big);
  o = over(o, vec3(0.75, 0.82, 0.95), dsn * 0.75);
  vec2 lg = (p - vec2(tx, tbase)) * 70.0;
  vec2 lc = floor(lg);
  float lh = hash(lc + 11.0);
  float bulb = smoothstep(0.32, 0.1, length(fract(lg) - 0.5)) * step(0.72, lh) * big;
  float twk = 0.5 + 0.5 * sin(t * (2.0 + lh * 3.0) + lh * 40.0);
  vec3 bc = 0.55 + 0.45 * cos(6.2831 * (lh * 3.0 + vec3(0.0, 0.33, 0.67)));
  o = over(o, mix(bc, vec3(1.0, 0.9, 0.6), 0.3), bulb * (0.4 + 0.6 * twk));
  vec2 st = p - vec2(tx, tbase + 0.3);
  float sa = atan(st.y, st.x);
  float starShape = smoothstep(0.012, 0.009, length(st) / (0.6 + 0.4 * cos(sa * 5.0 - 1.57)));
  o = over(o, vec3(1.0, 0.85, 0.35), exp(-length(st) * 40.0) * (0.5 + 0.2 * sin(t * 3.0)));
  o = over(o, vec3(1.0, 0.92, 0.55), starShape);
  // snow ground: blue shadows in the drifts
  float drift = fbm(vec2(p.x * 3.0, p.y * 12.0));
  o = over(o, mix(vec3(0.55, 0.62, 0.8), vec3(0.82, 0.88, 0.98), drift), ground * 0.92);
  // the cabin: log walls, a snowed roof, a warm window, a chimney smoking
  float cb = 0.12 + 0.04 * sin(cabinX * 2.0) + 0.02 * sin(cabinX * 5.3 + 1.0) - 0.01;
  vec2 cq = p - vec2(cabinX, cb);
  float walls = step(abs(cq.x), 0.08) * step(0.0, cq.y) * step(cq.y, 0.075);
  float logs = 0.75 + 0.25 * smoothstep(0.2, 0.5, abs(fract(cq.y * 110.0) - 0.5));
  float roof = step(cq.y, 0.075 + 0.06 - abs(cq.x) * 0.62) * step(0.07, cq.y) * step(abs(cq.x), 0.1);
  float roofSnow = roof * step(0.075 + 0.06 - abs(cq.x) * 0.62 - 0.012 - 0.004 * noise(vec2(cq.x * 90.0, 2.0)), cq.y);
  vec2 chim = cq - vec2(0.045, 0.12);
  float chimney = step(abs(chim.x), 0.008) * step(-0.04, chim.y) * step(chim.y, 0.0);
  o = over(o, vec3(0.13, 0.07, 0.04) * logs, walls);
  o = over(o, vec3(0.06, 0.035, 0.03), max(roof, chimney));
  o = over(o, vec3(0.88, 0.92, 1.0), roofSnow);
  float flick = 0.85 + 0.15 * noise(vec2(t * 5.0, 3.0));
  vec2 win = cq - vec2(-0.03, 0.038);
  float pane = step(abs(win.x), 0.017) * step(abs(win.y), 0.014);
  float mullion = step(abs(win.x), 0.0015) + step(abs(win.y), 0.0015);
  o = over(o, vec3(1.0, 0.72, 0.32) * flick, pane * (1.0 - clamp(mullion, 0.0, 1.0)));
  vec2 door = cq - vec2(0.035, 0.022);
  o = over(o, vec3(0.07, 0.04, 0.02), step(abs(door.x), 0.013) * step(abs(door.y), 0.022));
  o = over(o, vec3(1.0, 0.7, 0.35), exp(-length(win * vec2(1.0, 1.6)) * 30.0) * 0.35 * flick * (1.0 - pane));
  vec2 spill = (p - vec2(cabinX - 0.03, cb - 0.02)) / vec2(0.09, 0.025);
  o = over(o, vec3(1.0, 0.75, 0.4), exp(-dot(spill, spill)) * 0.35 * flick * ground);
  vec2 sm = chim - vec2(0.0, 0.005);
  float rise = max(sm.y, 0.0);
  float plume = fbm(vec2(sm.x * 30.0 - rise * 18.0, rise * 9.0 - t * 0.5));
  float width = 0.008 + rise * 0.35;
  float smoke = smoothstep(width, 0.0, abs(sm.x - rise * rise * 2.5 - (plume - 0.5) * 0.03)) * step(0.0, sm.y) * smoothstep(0.22, 0.0, rise);
  o = over(o, vec3(0.62, 0.64, 0.72), smoke * smoothstep(0.25, 0.65, plume) * 0.7);
  // snow on the hills sparkling
  float sparkle = step(0.997, hash(floor(p * 200.0) + floor(t * 3.0))) * ground;
  o = over(o, vec3(1.0), sparkle);
  gl_FragColor = o;
}