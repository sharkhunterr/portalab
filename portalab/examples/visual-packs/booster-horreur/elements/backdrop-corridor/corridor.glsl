// Horreur — the booster stage at the end of a corridor: a bulb buzzing and dying, the walls closing in, grain,
  // streaks running down, a red pulse at the edges like a racing heart, and now and then — as the light comes
  // back — a figure standing at the far end (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  // the bulb: buzzing, dying for a moment now and then
  float buzz = 0.82 + 0.18 * noise(vec2(t * 40.0, 1.0));
  float dying = step(0.82, noise(vec2(t * 2.3, 7.0)));
  float light = buzz * (1.0 - 0.92 * dying);
  // the corridor: walls converging on a far doorway
  float depth = 1.0 / (abs(c.x) * 1.6 + 0.35);
  vec3 wall = mix(vec3(0.04, 0.035, 0.03), vec3(0.16, 0.14, 0.11), smoothstep(0.0, 1.0, c.y + 0.6));
  float stains = fbm(vec2(c.x * 6.0 * depth, c.y * 3.0));
  o = over(o, wall * (0.5 + stains * 0.6), 1.0);
  float door = step(abs(c.x), 0.11) * step(abs(c.y + 0.02), 0.2);
  o = over(o, vec3(0.0), door * 0.92);
  // the bulb's cone from above
  vec2 b = c - vec2(0.0, 0.42);
  o = over(o, vec3(1.0, 0.85, 0.55), exp(-length(b) * 9.0) * light);
  float cone = smoothstep(0.45, 0.0, abs(c.x) - (0.42 - c.y) * 0.35) * smoothstep(0.42, -0.5, c.y);
  o.rgb *= 0.25 + 0.75 * mix(0.2, 1.0, cone) * light;
  // something at the far end: a few seconds in some, it stands in the doorway — seen as the light flickers
  float window = floor(t / 6.0);
  float there = step(0.55, hash(vec2(window, 3.0))) * smoothstep(0.0, 0.4, fract(t / 6.0)) * smoothstep(1.0, 0.7, fract(t / 6.0));
  vec2 f = c - vec2(0.012 * (hash(vec2(window, 5.0)) - 0.5), -0.06);
  float head = smoothstep(0.022, 0.018, length(f - vec2(0.0, 0.1)));
  float body = smoothstep(0.012, 0.0, max(abs(f.x) - 0.035 + f.y * 0.06, abs(f.y + 0.03) - 0.11));
  o = over(o, vec3(0.0), clamp(head + body, 0.0, 1.0) * there * (0.5 + 0.5 * light));
  o = over(o, vec3(0.9, 0.05, 0.05), smoothstep(0.004, 0.0, length(f - vec2(-0.008, 0.103))) * there + smoothstep(0.004, 0.0, length(f - vec2(0.008, 0.103))) * there);
  // blood running down from the top: a pooled edge, then runs of uneven width that wobble as they go, a drop
  // swelling at each tip until it falls
  o = over(o, vec3(0.22, 0.0, 0.015), smoothstep(0.455, 0.5, c.y) * (0.55 + 0.45 * noise(vec2(c.x * 22.0, 1.0))));
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float x0 = -0.92 + fk * 0.245 + 0.08 * hash(vec2(fk, 1.0));
    float cycle = fract(t * (0.01 + 0.018 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0)));
    float len = 0.06 + 0.48 * cycle;
    float below = 0.48 - c.y;
    float wob = 0.014 * (noise(vec2(fk * 7.0, c.y * 7.0)) - 0.5) + 0.003 * sin(c.y * 37.0 + fk);
    float width = mix(0.011, 0.0035, smoothstep(0.0, len, below)) * (0.7 + 0.6 * hash(vec2(fk, 4.0)));
    float dx = c.x - x0 - wob;
    float run = smoothstep(width, width * 0.45, abs(dx)) * step(0.0, below) * step(below, len);
    vec2 tip = vec2(x0 + 0.014 * (noise(vec2(fk * 7.0, (0.48 - len) * 7.0)) - 0.5), 0.48 - len);
    float swell = fract(cycle * 4.0);
    float rad = 0.005 + 0.007 * swell;
    float drop = smoothstep(rad, rad * 0.55, length((c - tip - vec2(0.0, -rad * 0.4)) * vec2(1.0, 0.82)));
    vec2 falling = tip - vec2(0.0, 0.01 + swell * swell * 2.5);
    float droplet = smoothstep(0.005, 0.0025, length((c - falling) * vec2(1.0, 0.55))) * step(swell, 0.18);
    float blood = clamp(run + drop + droplet, 0.0, 1.0);
    o = over(o, vec3(0.3, 0.0, 0.02), blood * 0.95);
    // the wet gleam along its left side
    o = over(o, vec3(0.75, 0.2, 0.2), smoothstep(width * 0.3, 0.0, abs(dx + width * 0.4)) * run * 0.45 * light);
    o = over(o, vec3(0.9, 0.4, 0.4), smoothstep(rad * 0.35, 0.0, length(c - tip - vec2(-rad * 0.35, rad * 0.1))) * 0.6 * light);
  }
  // grain, and the red pulse at the edges — a heart racing
  o.rgb += (hash(gl_FragCoord.xy + floor(t * 24.0)) - 0.5) * 0.09;
  float pulse = pow(0.5 + 0.5 * sin(t * 6.8), 6.0);
  float edge = smoothstep(0.35, 0.95, length(c * vec2(0.75, 1.0)));
  o = over(o, vec3(0.45, 0.0, 0.02), edge * (0.35 + 0.35 * pulse));
  o.rgb *= mix(0.25, 1.0, smoothstep(1.0, 0.25, length(c * vec2(0.7, 1.0))));
