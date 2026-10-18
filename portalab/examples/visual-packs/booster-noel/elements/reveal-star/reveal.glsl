// A legendary card turned: the guiding star lighting up — long rays crossing, a golden halo, golden snow
  // falling (u_age: seconds, 2.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.8, 2.0, age) * smoothstep(0.0, 0.2, age);
  vec2 s = c - vec2(0.0, 0.08);
  float r = length(s) + 0.001;
  float a = atan(s.y, s.x);
  float cross_ = exp(-abs(s.x) * 90.0) * exp(-abs(s.y) * 2.5) + exp(-abs(s.y) * 90.0) * exp(-abs(s.x) * 3.5);
  float diag = exp(-abs(abs(s.x) - abs(s.y)) * 140.0) * exp(-r * 6.0);
  o = over(o, vec3(1.0, 0.92, 0.7), (cross_ + diag * 0.6) * fade);
  o = over(o, vec3(1.0, 0.8, 0.4), exp(-r * 5.0) * 0.6 * fade);
  float rays = pow(0.5 + 0.5 * sin(a * 12.0 + age * 0.6), 8.0);
  o = over(o, vec3(1.0, 0.85, 0.5), rays * smoothstep(0.8, 0.1, r) * 0.35 * fade);
  for (int k = 0; k < 34; k++) {
    float fk = float(k);
    float x = (hash(vec2(fk, 1.0)) - 0.5) * 1.5;
    float y = 0.65 - fract(age * (0.18 + 0.12 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0))) * 1.4;
    float size = 0.003 + 0.004 * hash(vec2(fk, 4.0));
    o = over(o, vec3(1.0, 0.88, 0.5), smoothstep(size, 0.0, length(c - vec2(x + 0.03 * sin(age * 2.0 + fk), y))) * step(0.3, age) * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
