// Steam blast — a celebration over the whole stage (gl_FragCoord, u_res, u_age, 3 s): a blast of steam rising
  // from the reward, bolts and little gears thrown out spinning and falling back.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.1, age);
  vec2 q = c - vec2(0.0, -0.1);
  float plume = fbm(vec2(q.x * 5.0, q.y * 3.0 - age * 2.5)) * smoothstep(0.1 + q.y * 0.5, 0.0, abs(q.x)) * step(0.0, q.y) * smoothstep(0.0, 0.4, age);
  o = over(o, vec3(0.92, 0.9, 0.86), plume * 0.85 * fade);
  for (int k = 0; k < 26; k++) {
    float fk = float(k);
    float ang = 1.5708 + (hash(vec2(fk, 1.0)) - 0.5) * 2.6;
    float speed = 0.5 + 0.6 * hash(vec2(fk, 2.0));
    vec2 at = vec2(0.0, -0.1) + vec2(cos(ang), sin(ang)) * speed * age + vec2(0.0, -0.5 * age * age);
    vec2 rq = c - at;
    float spin = age * (5.0 + 5.0 * hash(vec2(fk, 3.0)));
    float a = atan(rq.y, rq.x) + spin;
    float r = length(rq);
    float size = 0.012 + 0.01 * hash(vec2(fk, 4.0));
    float gear = smoothstep(0.002, 0.0, r - size - 0.004 * step(0.0, sin(a * 8.0))) - smoothstep(0.002, 0.0, r - size * 0.4);
    float bolt = smoothstep(0.002, 0.0, max(abs(rq.x), abs(rq.y)) - size * 0.7);
    float shape = mix(gear, bolt, step(0.6, hash(vec2(fk, 5.0))));
    o = over(o, mix(vec3(0.85, 0.6, 0.25), vec3(0.7, 0.4, 0.2), hash(vec2(fk, 6.0))), clamp(shape, 0.0, 1.0) * fade);
  }
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
