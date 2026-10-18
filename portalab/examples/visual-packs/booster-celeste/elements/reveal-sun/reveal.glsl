// A legendary card turned: a star kindling behind it — a corona of flares, turning rays, a ring sweeping the
  // stage, golden dust falling (u_age: seconds, 2.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.8, 2.0, age) * smoothstep(0.0, 0.15, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  float corona = fbm(vec2(a * 4.0, r * 6.0 - age * 1.5));
  float edge = 0.16 + 0.05 * corona;
  o = over(o, vec3(1.0, 0.6, 0.2), smoothstep(edge + 0.12, edge, r) * smoothstep(edge - 0.08, edge, r) * fade);
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-r * 8.0) * fade);
  float rays = pow(0.5 + 0.5 * sin(a * 10.0 + age * 0.8), 6.0) + 0.5 * pow(0.5 + 0.5 * sin(a * 17.0 - age), 10.0);
  o = over(o, vec3(1.0, 0.85, 0.45), rays * smoothstep(0.85, 0.15, r) * 0.45 * fade);
  // the ring sweeping out, tilted
  vec2 rc = vec2(c.x, c.y * 3.2);
  float ring = smoothstep(0.02, 0.0, abs(length(rc) - (0.2 + age * 0.35)));
  o = over(o, vec3(1.0, 0.9, 0.7), ring * smoothstep(1.6, 0.6, age) * fade);
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    float x = (hash(vec2(fk, 1.0)) - 0.5) * 1.4;
    float y = 0.6 - fract(age * (0.25 + 0.2 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0))) * 1.3;
    float size = 0.003 + 0.004 * hash(vec2(fk, 4.0));
    o = over(o, vec3(1.0, 0.85, 0.4), smoothstep(size, 0.0, length(c - vec2(x + 0.02 * sin(age * 3.0 + fk), y))) * step(0.4, age) * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
