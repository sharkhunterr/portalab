// A rare card turned: two premiere searchlights rising from below, sweeping and crossing on it, dust in their
  // light (u_age, 1.8 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.8, 1.2, age) * smoothstep(0.0, 0.12, age);
  for (int k = 0; k < 2; k++) {
    float sd = k == 0 ? -1.0 : 1.0;
    vec2 src = vec2(sd * 0.35, -0.5);
    float ang = 1.5708 - sd * (0.55 - 0.45 * sin(age * 2.2));
    vec2 dir = vec2(cos(ang), sin(ang));
    vec2 q = c - src;
    float along = dot(q, dir);
    float off = abs(dot(q, vec2(-dir.y, dir.x)));
    float beam = smoothstep(0.02 + along * 0.08, 0.0, off) * step(0.0, along) * smoothstep(1.1, 0.3, along);
    o = over(o, vec3(1.0, 0.95, 0.8), beam * (0.35 + 0.15 * fbm(c * 6.0 + age)) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
