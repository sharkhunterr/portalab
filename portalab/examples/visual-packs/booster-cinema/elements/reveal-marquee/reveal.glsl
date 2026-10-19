// An epic card turned: a marquee of bulbs lighting up round it one after the other, then chasing, golden film
  // ribbons flying off (u_age, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.1, age);
  vec2 hb = vec2(0.3, 0.42);
  float a = atan(c.y, c.x) / 6.2832 + 0.5;
  float slot = floor(a * 40.0);
  vec2 bulbAt = vec2(cos((slot + 0.5) / 40.0 * 6.2832 - 3.1416), sin((slot + 0.5) / 40.0 * 6.2832 - 3.1416));
  bulbAt = bulbAt / max(abs(bulbAt.x) / hb.x, abs(bulbAt.y) / hb.y);
  float lit = step(slot / 40.0, age * 1.4) * (0.5 + 0.5 * step(0.5, fract(slot * 0.5 + age * 3.0)));
  float bulb = smoothstep(0.016, 0.008, length(c - bulbAt));
  o = over(o, vec3(1.0, 0.85, 0.45), bulb * lit * fade);
  o = over(o, vec3(1.0, 0.75, 0.3), exp(-length(c - bulbAt) * 60.0) * lit * 0.5 * fade);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float s = max(age - 0.5 - fk * 0.08, 0.0);
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 at = vec2(cos(ang), sin(ang)) * (0.45 + s * 0.35);
    vec2 r = c - at;
    float rot = ang + s * 3.0 + fk;
    r = mat2(cos(rot), -sin(rot), sin(rot), cos(rot)) * r;
    float ribbon = step(abs(r.x), 0.05) * smoothstep(0.012, 0.008, abs(r.y + 0.01 * sin(r.x * 60.0)));
    float holes = step(0.5, fract(r.x * 70.0)) * step(abs(r.y), 0.004);
    o = over(o, vec3(0.9, 0.7, 0.25), clamp(ribbon - holes, 0.0, 1.0) * step(0.001, s) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
