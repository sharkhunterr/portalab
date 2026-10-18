// A rare card turned: a gold laurel wreath closing round it from both sides, a few leaves flying off (u_age,
  // 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.2, age) * smoothstep(0.0, 0.1, age);
  vec2 e = c / vec2(0.32, 0.44);
  float r = length(e);
  float a = atan(e.y, e.x);
  float close = smoothstep(0.0, 0.8, age) * 2.9;
  float leaves = step(0.5, fract(a * 7.0)) * smoothstep(0.06, 0.0, abs(r - 1.0 - 0.03 * sin(a * 44.0)));
  o = over(o, vec3(0.88, 0.7, 0.2), leaves * step(abs(abs(a) - 1.5708), close * 0.55 + 0.01) * step(0.12, abs(a - 1.5708)) * fade);
  for (int k = 0; k < 8; k++) {
    float fk = float(k);
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 at = vec2(cos(ang) * 0.32, sin(ang) * 0.44) * (1.0 + age * 0.4);
    vec2 q = mat2(cos(ang + age * 4.0), -sin(ang + age * 4.0), sin(ang + age * 4.0), cos(ang + age * 4.0)) * (c - at);
    o = over(o, vec3(0.5, 0.62, 0.25), smoothstep(1.0, 0.8, length(q / vec2(0.022, 0.008))) * smoothstep(0.6, 1.0, age) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
