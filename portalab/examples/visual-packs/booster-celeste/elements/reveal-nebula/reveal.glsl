// An epic card turned: a spiral galaxy wheeling behind it — two arms of dust and young blue stars round a
  // bright core — stars kindling with cross flares, a ring of light rolling out (u_age: seconds, 2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.4, 1.7, age) * smoothstep(0.0, 0.25, age);
  vec2 g = c * vec2(1.0, 1.6);
  float r = length(g) + 0.001;
  float a = atan(g.y, g.x) - age * 0.9;
  float arms = pow(0.5 + 0.5 * cos(2.0 * a - log(r) * 5.0), 3.0);
  float dust = fbm(vec2(a * 2.0, r * 9.0) + age * 0.2);
  float disc = smoothstep(0.98, 0.15, r);
  o = over(o, mix(vec3(0.85, 0.4, 0.9), vec3(0.4, 0.65, 1.0), smoothstep(0.1, 0.5, r)), arms * disc * (0.5 + 0.6 * dust) * 0.95 * fade);
  o = over(o, vec3(0.15, 0.05, 0.12), smoothstep(0.55, 0.75, dust) * arms * disc * 0.6 * fade);
  o = over(o, vec3(1.0, 0.92, 0.8), exp(-r * 12.0) * fade);
  // stars kindling in the arms, each with its cross flare
  vec2 cell = floor(c * 22.0);
  vec2 f = fract(c * 22.0) - 0.5;
  float born = step(0.88, hash(cell)) * step(hash(cell + 3.0) * 1.8, age) * disc;
  float flare = exp(-abs(f.x) * 30.0) * exp(-abs(f.y) * 6.0) + exp(-abs(f.y) * 30.0) * exp(-abs(f.x) * 6.0);
  o = over(o, vec3(0.85, 0.92, 1.0), (smoothstep(0.12, 0.0, length(f)) + flare * 0.5) * born * fade);
  // the ring of light
  float front = 0.12 + age * 0.4;
  o = over(o, vec3(0.75, 0.6, 1.0), smoothstep(0.02, 0.0, abs(length(c) - front)) * smoothstep(1.6, 0.6, age) * fade);
  // its edges fade out, narrowly: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.08, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.08, min(edgeuv.y, 1.0 - edgeuv.y));
