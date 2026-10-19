// The towers HD — a level-up over the whole stage (gl_FragCoord, u_res, u_age), seen round the card on every
  // screen: below it, a wall of bricks built row after row (each brick dropping with gravity and clicking in with
  // a flash); above it, an arch of bricks closing in from both sides; at 2.2 s a gold keystone drops into the top
  // and studs spray out of it; a warm glow behind the card.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.3, tl) * smoothstep(6.8, 5.8, tl);
  o = over(o, vec3(1.0, 0.9, 0.6), exp(-length(c * vec2(0.8, 1.0)) * 2.5) * 0.3 * smoothstep(1.6, 2.4, tl) * fade);
  // the wall below: four rows in running bond
  float bw = 0.1;
  float bh = 0.05;
  for (int r = 0; r < 4; r++) {
    float fr = float(r);
    float shift = 0.5 * bw * mod(fr, 2.0);
    float col = floor((c.x + shift) / bw);
    float cx = col * bw - shift + bw * 0.5;
    float when = 0.1 + fr * 0.38 + hash(vec2(col, fr)) * 0.3;
    float since = tl - when;
    float landY = -0.42 + fr * bh + bh * 0.5;
    float y = landY + max(0.0, 0.8 - since * since * 9.0) * step(since, 0.3);
    vec2 q = c - vec2(cx, y);
    float body = step(abs(q.x), bw * 0.47) * step(abs(q.y), bh * 0.46);
    float studs = step(bh * 0.46, q.y) * step(q.y, bh * 0.75) * step(abs(q.x), bw * 0.47) * step(abs(fract(q.x / (bw * 0.5) + 0.5) - 0.5), 0.27);
    float hh = hash(vec2(col, fr + 5.0));
    vec3 bc = hh < 0.3 ? vec3(0.84, 0.16, 0.16) : (hh < 0.55 ? vec3(0.12, 0.44, 0.84) : (hh < 0.8 ? vec3(0.97, 0.77, 0.12) : vec3(0.95, 0.95, 0.92)));
    bc *= 0.72 + 0.4 * smoothstep(-bh * 0.5, bh * 0.5, q.y);
    float top = step(fr, 2.5);
    o = over(o, bc, clamp(body + studs * (1.0 - top * step(0.0, tl - 0.1 - (fr + 1.0) * 0.38 - 0.3)), 0.0, 1.0) * step(0.0, since) * fade);
    o = over(o, vec3(1.0), exp(-length(q) * 30.0) * exp(-max(since - 0.3, 0.0) * 12.0) * step(0.3, since) * 0.45 * fade);
  }
  // the arch above: eleven bricks along a half circle, closing in from both ends, a gold keystone last
  for (int k = 0; k < 11; k++) {
    float fk = float(k);
    float ang = 3.1416 * (0.08 + 0.84 * fk / 10.0);
    vec2 slot = vec2(cos(ang) * 0.44, 0.1 + sin(ang) * 0.23);
    float order = min(fk, 10.0 - fk);
    float key = step(4.5, fk) * step(fk, 5.5);
    float when = 0.4 + order * 0.32 + key * 0.3;
    float since = tl - when;
    vec2 at = slot + vec2(0.0, max(0.0, 0.7 - since * since * 8.0) * step(since, 0.3));
    vec2 q = c - at;
    float rot = ang - 1.5708;
    q = mat2(cos(rot), sin(rot), -sin(rot), cos(rot)) * q;
    float body = step(abs(q.x), 0.06) * step(abs(q.y), 0.026);
    float studs = step(0.026, q.y) * step(q.y, 0.038) * step(abs(q.x), 0.06) * step(abs(fract(q.x / 0.03 + 0.5) - 0.5), 0.27);
    float hh = hash(vec2(fk, 9.0));
    vec3 bc = hh < 0.33 ? vec3(0.84, 0.16, 0.16) : (hh < 0.66 ? vec3(0.12, 0.44, 0.84) : vec3(0.97, 0.77, 0.12));
    bc = mix(bc, vec3(1.0, 0.8, 0.28), key);
    bc *= 0.72 + 0.4 * smoothstep(-0.026, 0.026, q.y);
    bc += vec3(1.0, 0.95, 0.75) * key * exp(-abs(q.x + q.y - mod(tl, 1.5) * 0.2 + 0.1) * 30.0) * 0.6;
    o = over(o, bc, clamp(body + studs, 0.0, 1.0) * step(0.0, since) * fade);
    o = over(o, vec3(1.0), exp(-length(c - slot) * 25.0) * exp(-max(since - 0.3, 0.0) * 10.0) * step(0.3, since) * (0.4 + 0.6 * key) * fade);
  }
  // studs spraying out of the keystone
  float burst = tl - 2.35;
  if (burst > 0.0) {
    for (int k = 0; k < 28; k++) {
      float fk = float(k);
      float ang = hash(vec2(fk, 7.0)) * 6.2832;
      vec2 at = vec2(0.0, 0.33) + vec2(cos(ang), sin(ang) * 0.8 + 0.4) * burst * (0.5 + 0.6 * hash(vec2(fk, 8.0))) + vec2(0.0, -0.8 * burst * burst);
      float hh = hash(vec2(fk, 9.0));
      vec3 sc = hh < 0.33 ? vec3(0.95, 0.25, 0.25) : (hh < 0.66 ? vec3(0.3, 0.6, 1.0) : vec3(1.0, 0.85, 0.3));
      o = over(o, sc, smoothstep(0.013, 0.009, length((c - at) * vec2(1.0, 1.3))) * smoothstep(2.4, 1.4, burst) * fade);
    }
  }
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
