  // Nordlys — a level-up over the whole stage. Portalab's frame gives: gl_FragCoord, u_res, u_age (seconds
  // since it started), hash(), noise(), fbm(), over(); the scene writes its colour into o.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.8, 5.6, tl);
  // the polar night
  vec3 night = mix(vec3(0.01, 0.02, 0.06), vec3(0.02, 0.06, 0.12), smoothstep(-0.5, 0.5, c.y));
  o = over(o, night, 0.82 * fade);
  vec2 sg = c * 42.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(0.9, 0.95, 1.0), step(0.985, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.5 + 0.5 * sin(tl * 3.0 + sh * 40.0)) * fade);
  // the curtains: three ribbons of light coming down from the top, rippling sideways
  float down = smoothstep(0.2, 2.2, tl);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float x = c.x * (1.1 + fk * 0.3) + fk * 1.7;
    float wave = 0.18 * sin(x * 2.3 + tl * (0.6 + fk * 0.2)) + 0.12 * (fbm(vec2(x * 1.5, tl * 0.25 + fk)) - 0.5);
    float edge = 0.38 - fk * 0.12 + wave - (1.0 - down) * 0.9;
    float below = c.y - edge;
    float rays = 0.55 + 0.45 * fbm(vec2(x * 9.0, tl * 0.6 + fk * 3.0));
    float curtain = smoothstep(-0.02, 0.03, below) * exp(-max(below, 0.0) * (3.5 + fk)) * rays;
    vec3 green = vec3(0.2, 1.0, 0.55);
    vec3 top = mix(vec3(0.55, 0.3, 1.0), vec3(1.0, 0.35, 0.6), fk * 0.5);
    vec3 col = mix(green, top, smoothstep(0.02, 0.35, below));
    o = over(o, col, curtain * (0.55 - fk * 0.12) * fade);
  }
  // the ring of light your level appears in
  float open = smoothstep(1.9, 2.8, tl);
  float r = length(c);
  float ring = exp(-abs(r - 0.18 - 0.14 * open) * 55.0) * open;
  o = over(o, vec3(0.6, 1.0, 0.85), ring * 0.9 * fade);
  o = over(o, vec3(0.75, 1.0, 0.9), exp(-r * 6.0) * open * 0.35 * fade);
  o = over(o, vec3(1.0), exp(-abs(tl - 2.2) * 10.0) * 0.35 * fade);
  // frost crystals drifting down and glittering
  for (int i = 0; i < 40; i++) {
    float fi = float(i);
    vec2 pos = vec2((hash(vec2(fi, 11.0)) - 0.5) * aspect, 0.55 - fract(hash(vec2(fi, 12.0)) + tl * (0.03 + 0.04 * hash(vec2(fi, 13.0)))) * 1.1);
    float glint = 0.5 + 0.5 * sin(tl * 6.0 + fi * 2.3);
    vec2 g = abs(c - pos);
    float star = exp(-length(g) * 220.0) + (exp(-g.x * 400.0) * exp(-g.y * 60.0) + exp(-g.y * 400.0) * exp(-g.x * 60.0)) * 0.4;
    o = over(o, vec3(0.85, 1.0, 0.95), star * glint * open * fade);
  }
