// An epic card turned: a swarm of bats bursting out from behind it in a violet glow (u_age: seconds, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.5, age) * smoothstep(0.0, 0.15, age);
  o = over(o, vec3(0.6, 0.25, 0.95), exp(-length(c) * 4.0) * 0.55 * fade);
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 b = vec2(cos(ang), sin(ang) * 0.8) * age * (0.25 + 0.3 * hash(vec2(fk, 2.0))) + vec2(0.0, age * age * 0.05);
    vec2 q = (c - b) * (55.0 + 25.0 * hash(vec2(fk, 3.0)));
    float flap = sin(age * 28.0 + fk * 1.9);
    float wing = step(abs(q.x), 2.2) * smoothstep(0.4, 0.0, abs(q.y - abs(q.x) * 0.45 * flap - 0.25 * sin(abs(q.x) * 3.0)));
    float body = smoothstep(0.5, 0.3, length(q * vec2(1.4, 0.9)));
    o = over(o, vec3(0.04, 0.0, 0.06), clamp(wing + body, 0.0, 1.0) * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
