// A rare card turned: a lasso whirling round it and tightening, dust flying off (u_age, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.2, age) * smoothstep(0.0, 0.1, age);
  vec2 e = c / vec2(0.36 - age * 0.05, 0.14 - age * 0.015);
  float a = atan(e.y, e.x) + age * 10.0;
  float rope = smoothstep(0.12, 0.0, abs(length(e) - 1.0)) * (0.6 + 0.4 * step(0.5, fract(a * 6.0)));
  o = over(o, vec3(0.85, 0.65, 0.4), rope * fade);
  o = over(o, vec3(0.8, 0.6, 0.4), fbm(c * 8.0 + age * 2.0) * smoothstep(0.3, 0.0, abs(length(e) - 1.2)) * 0.4 * fade);
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
