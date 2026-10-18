// Gold Rush — the booster stage on Main Street at dusk: a burning sky, false-fronted buildings and the saloon
  // with its lanterns, a windmill turning, tumbleweeds rolling, a dust devil, vultures circling.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.95, 0.5, 0.2), vec3(0.3, 0.15, 0.3), smoothstep(-0.1, 0.5, c.y)), 1.0);
  o = over(o, vec3(1.0, 0.85, 0.45), exp(-length((c - vec2(0.2, -0.05)) * vec2(1.0, 1.4)) * 3.0) * 0.5);
  // the buildings, false fronts, their lit windows and the saloon's lanterns
  float ground = -0.3;
  float bx = floor((c.x + 1.0) * 5.0);
  float bh = ground + 0.18 + 0.12 * hash(vec2(bx, 1.0));
  float front = step(c.y, bh) * step(ground, c.y) * step(0.06, fract((c.x + 1.0) * 5.0));
  o = over(o, vec3(0.12, 0.06, 0.04), front);
  vec2 wq = fract(vec2((c.x + 1.0) * 15.0, (c.y - ground) * 18.0));
  float win = step(0.3, wq.x) * step(wq.x, 0.7) * step(0.3, wq.y) * step(wq.y, 0.75) * front * step(0.55, hash(floor(vec2((c.x + 1.0) * 15.0, (c.y - ground) * 18.0)))) * step(c.y, bh - 0.03);
  o = over(o, vec3(1.0, 0.7, 0.3), win * (0.7 + 0.3 * sin(t * 2.0 + bx)));
  // a windmill on the left, turning
  vec2 wm = c - vec2(-0.8, 0.0);
  float tower = smoothstep(0.004, 0.0, abs(wm.x) - 0.005 - (0.0 - wm.y) * 0.03) * step(ground, c.y) * step(wm.y, 0.0);
  float wa = atan(wm.y, wm.x) + t * 1.2;
  float blades = smoothstep(0.02, 0.0, abs(sin(wa * 4.0)) * length(wm)) * step(length(wm), 0.09);
  o = over(o, vec3(0.1, 0.05, 0.03), clamp(tower + blades, 0.0, 1.0));
  // the ground, a dust devil, tumbleweeds
  o = over(o, vec3(0.4, 0.22, 0.12), step(c.y, ground));
  vec2 dd = c - vec2(0.5 + 0.1 * sin(t * 0.3), ground);
  float devil = fbm(vec2(dd.x * 12.0 + t * 2.0, dd.y * 6.0)) * smoothstep(0.02 + dd.y * 0.15, 0.0, abs(dd.x + 0.02 * sin(dd.y * 30.0 + t * 4.0))) * step(0.0, dd.y) * smoothstep(0.45, 0.0, dd.y);
  o = over(o, vec3(0.8, 0.6, 0.4), devil * 0.6);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 tw = c - vec2(mod(t * (0.08 + 0.05 * fk) + fk * 1.1, 2.4) - 1.2, ground + 0.035 + 0.025 * abs(sin(t * 4.0 + fk)));
    float rr = length(tw);
    o = over(o, vec3(0.5, 0.36, 0.2), smoothstep(0.035, 0.03, rr) * (0.4 + 0.6 * step(0.5, fract(atan(tw.y, tw.x) * 3.0 + t * 5.0 + rr * 60.0))));
  }
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float ang = t * (0.2 + 0.05 * fk) + fk * 2.1;
    vec2 q = (c - vec2(-0.2 + fk * 0.3 + cos(ang) * 0.1, 0.35 + sin(ang) * 0.03)) * 80.0;
    o = over(o, vec3(0.08, 0.04, 0.03), step(abs(q.x), 3.0) * smoothstep(0.5, 0.0, abs(q.y - abs(q.x) * (0.25 + 0.1 * sin(t * 2.0 + fk)))));
  }
  o.rgb *= mix(0.45, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
