// The towers HD — a level-up over the whole stage (gl_FragCoord, u_res, u_age): two towers building up on
  // each side of the card, brick after brick dropping with gravity and bouncing as it clicks in (a flash),
  // their colours in turn; at 2.2 s a gold brick crowns each and studs spray up; a warm glow behind the card.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.3, tl) * smoothstep(6.8, 5.8, tl);
  o = over(o, vec3(1.0, 0.9, 0.6), exp(-length(c * vec2(0.8, 1.0)) * 3.0) * 0.35 * smoothstep(1.8, 2.4, tl) * fade);
  for (int s = 0; s < 2; s++) {
    float side = s == 0 ? -1.0 : 1.0;
    for (int k = 0; k < 9; k++) {
      float fk = float(k);
      float when = 0.15 + fk * 0.22;
      float since = tl - when;
      float landY = -0.42 + fk * 0.075 + 0.0375;
      float y = landY + max(0.0, 0.9 - since * since * 7.0) * step(since, 0.36) + 0.012 * abs(sin(max(since - 0.36, 0.0) * 25.0)) * exp(-max(since - 0.36, 0.0) * 8.0);
      vec2 q = c - vec2(side * (0.45 + 0.02 * mod(fk, 2.0)), y);
      float body = step(abs(q.x), 0.075) * step(abs(q.y), 0.0375);
      float studs = step(0.0375, q.y) * step(q.y, 0.052) * step(abs(q.x), 0.075) * step(abs(fract(q.x / 0.0375 + 0.5) - 0.5), 0.28);
      float gold = step(7.5, fk);
      float hh = hash(vec2(fk, side));
      vec3 bc = hh < 0.33 ? vec3(0.84, 0.16, 0.16) : (hh < 0.66 ? vec3(0.12, 0.44, 0.84) : vec3(0.97, 0.77, 0.12));
      bc = mix(bc, vec3(1.0, 0.8, 0.3), gold);
      bc *= 0.75 + 0.35 * smoothstep(-0.0375, 0.0375, q.y) + 0.2 * exp(-abs(q.x + q.y - 0.02) * 30.0) * gold;
      o = over(o, bc, clamp(body + studs, 0.0, 1.0) * step(0.0, since) * fade);
      o = over(o, vec3(1.0), exp(-length(q) * 20.0) * exp(-max(since - 0.36, 0.0) * 12.0) * step(0.36, since) * 0.5 * fade);
    }
  }
  float burst = tl - 2.3;
  if (burst > 0.0) {
    for (int k = 0; k < 26; k++) {
      float fk = float(k);
      float ang = 1.5708 + (hash(vec2(fk, 7.0)) - 0.5) * 2.6;
      vec2 at = vec2(0.0, 0.1) + vec2(cos(ang), sin(ang)) * burst * (0.6 + 0.6 * hash(vec2(fk, 8.0))) + vec2(0.0, -0.7 * burst * burst);
      vec2 q = c - at;
      float hh = hash(vec2(fk, 9.0));
      vec3 sc = hh < 0.33 ? vec3(0.95, 0.25, 0.25) : (hh < 0.66 ? vec3(0.3, 0.6, 1.0) : vec3(1.0, 0.85, 0.3));
      o = over(o, sc, smoothstep(0.014, 0.01, length(q * vec2(1.0, 1.4))) * smoothstep(2.2, 1.2, burst) * fade);
    }
  }
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
