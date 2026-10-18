// A rare card turned: green will-o'-the-wisps circling it, trailing mist (u_age: seconds, 1.9 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(1.9, 1.3, age) * smoothstep(0.0, 0.15, age);
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    for (int j = 0; j < 8; j++) {
      float fj = float(j);
      float ang = age * 3.0 + fk * 1.5708 - fj * 0.09;
      vec2 w = vec2(cos(ang) * 0.34, sin(ang) * 0.44 + 0.03 * sin(age * 7.0 + fk));
      float trail = (1.0 - fj / 8.0);
      o = over(o, vec3(0.45, 1.0, 0.6), exp(-length(c - w) * (45.0 + fj * 6.0)) * trail * fade);
    }
  }
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
