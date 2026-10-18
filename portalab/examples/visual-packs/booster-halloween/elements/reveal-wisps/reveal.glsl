// A rare card turned: spectral green flames rising round it, will-o'-the-wisps circling through them, sparks
  // spat up (u_age: seconds, 2.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.0, 1.4, age) * smoothstep(0.0, 0.15, age);
  vec2 e = c / vec2(0.3, 0.38);
  float r = length(e);
  float a = atan(e.y, e.x);
  // the flames: a ring licking upward, its tongues in the noise
  float tongue = fbm(vec2(a * 3.0 + c.x * 4.0, c.y * 7.0 - age * 5.0));
  float ring = smoothstep(0.35, 0.0, abs(r - 1.05 - 0.25 * tongue * smoothstep(-0.2, 0.4, c.y)));
  float lick = smoothstep(0.4, 0.75, tongue + 0.25 * c.y);
  o = over(o, mix(vec3(0.1, 0.9, 0.45), vec3(0.75, 1.0, 0.8), lick), ring * lick * 0.85 * fade);
  o = over(o, vec3(0.2, 1.0, 0.5), smoothstep(1.4, 0.95, r) * smoothstep(0.7, 1.0, r) * 0.25 * fade);
  // the wisps, circling through the flames, trailing
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    for (int j = 0; j < 7; j++) {
      float fj = float(j);
      float ang = age * 3.2 + fk * 1.5708 - fj * 0.1;
      vec2 w = vec2(cos(ang) * 0.34, sin(ang) * 0.44 + 0.03 * sin(age * 7.0 + fk));
      o = over(o, vec3(0.5, 1.0, 0.65), exp(-length(c - w) * (48.0 + fj * 7.0)) * (1.0 - fj / 7.0) * fade);
    }
  }
  // sparks spat up
  for (int k = 0; k < 24; k++) {
    float fk = float(k);
    float life = fract(age * (0.7 + 0.5 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    float ang = hash(vec2(fk, 3.0)) * 6.2832;
    vec2 s = vec2(cos(ang) * 0.3, sin(ang) * 0.38) + vec2(0.02 * sin(life * 9.0 + fk), life * 0.25);
    o = over(o, vec3(0.8, 1.0, 0.85), exp(-length(c - s) * 260.0) * smoothstep(1.0, 0.5, life) * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
