  // A rare card turned: a crown of bubbles bursting out round it and popping, glittering (u_age: seconds).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.6, 1.1, age);
  float r = length(c);
  o = over(o, vec3(0.3, 0.85, 1.0), exp(-pow((r - 0.22 - age * 0.12) * 9.0, 2.0)) * 0.35 * fade);
  for (int k = 0; k < 22; k++) {
    float fk = float(k);
    float ang = fk / 22.0 * 6.2832 + hash(vec2(fk, 1.0)) * 0.5;
    float born = hash(vec2(fk, 2.0)) * 0.35;
    float s = max(age - born, 0.0);
    vec2 b = vec2(cos(ang), sin(ang)) * (0.2 + s * (0.25 + 0.2 * hash(vec2(fk, 3.0)))) + vec2(0.0, s * 0.08);
    float rad = (0.012 + 0.018 * hash(vec2(fk, 4.0))) * smoothstep(0.0, 0.25, s);
    float popped = step(0.6 + 0.6 * hash(vec2(fk, 5.0)), s);
    float dd = length(c - b);
    float ring = smoothstep(rad, rad * 0.7, dd) * (1.0 - smoothstep(rad * 0.8, rad * 0.35, dd) * 0.7);
    vec3 iris = 0.6 + 0.4 * cos(vec3(0.0, 2.1, 4.2) + ang * 2.0 + age * 3.0);
    o = over(o, mix(vec3(0.85, 1.0, 1.0), iris, 0.5), ring * (1.0 - popped) * fade);
    o = over(o, vec3(1.0), smoothstep(rad * 0.3, 0.0, length(c - b - vec2(-0.3, 0.3) * rad)) * (1.0 - popped) * fade);
    float spark = popped * smoothstep(0.02, 0.0, dd) * smoothstep(0.35, 0.0, s - 0.6 - 0.6 * hash(vec2(fk, 5.0)));
    o = over(o, vec3(1.0), spark * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.3, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.3, min(edgeuv.y, 1.0 - edgeuv.y));
