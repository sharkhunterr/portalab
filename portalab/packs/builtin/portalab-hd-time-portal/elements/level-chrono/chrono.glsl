// Portalab — level_badge/chrono: the « chrono » effect (spec 028, B2)
  // once (a notification): the portal opens, then what it brings materialises; as it leaves, it
  // dematerialises first, then the portal closes (its letters follow in CSS: fx-teleport-in / -out)
  float leaving = u_close < 0.0 ? 0.0 : u_close;
  float k = smoothstep(0.0, 0.8, u_age) * (1.0 - smoothstep(0.6, 1.3, leaving));
  float shown = smoothstep(0.8, 1.4, u_age) * (1.0 - smoothstep(0.0, 0.6, leaving));
  float flash = exp(-abs(u_age - 1.0) * 7.0) + (u_close < 0.0 ? 0.0 : exp(-abs(u_close - 0.4) * 7.0));
  if (u_cycle > 0.5) {
    // a teleporter, over and over: the portal opens, the badge materialises, stays, dematerialises, the
    // portal closes — a pause — and again (its letters follow the same cycle in CSS: fx-teleport, 9 s)
    float tc = mod(u_age, 9.0);
    k = smoothstep(0.0, 0.8, tc) * (1.0 - smoothstep(7.1, 7.9, tc));
    shown = smoothstep(0.8, 1.4, tc) * (1.0 - smoothstep(6.5, 7.1, tc));
    flash = exp(-abs(tc - 1.1) * 7.0) + exp(-abs(tc - 6.8) * 7.0);
  }
  float rot = (1.0 - k) * 2.6 + sin(t * 0.6) * 0.05;
  vec2 tp = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * (p - vec2(0.0, -0.1));
  float size = (max(ax, 1.0) * 0.9 + 0.75) * max(k, 0.001);
  float tri = sdTri(tp, size);
  float crackle = noise(vec2(atan(tp.y, tp.x) * 6.0, floor(t * 12.0))) * 0.08;
  vec3 seen = vortex(tp / max(size, 0.01) * 1.4, t);
  o = over(o, seen, smoothstep(0.02, -0.04, tri) * 0.92 * k);
  o = over(o, vec3(0.4, 0.75, 1.0), exp(-abs(tri - crackle) * 14.0) * k);
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-abs(tri) * 45.0) * k);
  o = over(o, vec3(0.8, 0.9, 1.0), flash * exp(-length(p) * 1.5) * 0.7);
  for (int i = 0; i < 8; i++) {
    float fi = float(i);
    float life = fract(t * (0.4 + 0.3 * hash(vec2(fi, 91.0))) + hash(vec2(fi, 92.0)));
    float ang = hash(vec2(fi, 93.0)) * 6.2832 + life * 2.0;
    vec2 sp = vec2(cos(ang), sin(ang)) * size * (1.3 - life * 1.2);
    o = over(o, vec3(1.0, 0.85, 0.5), smoothstep(0.06, 0.0, length(tp - sp)) * (1.0 - life) * k);
  }
  vec3 body = vortex(p * 0.8, t) * 0.75;
  body += vec3(0.5, 0.8, 1.0) * smoothstep(-0.15, 0.0, d) * 0.6;
  o = over(o, body, smoothstep(0.03, -0.03, d) * shown);
