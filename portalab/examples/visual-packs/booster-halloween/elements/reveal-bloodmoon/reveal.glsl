// A legendary card turned: a blood eclipse behind it — the moon turning red, its corona of fire, a red mist
  // swirling, embers rising (u_age: seconds, 2.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.8, 2.0, age) * smoothstep(0.0, 0.2, age);
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  float corona = fbm(vec2(a * 5.0, r * 8.0 - age * 2.0));
  float rim = 0.2 + 0.04 * corona;
  o = over(o, vec3(1.0, 0.35, 0.1), smoothstep(rim + 0.1, rim, r) * smoothstep(rim - 0.03, rim, r) * fade);
  float shadow = smoothstep(0.0, 1.0, age);
  o = over(o, mix(vec3(1.0, 0.95, 0.85), vec3(0.55, 0.04, 0.05), shadow), smoothstep(0.2, 0.19, r) * fade);
  float swirl = fbm(vec2(cos(a + age * 0.7), sin(a + age * 0.7)) * r * 4.0 + age * 0.3);
  o = over(o, vec3(0.8, 0.05, 0.1), smoothstep(0.4, 0.8, swirl) * smoothstep(0.9, 0.25, r) * smoothstep(0.18, 0.3, r) * 0.6 * fade);
  for (int k = 0; k < 26; k++) {
    float fk = float(k);
    float life = fract(age * (0.3 + 0.2 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 e = vec2((hash(vec2(fk, 3.0)) - 0.5) * 1.2 + 0.04 * sin(life * 10.0 + fk), -0.6 + life * 1.2);
    o = over(o, vec3(1.0, 0.5, 0.15), exp(-length(c - e) * 180.0) * smoothstep(1.0, 0.7, life) * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
