// Odyssée — the jump (u_age: seconds, 2.8 s): jets of steam venting from its seams, the locks' sparks; at 1.6 s
  // the stars stretch into hyperspace streaks rushing out from the middle, a white flash at 1.9 s, then they ebb.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  // steam venting sideways from its seams, puffing
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float side = fk < 1.5 ? -1.0 : 1.0;
    vec2 seam = vec2(side * 0.12, 0.12 - mod(fk, 2.0) * 0.2);
    vec2 q = c - seam;
    float jet = smoothstep(0.0, 0.25, q.x * side) * exp(-abs(q.y) * (30.0 - 18.0 * clamp(q.x * side * 4.0, 0.0, 1.0)));
    float puff = fbm(vec2(q.x * 10.0 - age * 6.0 * side, q.y * 12.0)) * smoothstep(0.35, 0.0, q.x * side);
    float on = smoothstep(0.2, 0.4, age) * smoothstep(1.7, 1.4, age) * (0.6 + 0.4 * step(0.5, fract(age * 3.0 + fk * 0.3)));
    o = over(o, vec3(0.85, 0.92, 1.0), jet * puff * on * 0.9);
  }
  // sparks from the locks
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float tt = age - 0.2 - 0.3 * hash(vec2(fk, 1.0));
    vec2 sp = vec2((hash(vec2(fk, 2.0)) - 0.5) * 0.3, 0.2) + vec2((hash(vec2(fk, 3.0)) - 0.5) * 0.5, 0.4) * tt - vec2(0.0, 0.8 * tt * tt);
    o = over(o, vec3(1.0, 0.8, 0.4), exp(-length(c - sp) * 260.0) * step(0.0, tt) * step(tt, 0.6));
  }
  // the hyperspace streaks
  float jump = smoothstep(1.4, 1.9, age) * smoothstep(2.8, 2.2, age);
  float a = atan(c.y, c.x);
  float r = length(c);
  float lane = floor(a / 6.2832 * 140.0);
  float speed = 0.6 + hash(vec2(lane, 1.0));
  float head = fract(hash(vec2(lane, 2.0)) + age * speed * 1.6);
  float streak = smoothstep(0.012, 0.0, abs(fract(a / 6.2832 * 140.0) - 0.5) * r * 0.05) * smoothstep(head - 0.25 * jump - 0.02, head, r) * step(r, head) * step(0.5, hash(vec2(lane, 3.0)));
  o = over(o, mix(vec3(0.6, 0.85, 1.0), vec3(1.0), hash(vec2(lane, 4.0))), streak * jump);
  o = over(o, vec3(0.5, 0.8, 1.0), exp(-r * 4.0) * jump * 0.5);
  o = over(o, vec3(1.0), exp(-pow((age - 1.9) * 8.0, 2.0)) * exp(-r * 2.0));
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
