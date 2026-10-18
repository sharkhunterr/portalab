// Cogwork — the booster stage deep in an engine room, painted in depth: a hand-laid brick wall lit from below by
  // a furnace that breathes, light falling in shafts from a high window through the dust, great worn gears turning
  // and meshing (the far ones soft, a near one dark and out of focus), a copper pipe sagging across with a gauge
  // whose needle trembles, valves hissing out curling steam, a chain swaying, embers rising. The camera sways.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y + vec2(0.006 * sin(t * 0.35), 0.004 * sin(t * 0.27));
  float fl = 0.82 + 0.1 * sin(t * 7.3) + 0.06 * sin(t * 13.1 + 1.0) + 0.05 * noise(vec2(t * 3.0, 0.5));
  // the wall: bricks laid by hand — each course offset, each brick its own tone, the mortar uneven, soot above
  vec2 bq = c * vec2(8.0, 17.0) + vec2(0.0, 0.3);
  bq.x += 0.5 * mod(floor(bq.y), 2.0) + 0.06 * (noise(vec2(floor(bq.y), 3.0)) - 0.5);
  vec2 bid = floor(bq);
  vec2 bf = fract(bq);
  float mortar = smoothstep(0.03, 0.09, min(min(bf.x, 1.0 - bf.x) * 0.5, min(bf.y, 1.0 - bf.y)) + 0.05 * (noise(c * 70.0) - 0.5));
  vec3 brick = mix(vec3(0.15, 0.065, 0.04), vec3(0.34, 0.15, 0.08), hash(bid)) * (0.7 + 0.6 * fbm(c * 26.0 + bid));
  vec3 wall = mix(vec3(0.045, 0.03, 0.022), brick, mortar) * mix(1.0, 0.45, smoothstep(0.0, 0.5, c.y) * fbm(c * 4.0));
  float warm = exp(-length((c - vec2(0.0, -0.6)) * vec2(0.85, 1.25)) * 2.1) * fl;
  o = over(o, wall * (0.3 + 1.5 * warm) + vec3(0.28, 0.08, 0.02) * warm, 1.0);
  // light falling from a high window (top right) in shafts through the dusty air, the dust drifting in it
  vec2 w = c - vec2(0.55, 0.66);
  float wa = atan(w.y, w.x);
  float cone = smoothstep(0.45, 0.15, abs(wa + 2.3));
  float shafts = cone * smoothstep(0.25, 0.85, noise(vec2(wa * 26.0, t * 0.12))) * smoothstep(1.5, 0.15, length(w));
  o = over(o, vec3(1.0, 0.78, 0.48), shafts * 0.2);
  for (int k = 0; k < 26; k++) {
    float fk = float(k);
    vec2 at = vec2(hash(vec2(fk, 1.0)) - 0.5, hash(vec2(fk, 2.0)) - 0.5) * vec2(1.6, 1.0);
    at += vec2(noise(vec2(t * 0.1, fk)) - 0.5, noise(vec2(fk, t * 0.08)) - 0.5) * 0.2;
    vec2 aw = at - vec2(0.55, 0.66);
    float inShaft = smoothstep(0.45, 0.15, abs(atan(aw.y, aw.x) + 2.3));
    o = over(o, vec3(1.0, 0.85, 0.6), exp(-length(c - at) * (500.0 + 300.0 * hash(vec2(fk, 3.0)))) * (0.15 + 0.85 * inShaft) * 0.8);
  }
  // the gears: worn brass, rounded teeth, curved spokes; they mesh and turn — the far ones soft, the near one dark
  for (int k = 0; k < 4; k++) {
    vec2 gc = vec2(-0.38, 0.22);
    float gr = 0.36;
    float gn = 24.0;
    float gw = 0.1;
    float blur = 0.008;
    float lit = 0.55;
    if (k == 1) { gc = vec2(0.21, 0.06); gr = 0.25; gn = 17.0; gw = -0.1 * 24.0 / 17.0; blur = 0.006; lit = 0.75; }
    else if (k == 2) { gc = vec2(0.34, -0.3); gr = 0.11; gn = 9.0; gw = 0.1 * 24.0 / 9.0; blur = 0.004; lit = 0.9; }
    else if (k == 3) { gc = vec2(-0.22, -0.56); gr = 0.2; gn = 13.0; gw = -0.05; blur = 0.03; lit = 0.12; }
    vec2 q = c - gc;
    float r = length(q) + 0.0001;
    float a = atan(q.y, q.x) + t * gw;
    float tooth = smoothstep(-0.4, 0.4, sin(a * gn));
    float body = smoothstep(blur, -blur, r - gr * (0.9 + 0.1 * tooth));
    float rim = smoothstep(-blur, blur, r - gr * 0.7);
    float hub = smoothstep(blur, -blur, r - gr * 0.22);
    float spokes = smoothstep(0.3, 0.12, abs(sin((a + r / gr * 0.7) * 2.5))) * step(r, gr * 0.72);
    float metal = body * clamp(rim + hub + spokes, 0.0, 1.0);
    vec2 pol = vec2(cos(a), sin(a)) * r;
    float patina = fbm(pol * 22.0 + float(k) * 5.0);
    float light = 0.45 + 0.55 * dot(q / r, vec2(0.15, -0.99)) * warm * 2.0;
    vec3 col = mix(vec3(0.28, 0.16, 0.06), vec3(0.88, 0.62, 0.28), clamp(light * (0.5 + patina), 0.0, 1.0));
    col = mix(col, vec3(0.2, 0.3, 0.22), smoothstep(0.62, 0.8, patina) * 0.5);
    col *= 1.0 - 0.5 * smoothstep(0.02, 0.0, abs(r - gr * 0.7)) - 0.4 * smoothstep(0.015, 0.0, abs(r - gr * 0.22));
    col += vec3(1.0, 0.75, 0.4) * smoothstep(0.012, 0.0, abs(r - gr * (0.9 + 0.1 * tooth))) * light * 0.5;
    o = over(o, col * lit, metal);
  }
  // a copper pipe sagging across, its bands and rivets, lit along its round
  float py = -0.27 + 0.05 * sin(c.x * 2.6 + 0.6) + 0.015 * sin(c.x * 7.0);
  float across = (c.y - py) / 0.034;
  float pipe = smoothstep(1.05, 0.95, abs(across));
  float round = sqrt(max(1.0 - across * across, 0.0));
  vec3 copper = mix(vec3(0.35, 0.13, 0.06), vec3(0.95, 0.55, 0.32), round * (0.6 + 0.5 * fbm(vec2(c.x * 30.0, across))));
  copper *= 1.0 - 0.45 * smoothstep(0.012, 0.0, abs(fract(c.x * 3.5 + 0.2) - 0.5) - 0.018);
  copper += vec3(1.0, 0.8, 0.6) * pow(round, 12.0) * smoothstep(-0.2, 0.6, across) * 0.35;
  o = over(o, copper * (0.5 + warm), pipe);
  // its gauge, the needle trembling under the pressure
  vec2 gq = c - vec2(-0.15, -0.2);
  float gl = length(gq);
  o = over(o, vec3(0.75, 0.55, 0.25) * (0.6 + warm), smoothstep(0.052, 0.048, gl));
  o = over(o, vec3(0.93, 0.88, 0.76) * (0.55 + warm), smoothstep(0.042, 0.039, gl));
  float ga = atan(gq.x, gq.y);
  o = over(o, vec3(0.15, 0.1, 0.08), step(0.86, fract(ga / 6.2832 * 16.0)) * smoothstep(0.004, 0.0, abs(gl - 0.034) - 0.004) * step(abs(ga), 2.2));
  float needle = 0.6 + 0.35 * sin(t * 0.4) + 0.05 * sin(t * 23.0) + 0.04 * (noise(vec2(t * 6.0, 1.0)) - 0.5);
  vec2 nd = vec2(sin(needle), cos(needle));
  float along = clamp(dot(gq, nd), 0.0, 0.034);
  o = over(o, vec3(0.6, 0.08, 0.05), smoothstep(0.0025, 0.0, length(gq - nd * along)) + smoothstep(0.006, 0.004, gl));
  // valves hissing out steam: puffs curling, growing, drifting with the warm draught
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float vx = -0.32 + fk * 0.34;
    vec2 base = vec2(vx, -0.27 + 0.05 * sin(vx * 2.6 + 0.6) + 0.015 * sin(vx * 7.0) + 0.03);
    float cyc = fract(t * (0.13 + 0.03 * fk) + fk * 0.37);
    float puff = smoothstep(0.0, 0.08, cyc) * smoothstep(0.75, 0.25, cyc);
    vec2 q = c - base;
    q.x -= q.y * q.y * 0.6 + 0.04 * sin(q.y * 9.0 - t * 2.0);
    vec2 sq = vec2(q.x * 6.0, q.y * 3.5 - t * 1.6);
    float steam = fbm(sq + fbm(sq * 1.7 + t * 0.4) * 1.2);
    float plume = smoothstep(0.03 + q.y * 0.45, 0.0, abs(q.x)) * step(0.0, q.y) * smoothstep(0.75, 0.05, q.y);
    o = over(o, mix(vec3(0.95, 0.9, 0.86), vec3(1.0, 0.6, 0.35), warm * 0.6), smoothstep(0.35, 0.75, steam) * plume * puff * 0.75);
  }
  // a chain hanging from above, swaying, its links catching the furnace light
  float sw = 0.1 * sin(t * 0.8) + 0.03 * sin(t * 1.9);
  vec2 top = vec2(0.1, 0.56);
  vec2 dir = vec2(sin(sw), -cos(sw));
  vec2 cq = c - top;
  float s = dot(cq, dir);
  float side = dot(cq, vec2(-dir.y, dir.x));
  float link = fract(s * 32.0);
  float ring = mod(floor(s * 32.0), 2.0) < 0.5
    ? smoothstep(0.002, 0.0, abs(length(vec2(side * 32.0 / 0.7, (link - 0.5) * 1.6)) - 0.6) * 0.03 - 0.0015)
    : smoothstep(0.0025, 0.0, abs(side) - 0.002);
  o = over(o, vec3(0.3, 0.2, 0.12) * (0.6 + warm * 1.2), ring * step(0.0, s) * step(s, 0.42));
  // embers rising from the furnace, wandering, dying out
  for (int k = 0; k < 22; k++) {
    float fk = float(k);
    float life = fract(t * (0.12 + 0.08 * hash(vec2(fk, 4.0))) + hash(vec2(fk, 5.0)));
    vec2 at = vec2((hash(vec2(fk, 6.0)) - 0.5) * 0.9 + 0.08 * sin(life * 9.0 + fk) + 0.05 * (noise(vec2(fk, t)) - 0.5), -0.55 + life * 0.9);
    float ember = exp(-length(c - at) * 650.0) * (1.0 - life) * (0.6 + 0.4 * sin(t * 20.0 + fk));
    o = over(o, mix(vec3(1.0, 0.85, 0.4), vec3(1.0, 0.3, 0.05), life), ember * 1.6);
  }
  // smoke lying low, warm haze; the vignette and the film's grain
  float haze = fbm(vec2(c.x * 2.0 - t * 0.03, c.y * 3.0 + t * 0.02));
  o = over(o, vec3(0.4, 0.2, 0.1) * (0.5 + warm), smoothstep(0.4, 0.8, haze) * 0.25);
  o.rgb *= mix(0.35, 1.0, smoothstep(1.1, 0.25, length(c * vec2(0.75, 1.0))));
  o.rgb += (hash(gl_FragCoord.xy + fract(t) * 91.0) - 0.5) * 0.035;
