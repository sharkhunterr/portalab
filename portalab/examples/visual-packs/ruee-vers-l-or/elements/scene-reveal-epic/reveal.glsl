// An epic card turned: shots ringing out round it — muzzle flashes, ricochet sparks, gunsmoke drifting
  // (u_age, 2.2 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.2, 1.6, age) * smoothstep(0.0, 0.1, age);
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    float s = age - fk * 0.22;
    float ang = hash(vec2(fk, 1.0)) * 6.2832;
    vec2 at = vec2(cos(ang) * 0.32, sin(ang) * 0.42);
    o = over(o, vec3(1.0, 0.85, 0.4), exp(-length(c - at) * 60.0) * exp(-max(s, 0.0) * 20.0) * step(0.0, s) * fade);
    for (int j = 0; j < 5; j++) {
      float fj = float(j);
      float sa = ang + 3.1416 + (hash(vec2(fk, fj + 2.0)) - 0.5) * 1.5;
      vec2 sp = at + vec2(cos(sa), sin(sa)) * s * 0.4;
      o = over(o, vec3(1.0, 0.75, 0.3), exp(-length(c - sp) * 350.0) * step(0.0, s) * step(s, 0.4) * fade);
    }
    o = over(o, vec3(0.7, 0.68, 0.65), fbm((c - at) * 10.0 + s) * smoothstep(0.1 + s * 0.15, 0.0, length(c - at)) * step(0.0, s) * smoothstep(1.2, 0.2, s) * 0.5 * fade);
  }
  // its edges fade out: an ellipse inside its box, reaching close to its sides yet never showing them
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edgeuv));
