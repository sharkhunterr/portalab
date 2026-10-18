// Olympus — the booster stage in the hall of the gods, in one-point perspective: two colonnades of marble running
  // away to a great portal open on the setting sun and the sea of clouds, a coffered ceiling picked out in gold, a
  // polished marble floor mirroring the columns and the fires, braziers burning at the columns' feet, clouds
  // flowing in along the floor, the light pouring in through the portal in rays, gold dust in it, lightning now and
  // then outside — and the camera gliding slowly forward, for ever.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y + vec2(0.003 * sin(t * 0.25), 0.002 * sin(t * 0.19));
  float aa = 1.5 / u_res.y;
  float h0 = 0.08;
  float Hc = 0.34;
  float Wc = 0.13;
  float D = 0.32;
  float z0 = 0.47;
  float zEnd = 3.4;
  float dolly = mod(t * 0.035, D);
  vec2 v = c;
  // outside: the sky at sunset, the sun in the portal, clouds; a flash of lightning now and then
  float lph = fract(t / 7.0);
  float bolt = exp(-abs(lph - 0.6) * 70.0) + 0.6 * exp(-abs(lph - 0.63) * 90.0);
  vec3 sky = mix(vec3(1.0, 0.8, 0.5), vec3(0.95, 0.55, 0.42), smoothstep(0.0, 0.12, v.y));
  sky = mix(sky, vec3(0.32, 0.38, 0.7), smoothstep(0.1, 0.45, v.y));
  sky = mix(sky, vec3(0.98, 0.94, 0.9), smoothstep(0.0, -0.06, v.y));
  vec2 oc = vec2(v.x * 2.0 + t * 0.01, v.y * 6.0);
  float ocl = fbm(oc + fbm(oc * 1.4 + t * 0.02) * 1.2);
  sky = mix(sky, mix(vec3(1.0, 0.75, 0.55), vec3(0.6, 0.5, 0.62), smoothstep(0.55, 0.85, ocl)), smoothstep(0.5, 0.7, ocl) * smoothstep(0.02, 0.1, v.y) * 0.8);
  sky = mix(sky, mix(vec3(1.0, 0.92, 0.8), vec3(0.75, 0.72, 0.8), smoothstep(0.5, 0.8, ocl)), smoothstep(0.0, -0.03, v.y) * smoothstep(0.35, 0.6, ocl));
  vec2 sp = v - vec2(0.0, 0.015);
  sky += vec3(1.0, 0.9, 0.6) * (smoothstep(0.022, 0.018, length(sp)) + exp(-length(sp) * 9.0) * 0.6);
  sky += vec3(0.7, 0.75, 1.0) * bolt * 0.5;
  o = over(o, sky, 1.0);
  vec3 haze = vec3(1.0, 0.86, 0.66);
  // the end wall, far away, with its great arched portal open on the sky
  vec2 ew = v * zEnd;
  float ewY = ew.y + h0;
  float wall = step(abs(ew.x), Wc + 0.2) * step(0.0, ewY) * step(ewY, Hc + 0.12);
  float portal = step(abs(ew.x), 0.085) * step(ewY, 0.2) + smoothstep(0.086, 0.084, length(vec2(ew.x, ewY - 0.2))) * step(0.2, ewY);
  vec3 endCol = mix(vec3(0.82, 0.74, 0.66), haze, 0.55) * (0.8 + 0.2 * fbm(ew * 40.0));
  o = over(o, endCol, wall * (1.0 - clamp(portal, 0.0, 1.0)));
  // the ceiling: coffers between the two beams, gold rosettes, deepening into haze
  float zc = (Hc + 0.045 - h0) / max(v.y, 0.0001);
  float onCeil = step(0.0, v.y) * step(zc, zEnd) * step(abs(v.x * zc), Wc);
  vec2 cw = vec2(v.x * zc, zc + dolly);
  vec2 cf = fract(cw / vec2(0.065, D * 0.5) + vec2(0.5, 0.0)) - 0.5;
  float coffer = smoothstep(0.42, 0.36, max(abs(cf.x), abs(cf.y)));
  float ros = smoothstep(0.09, 0.05, length(cf * vec2(1.0, 0.6)));
  vec3 ceil = mix(vec3(0.62, 0.55, 0.5), vec3(0.42, 0.36, 0.38), coffer) + vec3(0.85, 0.62, 0.22) * ros * 0.55;
  ceil = mix(ceil, haze, 1.0 - exp(-zc * 0.45));
  o = over(o, ceil, onCeil);
  // the beams over the columns, both sides, with their frieze
  float zw = Wc / max(abs(v.x), 0.0001);
  float Yw = v.y * zw + h0;
  float onBeam = step(Hc, Yw) * step(Yw, Hc + 0.045) * step(zw, zEnd) * step(z0 - D, zw);
  float friezeB = step(0.5, fract((zw + dolly) * 24.0)) * step(abs(Yw - Hc - 0.025), 0.007);
  vec3 beamCol = vec3(0.86, 0.8, 0.72) * (0.7 + 0.15 * friezeB) + vec3(0.85, 0.6, 0.2) * smoothstep(0.003, 0.0, abs(Yw - Hc - 0.04)) * 0.6;
  o = over(o, mix(beamCol, haze, 1.0 - exp(-zw * 0.45)), onBeam);
  // the floor (the hall's own, the sea of clouds beyond its colonnades): veined marble slabs in a checker, a gold meander down the aisle, mirroring what stands on it
  float zg = h0 / max(-v.y, 0.0001);
  float onFloor = step(v.y, 0.0) * step(zg, zEnd) * smoothstep(Wc + 0.05, Wc + 0.04, abs(v.x * zg));
  vec2 fw = vec2(v.x * zg, zg + dolly);
  vec2 tile = floor(fw / vec2(0.065, D * 0.25));
  float checker = mod(tile.x + tile.y, 2.0);
  float vein = smoothstep(0.03, 0.0, abs(fbm(fw * vec2(30.0, 12.0) + tile) - 0.5));
  vec3 fl = mix(vec3(0.92, 0.89, 0.84), vec3(0.62, 0.6, 0.62), checker) * (1.0 - 0.25 * vein);
  float lineW = 0.0012 * zg;
  float runner = smoothstep(lineW, 0.0, abs(abs(fw.x) - 0.032)) + smoothstep(lineW, 0.0, abs(abs(fw.x) - 0.026));
  float key = smoothstep(lineW, 0.0, abs(fract(fw.y * 40.0) - 0.5) * 0.025 - 0.0) * step(0.026, abs(fw.x)) * step(abs(fw.x), 0.032);
  fl = mix(fl, vec3(0.85, 0.62, 0.22), clamp(runner + key, 0.0, 1.0) * 0.75);
  // the reflections: the sun's path down the aisle, and each column's image under it
  fl += vec3(1.0, 0.85, 0.6) * exp(-abs(v.x) * 30.0) * smoothstep(0.0, -0.3, v.y) * 0.35 * smoothstep(-0.5, -0.02, v.y);
  float n = floor((zw + dolly - z0) / D + 0.5);
  float zn = z0 + n * D - dolly;
  float xs = sign(v.x) * Wc / zn;
  float ym = 2.0 * (-h0 / zn) - v.y;
  float refl = step(abs(c.x - xs), 0.02 / zn) * step(-h0 / zn, ym) * step(ym, (Hc - h0) / zn) * step(z0 - D, zn) * step(v.y, -h0 / zn);
  fl = mix(fl, vec3(0.8, 0.76, 0.72), refl * 0.3 * exp(-max((-h0 / zn - v.y) * zn * 3.0, 0.0)));
  float fireRefl = exp(-abs(c.x - sign(v.x) * (Wc - 0.035) / zn) * zn * 90.0) * step(v.y, -h0 / zn) * exp(-max((-h0 / zn - v.y) * zn * 6.0, 0.0)) * step(0.5, mod(n, 2.0));
  fl += vec3(1.0, 0.55, 0.2) * fireRefl * 0.6 * (0.8 + 0.2 * sin(t * 9.0 + n));
  fl = mix(fl, haze, 1.0 - exp(-zg * 0.45));
  o = over(o, fl, onFloor);
  // the columns, both sides, far to near: fluted, swelling, their capitals and bases, a fire at every other foot
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    float ni = 9.0 - floor(fk / 2.0);
    float sd = mod(fk, 2.0) < 0.5 ? -1.0 : 1.0;
    float zk = z0 + ni * D - dolly;
    float xk = sd * Wc / zk;
    float yb = -h0 / zk;
    float yt = (Hc - h0) / zk;
    float hN = clamp((v.y - yb) / (yt - yb), 0.0, 1.0);
    float wk = 0.019 / zk * (1.0 + 0.08 * sin(hN * 3.1416)) * (1.0 - 0.12 * hN);
    float qx = (c.x - xk) / wk;
    float col = smoothstep(1.0 + aa * 2.0 / wk, 1.0, abs(qx)) * step(yb, v.y) * step(v.y, yt);
    float flute = 0.82 + 0.18 * abs(sin(qx * 6.0));
    float inner = -sd * qx;
    float shade = 0.5 + 0.3 * sqrt(max(1.0 - qx * qx, 0.0)) + 0.35 * smoothstep(0.3, 1.0, inner);
    vec3 cc = vec3(0.93, 0.9, 0.84) * flute * shade * (0.85 + 0.2 * fbm(vec2(qx, v.y * zk * 30.0) + ni));
    cc += vec3(1.0, 0.75, 0.4) * smoothstep(0.6, 1.0, inner) * 0.25 + vec3(0.7, 0.75, 1.0) * bolt * smoothstep(0.5, 1.0, -inner) * 0.4;
    float fog = 1.0 - exp(-zk * 0.45);
    o = over(o, mix(cc, haze, fog), col);
    float capB = step(abs(c.x - xk), wk * 1.45) * step(abs(v.y - yt - 0.007 / zk), 0.007 / zk);
    float baseB = step(abs(c.x - xk), wk * 1.35) * step(abs(v.y - yb - 0.006 / zk), 0.006 / zk);
    o = over(o, mix(vec3(0.8, 0.74, 0.66), haze, fog), clamp(capB + baseB, 0.0, 1.0));
    // a brazier on the aisle side of every other column
    float lit = step(0.5, mod(ni, 2.0));
    vec2 bq = vec2(c.x - sd * (Wc - 0.035) / zk, v.y - (0.045 - h0) / zk) * zk;
    float bowl = smoothstep(0.003, 0.0, length(bq * vec2(1.0, 2.2)) - 0.016) * step(bq.y, 0.0);
    float legsB = smoothstep(0.002, 0.0, abs(abs(bq.x) - 0.003 - (-bq.y) * 0.25)) * step(-0.045, bq.y) * step(bq.y, -0.004);
    o = over(o, mix(vec3(0.5, 0.32, 0.12), haze, fog), clamp(bowl + legsB, 0.0, 1.0) * lit);
    vec2 fq = vec2(bq.x * 45.0, bq.y * 20.0 - t * 4.0 - ni * 2.0);
    float fire = fbm(fq + fbm(fq * 1.5) * 0.8) * smoothstep(0.018 - bq.y * 0.15, 0.0, abs(bq.x + 0.006 * sin(bq.y * 60.0 + t * 6.0))) * step(-0.002, bq.y) * smoothstep(0.08, 0.0, bq.y);
    o = over(o, mix(vec3(1.0, 0.9, 0.5), vec3(1.0, 0.38, 0.06), smoothstep(0.0, 0.06, bq.y)), clamp(fire * 2.4 - 0.4, 0.0, 1.0) * lit * (1.0 - fog * 0.6));
    o = over(o, vec3(1.0, 0.6, 0.25), exp(-length(bq * vec2(1.0, 1.4)) * 30.0) * 0.35 * lit * (1.0 - fog));
  }
  // clouds flowing in along the floor, thicker toward the portal
  vec2 mq = vec2(c.x * 3.0 - t * 0.04, c.y * 9.0 + t * 0.02);
  float mist = fbm(mq + fbm(mq * 1.3 + vec2(t * 0.05, 0.0)) * 1.4);
  float mistBand = smoothstep(0.02, -0.1, v.y) * smoothstep(-0.5, -0.12, v.y);
  o = over(o, mix(vec3(1.0, 0.95, 0.9), vec3(0.85, 0.8, 0.82), smoothstep(0.5, 0.85, mist)), smoothstep(0.42, 0.75, mist) * mistBand * 0.75);
  o = over(o, haze, smoothstep(0.08, 0.0, abs(v.y)) * 0.25);
  // the light pouring in through the portal, in rays, gold dust drifting in them
  float ra = atan(sp.y, sp.x);
  float rays = pow(noise(vec2(ra * 10.0, t * 0.08)), 3.0) * smoothstep(0.9, 0.02, length(sp)) * smoothstep(-0.4, 0.0, sp.y + 0.2);
  o = over(o, vec3(1.0, 0.9, 0.65), rays * 0.35 + exp(-length(sp) * 7.0) * 0.25);
  for (int k = 0; k < 28; k++) {
    float fk = float(k);
    float life = fract(t * (0.04 + 0.03 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 at = vec2((hash(vec2(fk, 3.0)) - 0.5) * 1.0 + 0.04 * sin(life * 8.0 + fk), -0.3 + life * 0.75);
    o = over(o, vec3(1.0, 0.86, 0.45), exp(-length(c - at) * (380.0 + 400.0 * hash(vec2(fk, 4.0)))) * sin(life * 3.1416));
  }
  o.rgb *= mix(0.55, 1.0, smoothstep(1.1, 0.25, length(c * vec2(0.7, 1.0))));
  o.rgb += (hash(gl_FragCoord.xy + fract(t) * 91.0) - 0.5) * 0.025;
