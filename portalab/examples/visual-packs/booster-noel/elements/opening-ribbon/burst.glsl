// Noël — the gift opening (u_age: seconds, 2.4 s): a glow under the lid, then at 1.1 s a spray of golden stars,
  // snowflakes and confetti thrown up and falling back, a warm flash.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float pop = 1.1;
  o = over(o, vec3(1.0, 0.8, 0.45), exp(-dot(c, c) * 30.0) * smoothstep(0.0, pop, age) * 0.4);
  if (age > pop) {
    float s = age - pop;
    float fade = smoothstep(1.3, 0.7, s);
    o = over(o, vec3(1.0, 0.95, 0.8), exp(-length(c) * 7.0) * smoothstep(0.4, 0.0, s));
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
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
