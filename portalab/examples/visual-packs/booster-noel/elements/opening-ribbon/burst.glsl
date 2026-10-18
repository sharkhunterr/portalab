// Noël — the gift opening (u_age: seconds, 2.6 s): light leaking under the lid as the bow comes undone, then
  // at 1.2 s, the lid off, beams rising out of the box and a spray of golden stars, snowflakes and confetti
  // thrown up from its rim and falling back.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float pop = 1.2;
  vec2 rim = vec2(0.0, 0.17);
  vec2 dv = c - rim;
  o = over(o, vec3(1.0, 0.88, 0.55), exp(-dv.y * dv.y * 1200.0) * smoothstep(0.25, 0.0, abs(dv.x) - 0.12) * smoothstep(0.7, pop, age) * 0.7);
  if (age > pop) {
    float s = age - pop;
    float fade = smoothstep(1.4, 0.8, s);
    // the beams, fanning up out of the box
    float ang = atan(dv.x, max(dv.y, 0.001));
    float beams = pow(0.5 + 0.5 * sin(ang * 14.0 + s * 0.6), 4.0) * step(0.0, dv.y);
    o = over(o, vec3(1.0, 0.93, 0.7), beams * smoothstep(0.0, 0.25, s) * exp(-length(dv) * 2.2) * smoothstep(0.0, 0.03, dv.y) * 0.6 * fade);
    o = over(o, vec3(1.0, 0.95, 0.8), exp(-length(dv * vec2(1.0, 2.0)) * 9.0) * smoothstep(0.5, 0.0, s));
    c = dv;
    for (int k = 0; k < 46; k++) {
      float fk = float(k);
      float ang = 1.5708 + (hash(vec2(fk, 1.0)) - 0.5) * 2.4;
      float speed = 0.5 + 0.6 * hash(vec2(fk, 2.0));
      vec2 at = vec2(cos(ang), sin(ang)) * speed * s * 1.1 + vec2(0.0, -0.75 * s * s);
      vec2 q = c - at;
      float kind = hash(vec2(fk, 3.0));
      float spin = s * (4.0 + 6.0 * hash(vec2(fk, 5.0)));
      vec2 rq = vec2(q.x * cos(spin) - q.y * sin(spin), q.x * sin(spin) + q.y * cos(spin));
      float shape;
      vec3 col;
      if (kind < 0.35) {
        // a five-pointed star
        float a = atan(rq.y, rq.x);
        float rr = 0.012 * (0.55 + 0.45 * cos(a * 5.0));
        shape = smoothstep(rr + 0.002, rr, length(rq));
        col = vec3(1.0, 0.85, 0.35);
      } else if (kind < 0.65) {
        // a snowflake: six thin arms
        float a = atan(rq.y, rq.x);
        float arms = smoothstep(0.25, 0.0, abs(sin(a * 3.0))) * smoothstep(0.014, 0.004, length(rq));
        shape = max(arms, smoothstep(0.004, 0.0, length(rq)));
        col = vec3(0.92, 0.97, 1.0);
      } else {
        // confetti: a tumbling strip
        shape = step(abs(rq.x), 0.008) * step(abs(rq.y), 0.0035 * (0.3 + 0.7 * abs(cos(spin))));
        col = kind < 0.8 ? vec3(1.0, 0.25, 0.3) : vec3(0.25, 0.9, 0.45);
      }
      o = over(o, col, shape * fade);
    }
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
