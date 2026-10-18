// A rare card turned: a ring of steam widening round it, brass sparks springing out (u_age, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.2, age) * smoothstep(0.0, 0.1, age);
  float r = length(c * vec2(1.0, 0.8));
  float ring = smoothstep(0.08, 0.0, abs(r - 0.2 - age * 0.18)) * fbm(c * 9.0 + age);
  o = over(o, vec3(0.92, 0.9, 0.86), ring * fade);
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 sp = vec2(cos(ang), sin(ang)) * (0.22 + age * 0.3 * hash(vec2(fk, 2.0)));
    o = over(o, vec3(1.0, 0.8, 0.4), exp(-length(c - sp) * 260.0) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
