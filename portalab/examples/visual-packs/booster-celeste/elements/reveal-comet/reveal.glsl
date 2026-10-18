// A rare card turned: a comet circling it once, its icy tail glittering behind (u_age: seconds, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.3, age) * smoothstep(0.0, 0.1, age);
  vec2 e = c / vec2(0.36, 0.46);
  float r = length(e);
  float a = atan(e.y, e.x);
  float head = 1.6 - age * 4.2;
  float behind = mod(a - head, 6.2832);
  float tail = smoothstep(2.6, 0.0, behind) * smoothstep(0.08, 0.0, abs(r - 1.0));
  o = over(o, vec3(0.55, 0.9, 1.0), tail * 0.7 * fade);
  vec2 hp = vec2(cos(head), sin(head)) * vec2(0.36, 0.46);
  o = over(o, vec3(0.95, 1.0, 1.0), exp(-length(c - hp) * 45.0) * fade);
  float glit = step(0.86, hash(floor(vec2(a * 30.0, r * 20.0)) + floor(age * 12.0)));
  o = over(o, vec3(1.0), glit * smoothstep(2.0, 0.0, behind) * smoothstep(0.12, 0.0, abs(r - 1.0)) * fade);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
