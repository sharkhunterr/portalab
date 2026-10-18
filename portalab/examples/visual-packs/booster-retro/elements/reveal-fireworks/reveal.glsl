vec2 c = floor(((gl_FragCoord.xy - 0.5 * u_res) / u_res.y) * 90.0) / 90.0;
  // A legendary card turned: level clear — rainbow bands scrolling behind it, pixel fireworks bursting one after
  // the other, a shower of stars falling (u_age: seconds, 3.0 s).
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.15, age);
  float bands = floor(fract((c.y - c.x * 0.3) * 4.0 - age * 1.5) * 6.0);
  vec3 rainbow = bands < 0.5 ? vec3(1.0, 0.3, 0.4) : bands < 1.5 ? vec3(1.0, 0.65, 0.2) : bands < 2.5 ? vec3(1.0, 0.9, 0.25) : bands < 3.5 ? vec3(0.3, 0.85, 0.4) : bands < 4.5 ? vec3(0.25, 0.65, 1.0) : vec3(0.5, 0.35, 1.0);
  float behind = step(length(c * vec2(1.0, 0.8)), 0.5) * step(0.22, length(c * vec2(1.0, 0.8)));
  o = over(o, rainbow, behind * 0.6 * smoothstep(0.0, 0.4, age) * fade);
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float s = age - 0.25 - fk * 0.45;
    vec2 centre = vec2((hash(vec2(fk, 1.0)) - 0.5) * 0.7, 0.1 + (hash(vec2(fk, 2.0)) - 0.5) * 0.6);
    vec3 col = fk < 1.5 ? vec3(1.0, 0.4, 0.6) : fk < 3.5 ? vec3(0.4, 1.0, 0.6) : vec3(1.0, 0.9, 0.3);
    for (int j = 0; j < 12; j++) {
      float fj = float(j);
      float ang = fj / 12.0 * 6.2832;
      vec2 at = floor((centre + vec2(cos(ang), sin(ang)) * s * 0.3 + vec2(0.0, -0.2 * s * s)) * 90.0) / 90.0;
      vec2 q = abs(c - at) * 90.0;
      o = over(o, col, step(q.x, 1.1) * step(q.y, 1.1) * step(0.0, s) * step(s, 0.9) * fade);
    }
  }
  for (int k = 0; k < 20; k++) {
    float fk = float(k);
    vec2 at = floor(vec2((hash(vec2(fk, 3.0)) - 0.5) * 1.2, 0.55 - fract(age * (0.3 + 0.2 * hash(vec2(fk, 4.0))) + hash(vec2(fk, 5.0))) * 1.2) * 90.0) / 90.0;
    vec2 q = abs(c - at) * 90.0;
    o = over(o, vec3(1.0, 0.95, 0.5), clamp(step(q.x + q.y, 1.6), 0.0, 1.0) * step(0.6, age) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
