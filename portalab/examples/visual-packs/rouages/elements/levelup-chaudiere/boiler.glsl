// Boiler overheating — a level-up over the whole stage (gl_FragCoord, u_res, u_age): gears bursting in and
  // racing, a gauge climbing into the red, steam blasting out, a brass ring opening for the new level.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float fade = smoothstep(0.0, 0.5, tl) * smoothstep(6.8, 5.6, tl);
  o = over(o, mix(vec3(0.08, 0.05, 0.02), vec3(0.18, 0.1, 0.04), smoothstep(-0.5, 0.5, c.y)), 0.82 * fade);
  float spin = tl * tl * 0.8;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    float ang0 = fk * 1.047;
    vec2 centre = vec2(cos(ang0), sin(ang0)) * mix(1.0, 0.42, smoothstep(0.0, 1.2, tl));
    float rad = 0.1 + 0.03 * mod(fk, 2.0);
    vec2 q = c - centre;
    float a = atan(q.y, q.x) + (mod(fk, 2.0) < 0.5 ? spin : -spin);
    float r = length(q);
    float gear = smoothstep(0.004, 0.0, r - rad - 0.015 * step(0.0, sin(a * 12.0))) - smoothstep(0.004, 0.0, r - rad * 0.35);
    o = over(o, mix(vec3(0.6, 0.4, 0.14), vec3(0.95, 0.75, 0.38), 0.5 + 0.5 * sin(a * 2.0)), clamp(gear, 0.0, 1.0) * fade);
  }
  float pressure = smoothstep(0.3, 2.2, tl);
  float r0 = length(c);
  float dial = smoothstep(0.012, 0.0, abs(r0 - 0.24)) + smoothstep(0.006, 0.0, abs(r0 - 0.2)) * step(0.0, c.y + 0.05);
  o = over(o, vec3(0.9, 0.7, 0.35), dial * fade);
  float needle = -2.4 + pressure * 3.6 + 0.08 * sin(tl * 30.0) * pressure;
  vec2 nd = vec2(cos(needle + 1.5708), sin(needle + 1.5708));
  float h = clamp(dot(c, nd), 0.0, 0.2);
  o = over(o, mix(vec3(1.0, 0.95, 0.85), vec3(1.0, 0.15, 0.1), pressure), smoothstep(0.006, 0.0, length(c - nd * h)) * fade);
  float burst = smoothstep(2.0, 2.4, tl) * smoothstep(4.5, 2.6, tl);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float dir = fk * 0.785 + 0.3;
    vec2 dv = vec2(cos(dir), sin(dir));
    float along = dot(c, dv);
    float across = abs(dot(c, vec2(-dv.y, dv.x)));
    float jet = smoothstep(0.03 + along * 0.25, 0.0, across) * step(0.22, along) * fbm(vec2(along * 6.0 - tl * 4.0, across * 10.0 + fk));
    o = over(o, vec3(0.92, 0.9, 0.86), jet * burst * 0.9 * fade);
  }
  float open = smoothstep(2.2, 3.0, tl);
  o = over(o, vec3(1.0, 0.85, 0.5), exp(-abs(r0 - 0.28 - 0.06 * open) * 50.0) * open * fade);
  o = over(o, vec3(1.0), exp(-abs(tl - 2.3) * 10.0) * 0.4 * fade);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
