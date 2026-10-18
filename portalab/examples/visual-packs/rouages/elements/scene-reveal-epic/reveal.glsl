// An epic card turned: a storm of gears whirling round it, meshing and racing, steam between them (2.4 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.4, 1.7, age) * smoothstep(0.0, 0.2, age);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float orbit = age * 1.6 + fk * 0.785;
    vec2 centre = vec2(cos(orbit) * 0.33, sin(orbit) * 0.42);
    float rad = 0.05 + 0.025 * mod(fk, 3.0);
    vec2 q = c - centre;
    float a = atan(q.y, q.x) + (mod(fk, 2.0) < 0.5 ? 1.0 : -1.0) * age * 6.0;
    float r = length(q);
    float gear = smoothstep(0.003, 0.0, r - rad - 0.01 * step(0.0, sin(a * 10.0))) - smoothstep(0.003, 0.0, r - rad * 0.35);
    o = over(o, mix(vec3(0.75, 0.5, 0.2), vec3(1.0, 0.82, 0.45), hash(vec2(fk, 3.0))), clamp(gear, 0.0, 1.0) * fade);
  }
  o = over(o, vec3(0.9, 0.88, 0.84), fbm(c * 6.0 + age) * smoothstep(0.6, 0.25, length(c)) * smoothstep(0.15, 0.3, length(c)) * 0.4 * fade);
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
