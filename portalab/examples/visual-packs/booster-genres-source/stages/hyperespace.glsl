// Hyperespace — the booster stage: twinkling stars, magenta and blue nebulas drifting, a ringed planet turning
  // slowly, now and then a shooting star (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.01, 0.015, 0.05, 1.0);
  vec2 q = c * 1.6 + vec2(t * 0.01, 0.0);
  float neb = fbm(q + fbm(q * 1.5));
  o = over(o, vec3(0.8, 0.2, 0.7), smoothstep(0.5, 0.85, neb) * 0.35);
  o = over(o, vec3(0.15, 0.3, 0.9), smoothstep(0.45, 0.8, fbm(q * 0.8 + 3.0)) * 0.35);
  for (int k = 0; k < 60; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 7.0)) - 0.5) * asp, (hash(vec2(fk, 8.0)) - 0.5));
    float tw = 0.4 + 0.6 * pow(0.5 + 0.5 * sin(t * (1.0 + 3.0 * hash(vec2(fk, 9.0))) + fk), 3.0);
    o = over(o, vec3(0.9, 0.95, 1.0), exp(-length(c - sp) * 900.0) * tw);
  }
  // the ringed planet
  vec2 pp = vec2(asp * 0.28, -0.12);
  vec2 pd = c - pp;
  float pr = 0.17;
  float body = smoothstep(pr + 0.003, pr - 0.003, length(pd));
  vec2 nn = pd / pr;
  vec3 nrm = vec3(nn, sqrt(max(0.0, 1.0 - dot(nn, nn))));
  float shade = clamp(dot(nrm, normalize(vec3(-0.6, 0.5, 0.6))), 0.0, 1.0);
  float bands = 0.5 + 0.5 * sin(pd.y * 60.0 + pd.x * 8.0 + t * 0.1);
  vec2 rd = vec2(pd.x * cos(0.3) + pd.y * sin(0.3), -pd.x * sin(0.3) + pd.y * cos(0.3));
  float ringd = length(rd * vec2(1.0, 4.0));
  float ringm = smoothstep(0.015, 0.0, abs(ringd - 0.27)) + 0.6 * smoothstep(0.01, 0.0, abs(ringd - 0.23));
  float front = step(0.0, -rd.y);
  o = over(o, vec3(0.3, 0.85, 1.0), ringm * (1.0 - body) * 0.8);
  o = over(o, mix(vec3(0.12, 0.15, 0.4), vec3(0.45, 0.55, 0.95), shade) * (0.85 + 0.15 * bands), body);
  o = over(o, vec3(0.3, 0.85, 1.0), ringm * body * front * 0.8);
  float cyc = fract(t / 7.0);
  vec2 sp0 = vec2(-asp * 0.5 + cyc * asp * 1.4, 0.45 - cyc * 0.5);
  vec2 sd = c - sp0;
  float trail = exp(-abs(sd.x * 0.58 + sd.y * 0.81) * 400.0) * smoothstep(0.0, -0.25, sd.x) * step(-0.25, sd.x);
  o = over(o, vec3(1.0), trail * step(cyc, 0.25));
