// Portalab — level_up/rift: the « rift » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float aspect = u_res.x / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.3, tl) * smoothstep(6.6, 5.4, tl);
  float enter = smoothstep(2.55, 3.05, tl);
  // the room: dark, the lights flickering before it tears
  float flick = step(0.4, hash(vec2(floor(tl * 13.0), 7.0))) * (1.0 - smoothstep(0.6, 1.4, tl));
  o = over(o, vec3(0.02, 0.0, 0.01), (0.5 + 0.25 * flick) * fade * (1.0 - enter));
  // drawn in: the rift and all round it grow from the middle, faster and faster, with a tremor
  float push = exp(max(tl - 1.7, 0.0) * 2.4);
  float shake = smoothstep(0.5, 1.5, tl) * (1.0 - enter) * 0.004;
  vec2 q = (c + vec2(hash(vec2(floor(tl * 30.0), 3.0)) - 0.5, hash(vec2(floor(tl * 30.0), 4.0)) - 0.5) * shake) / push;
  // the tear: a jagged vertical slit, widest at its middle, opening over a second
  float open = smoothstep(0.35, 1.8, tl);
  float jag = (fbm(vec2(q.y * 6.0, 3.0)) - 0.5) * 0.12 + (fbm(vec2(q.y * 24.0, 9.0)) - 0.5) * 0.035;
  float len = 0.06 + 0.5 * open;
  float along = clamp(1.0 - abs(q.y) / len, 0.0, 1.0);
  float width = 0.08 * open * pow(along, 0.65);
  float dx = abs(q.x - jag * (0.4 + open)) - width;
  float rim = step(abs(q.y), len);
  float inside = smoothstep(0.004, -0.004, dx) * rim;
  // the other side: fog, the red glow of the sky, lightning, vines and ash
  vec2 w = c * 1.3 + vec2(0.0, tl * 0.03);
  float fog = fbm(w * 2.0 + vec2(tl * 0.06, -tl * 0.02));
  vec3 world = mix(vec3(0.03, 0.05, 0.09), vec3(0.2, 0.24, 0.32), fog);
  world += vec3(0.6, 0.06, 0.05) * 0.45 * smoothstep(0.0, 0.5, c.y) * (0.7 + 0.3 * sin(tl * 1.7));
  float strike = step(0.55, hash(vec2(floor(tl * 2.5), 21.0))) * exp(-fract(tl * 2.5) * 7.0);
  float bolt = smoothstep(0.02, 0.0, abs(c.x - 0.3 * sin(floor(tl * 2.5) * 5.1) - (fbm(vec2(c.y * 9.0, floor(tl * 2.5))) - 0.5) * 0.25)) * smoothstep(-0.05, 0.3, c.y);
  world += vec3(1.0, 0.2, 0.15) * strike * (bolt * 1.2 + fbm(c * 3.0 + 11.0) * smoothstep(0.0, 0.5, c.y) * 0.8);
  float edge = max(abs(c.x) / (0.5 * aspect), abs(c.y) / 0.5);
  float vine = smoothstep(0.04, 0.0, abs(fbm(c * 4.5 + 3.0) - 0.5)) + 0.6 * smoothstep(0.025, 0.0, abs(fbm(c * 9.0 + 8.0) - 0.5));
  world = mix(world, vec3(0.1, 0.03, 0.03), clamp(vine, 0.0, 1.0) * smoothstep(0.5, 1.0, edge) * 0.9);
  for (int i = 0; i < 48; i++) {
    float fi = float(i);
    float rise = 0.025 + 0.05 * hash(vec2(fi, 141.0));
    vec2 pos = vec2((hash(vec2(fi, 142.0)) - 0.5) * aspect + sin(tl * 0.6 + fi) * 0.03, fract(hash(vec2(fi, 143.0)) + tl * rise) - 0.5);
    float size = 0.002 + 0.005 * hash(vec2(fi, 144.0));
    world = mix(world, vec3(0.85, 0.85, 0.9), smoothstep(size, 0.0, length(c - pos)) * 0.8);
  }
  o = over(o, world, max(inside, enter) * fade);
  // strands of membrane across the opening, torn away as it widens
  float strand = smoothstep(0.1, 0.0, abs(fract(q.y * 8.0 + fbm(q * 5.0) * 2.0) - 0.5)) * inside * (1.0 - smoothstep(0.9, 2.1, tl));
  o = over(o, vec3(0.45, 0.1, 0.08), strand * 0.65 * fade);
  // its lips: white-hot right at the edge, burning red outside it, veins pulsing in the membrane round it
  float pulse = 0.75 + 0.25 * sin(tl * 7.0);
  float gap = max(dx, 0.0);
  float edge0 = abs(dx);
  float lips = (1.0 - enter) * fade * exp(-max(abs(q.y) - len, 0.0) * 30.0);
  float outside = smoothstep(-0.004, 0.004, dx);
  o = over(o, vec3(0.7, 0.06, 0.04), exp(-gap * 7.0) * 0.4 * open * lips * outside);
  float veins = smoothstep(0.035, 0.0, abs(fbm(q * 9.0 + vec2(0.0, tl * 0.15)) - 0.5)) * exp(-gap * 9.0) * (0.3 + along);
  o = over(o, vec3(0.65, 0.05, 0.07), veins * 0.8 * open * pulse * lips * outside);
  o = over(o, vec3(1.0, 0.25, 0.08), exp(-edge0 * 90.0) * pulse * (0.4 + 0.6 * open) * lips);
  o = over(o, vec3(1.0, 0.82, 0.55), exp(-edge0 * 400.0) * (0.5 + 0.5 * open) * lips);
  // red light spilling out of it onto the inside of the opening
  o = over(o, vec3(0.9, 0.15, 0.08), exp(-edge0 * 25.0) * 0.35 * inside * lips);
  // the crossing: a red shudder
  o = over(o, vec3(0.75, 0.08, 0.06), exp(-abs(tl - 2.85) * 10.0) * 0.45 * fade);
