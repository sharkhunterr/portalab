// Gold Rush — the booster stage inside a carriage of the western train, looking out of its window at sunset: the
  // desert rolling by in depth (far mesas barely moving, nearer buttes, the prairie with its saguaros streaming,
  // telegraph poles flashing past, their wires rising and falling), the locomotive's smoke drifting across the
  // glass, dust and the lamps' reflection on it; inside, mahogany panels, a velvet curtain and its valance, a brass
  // luggage rack where a suitcase jolts, oil lamps flickering — and the carriage rocking on the rails' joints.
  float clack = exp(-fract(t / 0.55) * 16.0) * 0.0035 + exp(-fract(t / 0.55 + 0.18) * 16.0) * 0.002;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y + vec2(0.0015 * sin(t * 1.7), 0.0022 * sin(t * 5.3) + clack);
  float aa = 1.5 / u_res.y;
  // --- the land outside, its horizon a little below the middle
  float hz = -0.03;
  vec2 v = c - vec2(0.0, hz);
  vec3 sky = mix(vec3(1.0, 0.7, 0.36), vec3(0.92, 0.4, 0.3), smoothstep(0.0, 0.2, v.y));
  sky = mix(sky, vec3(0.3, 0.16, 0.34), smoothstep(0.18, 0.42, v.y));
  o = over(o, sky, 1.0);
  vec2 sp = v - vec2(0.2, 0.05);
  o = over(o, vec3(1.0, 0.95, 0.78), smoothstep(0.045, 0.04, length(sp)));
  o = over(o, vec3(1.0, 0.68, 0.32), exp(-length(sp) * 4.0) * 0.55);
  vec2 cq = vec2(c.x * 1.4 + t * 0.008, c.y * 5.0);
  float cw = fbm(cq + vec2(fbm(cq * 1.3 + t * 0.01), 0.0) * 1.2);
  o = over(o, mix(vec3(1.0, 0.62, 0.38), vec3(0.45, 0.22, 0.34), smoothstep(0.55, 0.85, cw)), smoothstep(0.5, 0.72, cw) * smoothstep(0.08, 0.2, v.y) * 0.85);
  // far mesas, hardly moving; nearer buttes, a little faster, their strata
  float s1 = c.x + t * 0.006;
  float m1 = 0.012 + 0.075 * smoothstep(0.4, 0.56, noise(vec2(s1 * 2.4 + 3.0, 1.0))) + 0.01 * fbm(vec2(s1 * 30.0, 2.0));
  o = over(o, vec3(0.76, 0.43, 0.37), smoothstep(aa, -aa, v.y - m1));
  float s2 = c.x + t * 0.03;
  float m2 = 0.004 + 0.06 * smoothstep(0.55, 0.7, noise(vec2(s2 * 3.2 + 7.0, 3.0))) + 0.012 * fbm(vec2(s2 * 24.0, 4.0));
  o = over(o, vec3(0.5, 0.22, 0.16) * (0.85 + 0.15 * sin((v.y + 0.008 * noise(vec2(s2 * 20.0, 5.0))) * 180.0)), smoothstep(aa, -aa, v.y - m2));
  o = over(o, vec3(1.0, 0.66, 0.4), exp(-abs(v.y) * 30.0) * 0.3);
  // the prairie, streaming faster the nearer it is
  float zg = 0.05 / max(-v.y, 0.0005);
  float gx = c.x * zg + t * 0.22;
  vec3 ground = vec3(0.56, 0.36, 0.2) * (0.7 + 0.5 * fbm(vec2(gx * 6.0, zg * 8.0)));
  ground = mix(ground, vec3(0.3, 0.3, 0.12), smoothstep(0.62, 0.78, noise(vec2(gx * 14.0, zg * 20.0))) * 0.6);
  ground = mix(ground, vec3(1.0, 0.66, 0.4), smoothstep(0.6, 4.0, zg) * 0.6);
  o = over(o, ground, smoothstep(aa, -aa, v.y));
  // saguaros in two rows, the nearer row faster
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float zc = 0.6 - fk * 0.3;
    float wx = c.x * zc + t * 0.22;
    float cell = floor(wx / 0.25);
    float cu = (fract(wx / 0.25) - 0.5) * 0.25 / zc;
    float keep = step(0.45, hash(vec2(cell, fk + 2.0)));
    float hgt = (0.035 + 0.02 * hash(vec2(cell, fk))) / zc;
    float yb = -0.05 / zc;
    float yy = v.y - yb;
    float trunk = smoothstep(0.004 / zc, 0.0025 / zc, abs(cu)) * step(0.0, yy) * step(yy, hgt);
    float armY = hgt * (0.45 + 0.2 * hash(vec2(cell, fk + 5.0)));
    float armL = step(0.0, -cu) * smoothstep(0.003 / zc, 0.002 / zc, abs(yy - armY - min(abs(cu) - 0.008 / zc, 0.0) * 0.0)) * step(abs(cu), 0.01 / zc);
    float armL2 = smoothstep(0.003 / zc, 0.002 / zc, abs(cu + 0.01 / zc)) * step(armY, yy) * step(yy, armY + hgt * 0.3);
    float armR = step(0.0, cu) * smoothstep(0.003 / zc, 0.002 / zc, abs(yy - armY * 1.2)) * step(abs(cu), 0.009 / zc);
    float armR2 = smoothstep(0.003 / zc, 0.002 / zc, abs(cu - 0.009 / zc)) * step(armY * 1.2, yy) * step(yy, armY * 1.2 + hgt * 0.22);
    o = over(o, vec3(0.2, 0.2, 0.08) * (1.0 + fk * 0.3), clamp(trunk + armL + armL2 + armR + armR2, 0.0, 1.0) * keep);
  }
  // telegraph poles flashing past, their wires sagging between them
  float spacing = 0.75;
  float ph = c.x + t * 0.95;
  float pu = fract(ph / spacing);
  float px = (pu - 0.5) * spacing;
  float pole = smoothstep(0.012, 0.005, abs(px)) * step(c.y, 0.27);
  float arm = smoothstep(0.03, 0.022, abs(px)) * smoothstep(0.006, 0.003, abs(c.y - 0.245));
  float sag = 0.04 * (1.0 - pow(abs(pu - 0.5) * 2.0 - 1.0, 2.0)) ;
  sag = 0.04 * (1.0 - pow(2.0 * pu - 1.0, 2.0));
  float wires = smoothstep(0.003, 0.0, abs(c.y - (0.24 - (0.04 - sag)))) + smoothstep(0.003, 0.0, abs(c.y - (0.225 - (0.04 - sag))));
  o = over(o, vec3(0.16, 0.09, 0.06), clamp(pole + arm, 0.0, 1.0) * 0.95);
  o = over(o, vec3(0.12, 0.07, 0.05), clamp(wires, 0.0, 1.0) * 0.7);
  // the locomotive's smoke blowing past the glass now and then
  vec2 smq = vec2(c.x * 2.5 + t * 0.9, c.y * 5.0 + 0.3 * sin(t * 0.7));
  float smoke = fbm(smq + fbm(smq * 1.5 + t * 0.4) * 1.3);
  float gust = smoothstep(0.35, 0.7, noise(vec2(t * 0.18, 4.0)));
  o = over(o, mix(vec3(0.95, 0.78, 0.7), vec3(0.45, 0.35, 0.4), smoothstep(0.55, 0.9, smoke)), smoothstep(0.45, 0.8, smoke) * smoothstep(0.02, 0.22, c.y) * gust * 0.8);
  // --- the glass: a sheen, dust specks, the lamps' warm reflection
  float sheen = smoothstep(0.05, 0.0, abs(fract((c.x + c.y * 0.6) * 1.3 + 0.2) - 0.5) - 0.06);
  o = over(o, vec3(1.0, 0.95, 0.9), sheen * 0.06);
  vec2 dg = c * 90.0;
  o = over(o, vec3(0.9, 0.8, 0.7), step(0.985, hash(floor(dg))) * smoothstep(0.4, 0.1, length(fract(dg) - 0.5)) * 0.35);
  // --- inside the carriage: the window's opening
  vec2 wq = c - vec2(0.0, 0.07);
  float wd = length(max(abs(wq) - vec2(0.5, 0.24) + 0.05, 0.0)) - 0.05;
  float inside = smoothstep(-aa, aa, wd);
  // mahogany panels: planks, grain, mouldings; warmed near the window by the sunset, by the lamps elsewhere
  float plank = 0.82 + 0.18 * smoothstep(0.0, 0.06, fract(c.x * 9.0)) * smoothstep(1.0, 0.94, fract(c.x * 9.0));
  float grain = fbm(vec2(c.x * 40.0 + fbm(c * 6.0) * 2.0, c.y * 220.0));
  vec3 wood = mix(vec3(0.2, 0.07, 0.04), vec3(0.42, 0.17, 0.08), grain) * plank;
  vec2 wp = vec2(fract(c.x * 2.6) - 0.5, c.y + 0.36);
  float panel = smoothstep(0.004, 0.0, abs(max(abs(wp.x) - 0.15, abs(wp.y) - 0.09))) * step(c.y, -0.24);
  wood *= 1.0 - 0.35 * panel;
  float sunIn = exp(-max(wd, 0.0) * 9.0);
  float lampFl = 0.85 + 0.1 * sin(t * 9.0) + 0.05 * noise(vec2(t * 4.0, 1.0));
  vec3 lit = wood * (0.45 + 0.9 * sunIn) + vec3(0.35, 0.15, 0.05) * exp(-length((c - vec2(sign(c.x) * 0.66, 0.12)) * vec2(1.0, 0.8)) * 5.0) * lampFl;
  // the window's frame, bevelled, its inner edge caught by the light
  float frame = smoothstep(0.036, 0.03, wd) * step(0.0, wd);
  vec3 frameCol = mix(vec3(0.3, 0.12, 0.05), vec3(0.75, 0.42, 0.2), smoothstep(0.036, 0.0, wd)) * (0.75 + 0.25 * grain);
  lit = mix(lit, frameCol, frame);
  float sill = step(abs(c.y + 0.21), 0.012) * step(abs(c.x), 0.56);
  lit = mix(lit, vec3(0.62, 0.32, 0.14) * (0.8 + 0.3 * grain) * (0.7 + 0.5 * smoothstep(-0.222, -0.198, c.y)), sill);
  o = over(o, lit, inside);
  // the velvet curtains drawn back at the sides, folded, swaying; the valance scalloped across the top
  float swayC = 0.006 * sin(t * 1.6) + clack * 2.0;
  float cx = abs(c.x) - 0.42 - swayC * sign(c.x);
  float drape = smoothstep(0.0, 0.004, cx + 0.02 * smoothstep(0.0, -0.2, c.y - 0.1) * smoothstep(-0.25, 0.0, c.y + 0.1)) * step(-0.3, c.y) * step(c.y, 0.33) * step(abs(c.x), 0.62);
  float folds = 0.65 + 0.35 * sin(c.x * 120.0 + sin(c.y * 8.0) * 2.0);
  vec3 velvet = vec3(0.45, 0.06, 0.07) * folds * (0.6 + 0.6 * sunIn);
  o = over(o, velvet, drape);
  float valB = 0.295 - 0.014 * abs(sin(c.x * 14.0 + swayC * 30.0));
  float valance = step(valB, c.y) * step(c.y, 0.345) * step(abs(c.x), 0.6);
  o = over(o, vec3(0.5, 0.08, 0.08) * (0.7 + 0.3 * sin(c.x * 60.0)) * (0.7 + 0.4 * sunIn), valance);
  o = over(o, vec3(0.85, 0.65, 0.25), smoothstep(0.004, 0.0, abs(c.y - valB - 0.004)) * valance * 0.9);
  // the brass luggage rack above, a suitcase jolting on it
  float rack = smoothstep(0.004, 0.0, abs(c.y - 0.385)) + smoothstep(0.003, 0.0, abs(c.y - 0.41)) + step(0.9, fract(c.x * 12.0)) * step(0.385, c.y) * step(c.y, 0.41) * 0.6;
  o = over(o, vec3(0.85, 0.62, 0.25) * (0.6 + 0.5 * lampFl), clamp(rack, 0.0, 1.0));
  float jolt = clack * 3.0;
  vec2 bag = c - vec2(-0.12, 0.44 + jolt);
  float suitcase = smoothstep(aa, -aa, length(max(abs(bag) - vec2(0.085, 0.028), 0.0)) - 0.008);
  vec3 leather = vec3(0.35, 0.18, 0.08) * (0.75 + 0.35 * fbm(bag * 60.0));
  leather = mix(leather, vec3(0.85, 0.62, 0.25), smoothstep(0.004, 0.0, abs(abs(bag.x) - 0.05)) * 0.8);
  o = over(o, leather, suitcase);
  // oil lamps on the pillars, their flames flickering, their glow
  for (int k = 0; k < 2; k++) {
    vec2 lq = c - vec2(k == 0 ? -0.66 : 0.66, 0.12);
    float glass = smoothstep(0.003, 0.0, length(lq * vec2(1.0, 0.7)) - 0.022);
    float flame = smoothstep(0.012, 0.0, length((lq - vec2(0.0, 0.002)) * vec2(1.6, 0.8))) * lampFl;
    float bracket = smoothstep(0.004, 0.002, abs(lq.y + 0.035)) * step(abs(lq.x), 0.02) + smoothstep(0.003, 0.0, abs(lq.x)) * step(-0.07, lq.y) * step(lq.y, -0.03);
    o = over(o, vec3(0.8, 0.58, 0.22), clamp(bracket, 0.0, 1.0));
    o = over(o, vec3(1.0, 0.85, 0.55), glass * 0.35);
    o = over(o, vec3(1.0, 0.8, 0.4), flame);
    o = over(o, vec3(1.0, 0.65, 0.3), exp(-length(lq) * 14.0) * 0.35 * lampFl);
  }
  o.rgb *= mix(0.38, 1.0, smoothstep(1.1, 0.25, length(c * vec2(0.7, 1.0))));
  o.rgb += (hash(gl_FragCoord.xy + fract(t) * 91.0) - 0.5) * 0.03;
