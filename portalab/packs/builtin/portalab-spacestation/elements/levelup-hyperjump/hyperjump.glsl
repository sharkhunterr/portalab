// Portalab — level_up/hyperjump: the « hyperjump » effect (spec 028, B2)
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float r = length(c) + 1e-4;
  float a = atan(c.y, c.x);
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.3, tl) * smoothstep(6.6, 5.4, tl);
  float speed = smoothstep(0.4, 2.5, tl) * (1.0 - smoothstep(2.65, 2.85, tl));
  float travel = 0.25 * tl + 2.2 * max(tl - 0.6, 0.0) * max(tl - 0.6, 0.0) * step(tl, 2.8);
  o = over(o, vec3(0.0, 0.01, 0.04), 0.55 * fade * step(tl, 2.8));
  // the stars, in rings of directions, sliding out along their rays; streaks as the speed grows
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 g = vec2(a / 6.2832 * (70.0 + fk * 50.0), log(r) * 5.0 - travel * (5.0 + fk * 2.0));
    vec2 id = floor(g);
    vec2 f = fract(g);
    float on = step(0.8, hash(id + fk * 13.0));
    float len = 0.04 + speed * 0.95;
    float lane = smoothstep(0.1, 0.0, abs(f.x - 0.5 - (hash(id + 3.0) - 0.5) * 0.6));
    float streak = lane * smoothstep(0.0, 0.03, f.y) * smoothstep(len, len * 0.3, f.y);
    vec3 sc = mix(vec3(0.85, 0.9, 1.0), vec3(0.45, 0.65, 1.0), speed * hash(id + 5.0));
    o = over(o, sc, on * streak * smoothstep(0.02, 0.15, r) * fade * step(tl, 2.85));
  }
  // the tunnel: rings of blue light rushing outwards, a glow at its far end
  float rings = pow(0.5 + 0.5 * sin(log(r) * 18.0 - tl * 26.0), 6.0) * smoothstep(0.05, 0.6, r);
  o = over(o, vec3(0.35, 0.55, 1.0), rings * speed * 0.2 * fade);
  o = over(o, vec3(0.75, 0.85, 1.0), exp(-r * 6.0) * speed * 0.8 * fade);
  float flash = exp(-abs(tl - 2.75) * 9.0);
  o = over(o, vec3(0.9, 0.95, 1.0), flash);
  // out of the jump: a nebula blooms in front, the stars still again
  float there = smoothstep(2.75, 3.6, tl) * fade;
  vec2 q = c * (1.4 - 0.25 * smoothstep(2.75, 6.0, tl));
  vec2 w = vec2(fbm(q * 2.0 + vec2(tl * 0.05, 0.0)), fbm(q * 2.0 + vec2(4.0, -tl * 0.04)));
  float gas = fbm(q * 2.5 + w * 2.0);
  float body = smoothstep(0.75, 0.1, length(q * vec2(0.8, 1.0)) + (gas - 0.5) * 0.7);
  vec3 neb = mix(vec3(0.5, 0.12, 0.65), vec3(1.0, 0.25, 0.55), smoothstep(0.4, 0.72, gas));
  neb = mix(neb, vec3(0.2, 0.85, 0.95), smoothstep(0.5, 0.85, w.x) * 0.7);
  neb = mix(neb, vec3(1.0, 0.92, 0.88), smoothstep(0.7, 0.95, gas) * 0.6);
  float lit = clamp((fbm(q * 2.5 + w * 2.0 - normalize(q + 1e-4) * 0.05) - gas) * 12.0 + 0.5, 0.0, 1.0);
  neb *= 0.8 + 0.6 * lit;
  float fil = 1.0 - abs(2.0 * fbm(q * 5.0 + w * 3.0) - 1.0);
  neb += vec3(1.0, 0.7, 0.9) * pow(fil, 8.0) * 0.5;
  o = over(o, neb, clamp(body * (0.55 + 0.45 * gas), 0.0, 0.95) * there);
  o = over(o, vec3(0.9, 0.95, 1.0), exp(-length(q) * 18.0) * there);
  vec2 sg = c * 38.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(1.0), step(0.985, sh) * smoothstep(0.35, 0.0, length(fract(sg) - 0.5)) * (0.6 + 0.4 * sin(tl * 3.0 + sh * 30.0)) * there);
