// An epic card turned: a nebula swirling open behind it, stars kindling in it (u_age: seconds, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.5, age) * smoothstep(0.0, 0.2, age);
  float r = length(c);
  float a = atan(c.y, c.x) + age * 0.8 - r * 3.0;
  vec2 q = vec2(cos(a), sin(a)) * r * 3.0;
  float cloud = fbm(q + age * 0.5);
  float open = smoothstep(0.1 + age * 0.35, 0.0, r - 0.05);
  o = over(o, mix(vec3(0.95, 0.35, 0.75), vec3(0.3, 0.6, 1.0), smoothstep(0.3, 0.7, cloud)), smoothstep(0.35, 0.8, cloud) * open * 0.75 * fade);
  vec2 g = c * 26.0;
  vec2 cell = floor(g);
  float born = step(0.9, hash(cell)) * smoothstep(0.15, 0.0, length(fract(g) - 0.5)) * step(hash(cell + 2.0) * 1.6, age);
  o = over(o, vec3(1.0, 0.95, 1.0), born * open * fade);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
