// Céleste — the supernova (u_age: seconds, 2.4 s): the pack's light drawn into a throbbing core, the flash at
  // 1.1 s, a shockwave ring in nebula colours, rays turning, stardust thrown out and slowing.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float boom = 1.1;
  float r = length(c) + 0.001;
  float a = atan(c.y, c.x);
  // before: light drawn inward, the core throbbing faster
  float pull = smoothstep(0.0, boom, age) * step(age, boom + 0.05);
  float inward = fract(r * 6.0 + age * 3.0);
  o = over(o, vec3(0.7, 0.6, 1.0), smoothstep(0.1, 0.0, abs(inward - 0.5)) * smoothstep(0.6, 0.05, r) * pull * 0.35);
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-r * (40.0 - 25.0 * pull)) * (0.6 + 0.4 * sin(age * age * 30.0)) * pull);
  if (age > boom) {
    float s = age - boom;
    float fade = smoothstep(1.3, 0.6, s);
    o = over(o, vec3(1.0), exp(-r * 6.0) * smoothstep(0.35, 0.0, s));
    // the shockwave: a ring of nebula colours rolling out, broken by the noise
    float front = 0.05 + s * 0.75;
    float shell = smoothstep(0.06, 0.0, abs(r - front - 0.03 * fbm(vec2(a * 3.0, s * 2.0))));
    vec3 hue = mix(vec3(1.0, 0.45, 0.75), vec3(0.35, 0.75, 1.0), 0.5 + 0.5 * sin(a * 2.0 + s));
    o = over(o, hue, shell * fade);
    o = over(o, mix(vec3(0.5, 0.2, 0.7), vec3(0.15, 0.5, 0.7), 0.5 + 0.5 * sin(a)), smoothstep(front, front * 0.3, r) * fbm(c * 5.0 + s) * 0.5 * fade);
    // rays
    float rays = pow(0.5 + 0.5 * sin(a * 16.0 + s * 1.5), 10.0);
    o = over(o, vec3(1.0, 0.92, 0.8), rays * smoothstep(0.7, 0.05, r) * 0.5 * fade);
    // stardust thrown out, slowing
    for (int k = 0; k < 40; k++) {
      float fk = float(k);
      float ang = hash(vec2(fk, 1.0)) * 6.2832;
      float speed = 0.3 + 0.7 * hash(vec2(fk, 2.0));
      vec2 grain = vec2(cos(ang), sin(ang)) * speed * (1.0 - exp(-s * 2.5)) * 0.6;
      float size = 0.003 + 0.004 * hash(vec2(fk, 3.0));
      o = over(o, mix(vec3(1.0, 0.85, 0.6), vec3(0.7, 0.85, 1.0), hash(vec2(fk, 4.0))), smoothstep(size, 0.0, length(c - grain)) * fade);
    }
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
