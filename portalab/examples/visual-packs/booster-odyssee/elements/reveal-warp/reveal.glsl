// A legendary card turned: it bursts out of a hyperspace tunnel — rings of light rushing past, star streaks,
  // a mothership's shadow passing overhead with its lights, a wide anamorphic flare, a shockwave
  // (u_age: seconds, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  // the tunnel: rings rushing out, swirling light
  float depth = 0.3 / r + age * 3.0;
  float rings = smoothstep(0.15, 0.0, abs(fract(depth) - 0.5) - 0.35);
  float swirl = fbm(vec2(a * 3.0 + age, depth * 0.5));
  float tunnel = smoothstep(0.08, 0.3, r) * smoothstep(1.4, 0.6, age);
  o = over(o, mix(vec3(0.2, 0.5, 1.0), vec3(0.8, 0.4, 1.0), swirl), (rings * 0.5 + swirl * 0.35) * tunnel * fade);
  // star streaks
  float lane = floor(a / 6.2832 * 120.0);
  float head = fract(hash(vec2(lane, 2.0)) + age * (1.0 + hash(vec2(lane, 1.0))));
  float streak = smoothstep(0.01, 0.0, abs(fract(a / 6.2832 * 120.0) - 0.5) * r * 0.06) * smoothstep(head - 0.3, head, r) * step(r, head) * step(0.55, hash(vec2(lane, 3.0)));
  o = over(o, vec3(0.85, 0.95, 1.0), streak * fade);
  // the mothership passing overhead: a huge dark wedge sliding across the top, its lights
  float pass = smoothstep(0.6, 2.4, age);
  vec2 m = c - vec2(-0.9 + pass * 1.8, 0.36);
  float ship = smoothstep(0.004, 0.0, max(abs(m.y) - 0.04 + m.x * 0.08, abs(m.x) - 0.45));
  o = over(o, vec3(0.04, 0.05, 0.08), ship * 0.92 * fade);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    o = over(o, mix(vec3(1.0, 0.5, 0.2), vec3(0.4, 0.9, 1.0), step(4.0, fk)), exp(-length(m - vec2(-0.38 + fk * 0.1, -0.03)) * 260.0) * step(0.5, fract(age * 2.0 + fk * 0.2)) * fade);
  }
  // the flare and the shockwave
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-r * 8.0) * 0.8 * fade);
  o = over(o, vec3(0.5, 0.8, 1.0), exp(-abs(c.y) * 150.0) * exp(-abs(c.x) * 3.0) * 0.9 * fade);
  o = over(o, vec3(0.7, 0.9, 1.0), smoothstep(0.015, 0.0, abs(r - (0.1 + age * 0.4))) * smoothstep(1.4, 0.6, age) * fade);
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
