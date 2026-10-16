// Portalab — level_up/timeportal: the « timeportal » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float k = smoothstep(0.9, 1.6, tl) * smoothstep(6.6, 5.6, tl);
  float rot = (1.0 - k) * 3.0 + u_age * 0.05;
  vec2 tp = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * c;
  float size = 0.42 * max(k, 0.0) + 0.0001;
  float tri = sdTri(tp, size);
  o = over(o, vortex(tp / max(size, 0.01) * 1.3, u_age), smoothstep(0.004, -0.01, tri) * 0.95 * k);
  float drawn = smoothstep(0.0, 1.0, tl);
  vec2 q = tp;
  float side = 0.0;
  for (int i = 0; i < 3; i++) {
    float a = float(i) * 2.0944;
    vec2 v = mat2(cos(a), -sin(a), sin(a), cos(a)) * q;
    float along = (v.x / 0.36 + 0.5);
    float reveal = step(along, clamp(drawn * 3.0 - float(i), 0.0, 1.0));
    side += exp(-abs(v.y + 0.42 * 0.577) * 220.0) * step(0.0, along) * step(along, 1.0) * reveal * (1.0 - k);
  }
  o = over(o, vec3(0.6, 0.85, 1.0), clamp(side, 0.0, 1.0));
  float crackle = noise(vec2(atan(tp.y, tp.x) * 8.0, floor(u_age * 14.0))) * 0.015;
  o = over(o, vec3(0.4, 0.75, 1.0), exp(-abs(tri - crackle) * 60.0) * k);
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-abs(tri) * 200.0) * k);
  float flash = exp(-abs(tl - 1.6) * 8.0) + exp(-abs(tl - 6.4) * 8.0);
  o = over(o, vec3(0.85, 0.92, 1.0), flash * exp(-length(c) * 1.5) * 0.8);
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    float life = fract(u_age * (0.25 + 0.25 * hash(vec2(fi, 94.0))) + hash(vec2(fi, 95.0)));
    float ang = hash(vec2(fi, 96.0)) * 6.2832 + life * 3.0;
    vec2 sp = vec2(cos(ang), sin(ang)) * (1.0 - life) * 0.9;
    o = over(o, mix(vec3(1.0, 0.85, 0.5), vec3(0.6, 0.85, 1.0), hash(vec2(fi, 97.0))), smoothstep(0.008, 0.0, length(c - sp)) * life * k);
  }
