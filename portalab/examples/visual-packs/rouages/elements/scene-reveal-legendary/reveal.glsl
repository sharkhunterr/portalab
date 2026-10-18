// A legendary card turned: a giant clockwork turning behind it, blue arcs leaping from coils, a golden flash
  // and a rain of sparks (u_age, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float r = length(c);
  float a = atan(c.y, c.x);
  float big = smoothstep(0.004, 0.0, abs(r - 0.42 - 0.02 * step(0.0, sin((a + age * 0.6) * 24.0)))) + smoothstep(0.004, 0.0, abs(r - 0.36));
  big += smoothstep(0.006, 0.0, abs(sin((a + age * 0.6) * 4.0)) * r) * step(0.2, r) * step(r, 0.36);
  o = over(o, vec3(1.0, 0.8, 0.4), clamp(big, 0.0, 1.0) * 0.8 * fade);
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float t0 = 0.3 + fk * 0.45;
    float on = step(t0, age) * step(age, t0 + 0.25);
    float dir = hash(vec2(fk, 4.0)) * 6.2832;
    float seg = floor(r * 18.0);
    float jag = dir + 0.3 * (hash(vec2(fk, seg + floor(age * 24.0))) - 0.5);
    float arc = smoothstep(0.005, 0.0, abs(sin(a - jag)) * r) * step(0.2, r) * step(r, 0.6) * step(0.0, cos(a - jag));
    o = over(o, vec3(0.6, 0.85, 1.0), arc * on);
    o = over(o, vec3(0.4, 0.7, 1.0), on * exp(-r * 4.0) * 0.3);
  }
  o = over(o, vec3(1.0, 0.9, 0.6), exp(-r * 7.0) * 0.7 * fade);
  for (int k = 0; k < 28; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 1.0)) - 0.5) * 1.2, 0.55 - fract(age * (0.3 + 0.3 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0))) * 1.2);
    o = over(o, vec3(1.0, 0.8, 0.4), exp(-length(c - sp) * 260.0) * step(0.5, age) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
