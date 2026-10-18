vec2 c = floor(((gl_FragCoord.xy - 0.5 * u_res) / u_res.y) * 90.0) / 90.0;
  // A rare card turned: pixel coins springing out round it, spinning, glinting (u_age: seconds, 1.8 s).
  float age = u_age;
  float fade = smoothstep(1.8, 1.2, age) * smoothstep(0.0, 0.1, age);
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    float ang = fk / 18.0 * 6.2832 + 0.2;
    float d = (1.0 - exp(-age * 3.0)) * (0.3 + 0.12 * hash(vec2(fk, 1.0)));
    vec2 at = floor((vec2(cos(ang), sin(ang) * 1.2) * d + vec2(0.0, -0.15 * age * age)) * 90.0) / 90.0;
    vec2 q = abs(c - at) * 90.0;
    float w = 2.1 * abs(cos(age * 9.0 + fk));
    float coin = step(q.x, w) * step(q.y, 2.1);
    float shine = step(q.x, w * 0.35) * step(q.y, 1.1);
    o = over(o, vec3(0.85, 0.55, 0.05), coin * fade);
    o = over(o, vec3(1.0, 0.9, 0.3), coin * step(q.x, w * 0.7) * fade);
    o = over(o, vec3(1.0), shine * step(0.6, abs(cos(age * 9.0 + fk))) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
