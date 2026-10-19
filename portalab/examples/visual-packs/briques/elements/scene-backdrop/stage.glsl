// Bricks — the booster stage in a playroom, in perspective: a warm wall and a window's light falling in a shaft
  // with dust, a wooden floor running to the horizon, a big green studded plate on it with a town of brick houses
  // (running bond, their roofs, their windows), a toy crane lowering a brick then raising its line again, bricks
  // scattered near us out of focus. The camera breathes.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y + vec2(0.004 * sin(t * 0.3), 0.003 * sin(t * 0.23));
  float aa = 1.5 / u_res.y;
  float hz = 0.02;
  vec2 v = c - vec2(0.0, hz);
  // the wall, warm, with a soft pattern, and the window's light
  o = over(o, mix(vec3(0.95, 0.88, 0.76), vec3(0.85, 0.74, 0.6), smoothstep(0.0, 0.5, v.y)) * (0.92 + 0.08 * step(0.5, fract(c.x * 12.0))), 1.0);
  vec2 wq = c - vec2(-0.55, 0.32);
  float win = step(abs(wq.x), 0.16) * step(abs(wq.y), 0.14);
  float bars = step(abs(wq.x), 0.008) + step(abs(wq.y), 0.008);
  o = over(o, mix(vec3(0.85, 0.95, 1.0), vec3(0.55, 0.75, 0.95), wq.y * 2.0 + 0.5), win);
  o = over(o, vec3(0.95, 0.95, 0.92), clamp(bars, 0.0, 1.0) * win);
  // the floor: planks running away, a warm sheen
  float zg = 0.09 / max(-v.y, 0.0005);
  float gx = c.x * zg;
  float planks = step(0.03, fract(gx * 6.0)) * step(0.02, fract(zg * 1.3 + floor(gx * 6.0) * 0.37));
  vec3 wood = mix(vec3(0.62, 0.42, 0.24), vec3(0.75, 0.53, 0.32), hash(vec2(floor(gx * 6.0), floor(zg * 1.3 + floor(gx * 6.0) * 0.37)))) * (0.8 + 0.2 * fbm(vec2(gx * 40.0, zg * 3.0)));
  wood *= 0.75 + 0.25 * planks;
  wood = mix(wood, vec3(0.95, 0.85, 0.7), smoothstep(1.0, 8.0, zg) * 0.6);
  o = over(o, wood, smoothstep(aa, -aa, v.y));
  // the window's light: a shaft across the room and its pool on the floor, dust in it
  vec2 sh = c - vec2(-0.55, 0.32);
  float shaft = smoothstep(0.2, 0.0, abs(sh.x - sh.y * 0.9 + 0.0) - 0.05 - (-sh.y) * 0.25) * step(sh.y, 0.0);
  o = over(o, vec3(1.0, 0.95, 0.8), shaft * 0.12);
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    vec2 at = vec2(-0.55 + (hash(vec2(fk, 1.0)) - 0.2) * 0.6, 0.3 - hash(vec2(fk, 2.0)) * 0.6) + vec2(noise(vec2(t * 0.15, fk)) - 0.5, noise(vec2(fk, t * 0.12)) - 0.5) * 0.08;
    vec2 aq = at - vec2(-0.55, 0.32);
    float inS = smoothstep(0.2, 0.0, abs(aq.x - aq.y * 0.9) - 0.05 - (-aq.y) * 0.25);
    o = over(o, vec3(1.0, 0.97, 0.88), exp(-length(c - at) * 500.0) * inS);
  }
  // the big green plate, its studs in perspective
  float zp = zg;
  float onPlate = step(v.y, 0.0) * step(abs(gx), 0.75) * step(0.9, zp) * step(zp, 4.0);
  vec2 sp = fract(vec2(gx, zp * 0.5) * vec2(20.0, 20.0)) - 0.5;
  vec3 green = vec3(0.16, 0.6, 0.29) * (0.85 + 0.25 * smoothstep(0.3, 0.2, length(sp * vec2(1.0, 0.6)))) * (0.75 + 0.25 * smoothstep(4.0, 0.9, zp));
  o = over(o, green, onPlate);
  // the brick houses standing on the plate, their faces toward us at the plate's depth
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float zh = 1.15 + 0.4 * mod(fk * 3.0, 5.0);
    float xh = (fk - 2.0) * 0.3 + 0.05 * sin(fk * 2.3);
    float wh = 0.24;
    float hh = 0.14 + 0.12 * hash(vec2(fk, 3.0));
    vec2 base = vec2(xh / zh, hz - 0.09 / zh);
    vec2 q = (c - base) * zh;
    float rows = floor(q.y / 0.03);
    vec2 bq = vec2((q.x + 0.03 * mod(rows, 2.0)) / 0.06, q.y / 0.03);
    vec2 bid = floor(bq);
    vec2 bf = fract(bq);
    float wall = step(abs(q.x), wh * 0.5) * step(0.0, q.y) * step(q.y, hh);
    float roof = step(hh, q.y) * step(q.y - hh, (wh * 0.5 - abs(q.x)) * 0.8) * step(abs(q.x), wh * 0.5 + 0.01);
    float hb = hash(bid + fk * 7.0);
    vec3 bc = hb < 0.5 ? vec3(0.84, 0.16, 0.16) : (hb < 0.75 ? vec3(0.95, 0.95, 0.92) : vec3(0.97, 0.77, 0.12));
    bc = mix(bc, vec3(0.12, 0.44, 0.84), step(0.5, hash(vec2(fk, 4.0))) * step(hb, 0.5));
    bc *= 0.75 + 0.25 * smoothstep(0.0, 0.15, bf.x) * smoothstep(1.0, 0.85, bf.x) * smoothstep(0.0, 0.2, bf.y);
    float window = step(0.3, bf.x) * step(bf.x, 0.7) * step(0.25, bf.y) * step(bf.y, 0.85) * step(0.7, hash(bid + 3.0)) * step(1.0, bid.y);
    bc = mix(bc, vec3(0.6, 0.85, 1.0), window);
    float fogh = smoothstep(1.2, 3.2, zh) * 0.3;
    o = over(o, mix(bc, vec3(0.95, 0.88, 0.76), fogh), wall);
    o = over(o, mix(vec3(0.12, 0.35, 0.7), vec3(0.95, 0.88, 0.76), fogh) * (0.85 + 0.15 * step(0.5, fract(q.x * 60.0))), roof);
  }
  // a toy crane on the right, lowering a brick on its line, then raising it again
  vec2 cq = c - vec2(0.42, hz - 0.03);
  float mast = step(abs(cq.x), 0.008) * step(0.0, cq.y) * step(cq.y, 0.42);
  float jib = step(abs(cq.y - 0.4), 0.007) * step(-0.3, cq.x) * step(cq.x, 0.06);
  float lattice = step(0.5, fract((cq.y + cq.x) * 40.0)) * (mast + jib) * 0.4;
  o = over(o, vec3(0.97, 0.77, 0.12), clamp(mast + jib, 0.0, 1.0) * (0.85 + 0.15 * lattice));
  float hook = 0.36 - 0.22 * (0.5 - 0.5 * cos(t * 0.6));
  float line = step(abs(cq.x + 0.24), 0.0015) * step(hook, cq.y) * step(cq.y, 0.4);
  o = over(o, vec3(0.2), line);
  vec2 hb2 = cq - vec2(-0.24, hook - 0.02);
  o = over(o, vec3(0.12, 0.44, 0.84) * (0.8 + 0.3 * smoothstep(-0.02, 0.02, hb2.y)), step(abs(hb2.x), 0.035) * step(abs(hb2.y), 0.016));
  // bricks scattered near us, out of focus
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 at = vec2((hash(vec2(fk, 5.0)) - 0.5) * 1.6, -0.38 - 0.1 * hash(vec2(fk, 6.0)));
    float ang = (hash(vec2(fk, 7.0)) - 0.5) * 1.2;
    vec2 q = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * (c - at);
    float blur = 0.012;
    float body = smoothstep(blur, -blur, max(abs(q.x) - 0.1, abs(q.y) - 0.04));
    float studs = smoothstep(blur, -blur, max(abs(fract(q.x / 0.05 + 0.5) - 0.5) * 0.05 - 0.016, abs(q.y - 0.048) - 0.01)) * step(abs(q.x), 0.1);
    float hh = hash(vec2(fk, 8.0));
    vec3 bc = hh < 0.33 ? vec3(0.84, 0.16, 0.16) : (hh < 0.66 ? vec3(0.97, 0.77, 0.12) : vec3(0.12, 0.44, 0.84));
    o = over(o, bc * (0.7 + 0.35 * smoothstep(-0.04, 0.04, q.y)), clamp(body + studs, 0.0, 1.0) * 0.95);
  }
  o.rgb *= mix(0.55, 1.0, smoothstep(1.15, 0.3, length(c * vec2(0.7, 1.0))));
  o.rgb += (hash(gl_FragCoord.xy + fract(t) * 91.0) - 0.5) * 0.02;
