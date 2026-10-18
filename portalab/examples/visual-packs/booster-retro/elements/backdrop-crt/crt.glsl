// Rétro — the booster stage in an 8-bit platformer on a CRT: everything on a coarse pixel grid — a dithered
  // sky, clouds and hills scrolling in parallax, a brick floor, spinning coins, an invader stepping down, then
  // the tube's scanlines, its RGB mask and its curved, darker edges (a stage: gl_FragCoord, u_res, t).
  vec2 raw = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  // the tube's bulge
  vec2 bent = raw * (1.0 + 0.06 * dot(raw, raw));
  vec2 c = floor(bent * 80.0) / 80.0;
  // the sky: bands, dithered where they meet
  float band = (c.y + 0.5) * 6.0;
  float dither = step(0.5, fract((floor(bent.x * 80.0) + floor(bent.y * 80.0)) * 0.5));
  float level = floor(band + 0.5 * dither);
  vec3 sky = mix(vec3(0.36, 0.58, 0.98), vec3(0.15, 0.25, 0.75), clamp(level / 6.0, 0.0, 1.0));
  o = over(o, sky, 1.0);
  // clouds, scrolling slowly
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float cx = mod(fk * 0.8 - t * 0.04, 2.6) - 1.3;
    vec2 q = (c - vec2(cx, 0.28 + fk * 0.05)) * vec2(1.0, 1.6);
    float puff = step(length(q - vec2(-0.05, 0.0)), 0.05) + step(length(q - vec2(0.03, 0.02)), 0.06) + step(length(q - vec2(0.1, 0.0)), 0.045);
    o = over(o, vec3(1.0), clamp(puff, 0.0, 1.0));
  }
  // hills, faster
  float hx = c.x + t * 0.08;
  float hill = -0.18 + 0.1 * abs(sin(hx * 2.2)) + 0.04 * abs(sin(hx * 5.1));
  o = over(o, vec3(0.2, 0.62, 0.25), step(c.y, hill));
  o = over(o, vec3(0.13, 0.45, 0.18), step(c.y, hill) * step(0.5, fract((c.x + t * 0.08) * 20.0)) * step(hill - 0.03, c.y));
  // the brick floor, fastest
  float fx = c.x + t * 0.18;
  float floorline = -0.3;
  float brick = step(c.y, floorline);
  vec2 b = vec2(fx * 20.0 + step(0.5, fract(c.y * 10.0)) * 0.5, c.y * 10.0);
  float mortar = step(0.9, fract(b.x)) + step(0.85, fract(b.y));
  o = over(o, mix(vec3(0.75, 0.32, 0.12), vec3(0.3, 0.1, 0.03), clamp(mortar, 0.0, 1.0)), brick);
  o = over(o, vec3(0.95, 0.65, 0.35), step(abs(c.y - floorline + 0.006), 0.006));
  // coins spinning above the floor
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float cx = mod(fk * 0.45 - t * 0.18, 2.4) - 1.2;
    vec2 q = c - vec2(cx, -0.2 + 0.04 * sin(fk * 2.0));
    float w = 0.022 * abs(cos(t * 4.0 + fk));
    float coin = step(abs(q.x), w) * step(abs(q.y), 0.03);
    o = over(o, mix(vec3(1.0, 0.85, 0.2), vec3(0.85, 0.55, 0.05), step(abs(q.x), w * 0.4)), coin);
  }
  // an invader stepping down across the top
  float step8 = floor(t * 2.0);
  vec2 iv = vec2(mod(step8 * 0.05, 1.6) - 0.8, 0.42 - floor(step8 / 32.0) * 0.0);
  vec2 iq = floor((c - iv) * 80.0);
  float body = step(abs(iq.x), 4.0) * step(abs(iq.y), 2.0) - step(abs(iq.x - 0.0), 0.0) * 0.0;
  float eyes = step(abs(abs(iq.x) - 2.0), 0.0) * step(abs(iq.y - 1.0), 0.0);
  float legs = step(abs(abs(iq.x) - 3.0 + mod(step8, 2.0)), 0.0) * step(abs(iq.y + 3.0), 0.0);
  float horns = step(abs(abs(iq.x) - 3.0), 0.0) * step(abs(iq.y - 3.0), 0.0);
  o = over(o, vec3(0.6, 1.0, 0.4), clamp(body - eyes + legs + horns, 0.0, 1.0));
  // the tube: scanlines, the RGB mask, darker curved edges
  float scan = 0.8 + 0.2 * step(0.5, fract(gl_FragCoord.y * 0.33));
  float mask = 0.88 + 0.12 * step(0.66, fract(gl_FragCoord.x * 0.33));
  o.rgb *= scan * mask;
  float edge = smoothstep(0.62, 0.48, max(abs(bent.x) * 0.55, abs(bent.y)));
  o.rgb *= mix(0.15, 1.0, edge);
