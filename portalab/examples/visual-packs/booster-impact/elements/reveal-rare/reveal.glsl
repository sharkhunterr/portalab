// Impact — a rare card turned (u_age: seconds, 1.8 s), hard-edged: white speed lines shooting out from behind
  // it, and a shockwave rolling away as a ring of halftone dots, inked at its rim.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float a = atan(c.y, c.x);
  float on = step(0.05, age) * step(age, 1.5);
  vec3 ink = vec3(0.07, 0.02, 0.11);
  // speed lines, redrawn on each beat
  float beat = floor(age * 12.0);
  float lanes = a / 6.2832 * 56.0;
  float lid = floor(lanes);
  float head = 0.3 + fract(age * (0.8 + hash(vec2(lid, 2.0))) + hash(vec2(lid, 3.0))) * 0.6;
  float streak = step(head - 0.14, r) * step(r, head);
  float thin = step(abs(fract(lanes) - 0.5), 0.09);
  float pick = step(0.5, hash(vec2(lid, beat)));
  o = over(o, ink, step(abs(fract(lanes) - 0.5), 0.16) * streak * pick * on);
  o = over(o, vec3(1.0), thin * streak * pick * on);
  // the shockwave: a band of halftone dots rolling out, inked at its outer rim
  float wave = 0.2 + age * 0.5;
  float band = step(abs(r - wave), 0.05);
  vec2 g = gl_FragCoord.xy / (u_res.y * 0.028);
  g = vec2(g.x + g.y, g.y - g.x) * 0.7071;
  float dots = step(length(fract(g) - 0.5), 0.36);
  float life = step(age, 1.2);
  o = over(o, vec3(0.13, 0.75, 0.94), band * dots * life);
  o = over(o, ink, step(abs(r - wave - 0.055), 0.008) * life);
  o = over(o, vec3(1.0), step(abs(r - wave - 0.055), 0.004) * life);
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.82, length(edge));
