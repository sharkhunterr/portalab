// Portalab — effect/skyveil: the « aurorasky » effect (spec 028, B2)
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float tl = mod(u_age, 7.0);
  float show = smoothstep(0.0, 1.5, tl) * smoothstep(7.0, 5.5, tl);
  o = over(o, mix(vec3(0.01, 0.03, 0.08), vec3(0.03, 0.08, 0.2), uv.y), 0.75 * show);
  vec2 sg = c * 40.0;
  o = over(o, vec3(1.0), step(0.985, hash(floor(sg))) * smoothstep(0.4, 0.0, length(fract(sg) - 0.5)) * show * (0.5 + 0.5 * sin(u_age * 3.0 + hash(floor(sg)) * 50.0)));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = c.x * 1.4 + fbm(vec2(c.x * 1.2 + fi * 3.0, u_age * 0.12)) * 1.6;
    float centre = 0.18 + 0.14 * sin(x * 2.2 + u_age * 0.4 + fi * 2.0) + fi * 0.04;
    float curtain = exp(-pow((c.y - centre) * 5.0, 2.0)) * smoothstep(-0.15, centre, c.y) * (0.6 + 0.4 * fbm(vec2(x * 3.0, u_age * 0.2)));
    float rays = 0.65 + 0.35 * sin(c.x * 22.0 + fbm(vec2(c.x * 4.0, u_age * 0.25 + fi)) * 9.0);
    vec3 col = fi < 0.5 ? vec3(0.2, 1.0, 0.55) : fi < 1.5 ? vec3(0.2, 0.85, 0.9) : vec3(0.7, 0.35, 1.0);
    o = over(o, col, curtain * rays * 0.6 * show);
  }
  float st = mod(u_age, 7.0) - 2.0;
  vec2 head = vec2(-0.6 + st * 0.5, 0.45 - st * 0.18);
  vec2 rel = c - head;
  vec2 dir = normalize(vec2(-0.5, 0.18));
  float along = dot(rel, dir);
  float across = abs(dot(rel, vec2(-dir.y, dir.x)));
  o = over(o, vec3(1.0), smoothstep(0.003, 0.0, across) * step(0.0, along) * exp(-along * 10.0) * step(0.0, st) * step(st, 1.2));
