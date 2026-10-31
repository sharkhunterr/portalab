// VHS — the booster stage: the arcade's dusk in pixel bands over a pixel skyline, a striped pixel sun, blinking
  // stars, scanlines rolling, the tape's tracking band passing (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  float px = 1.0 / 90.0;
  vec2 q = floor(c / px) * px + px * 0.5;
  float b = floor((0.5 - q.y) * 9.0);
  vec3 sky = b < 3.0 ? vec3(0.1, 0.08, 0.27) : b < 4.0 ? vec3(0.18, 0.11, 0.39) : b < 5.0 ? vec3(0.35, 0.14, 0.47) : b < 6.0 ? vec3(0.63, 0.2, 0.49) : b < 7.0 ? vec3(0.88, 0.31, 0.48) : vec3(1.0, 0.55, 0.4);
  o = vec4(sky, 1.0);
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    vec2 sp = floor(vec2((hash(vec2(fk, 1.0)) - 0.5) * asp, 0.2 + hash(vec2(fk, 2.0)) * 0.3) / px) * px + px * 0.5;
    float on = step(0.5, fract(t * (0.3 + hash(vec2(fk, 3.0))) + fk * 0.37));
    o = over(o, vec3(1.0), step(length(q - sp), px * 0.6) * on);
  }
  vec2 s = q - vec2(0.0, -0.08);
  float stripes = step(s.y, 0.0) * step(0.6, fract(s.y * 30.0 + t * 0.5));
  o = over(o, vec3(1.0, 0.82, 0.42), step(length(s), 0.26) * (1.0 - stripes));
  float bx = floor(q.x * 11.0);
  float h = -0.22 + 0.16 * hash(vec2(bx, 5.0));
  o = over(o, vec3(0.04, 0.035, 0.09), step(q.y, h));
  float win = step(0.5, hash(floor(q / (px * 2.0)) + floor(t * 0.5))) * step(mod(floor(q.x / px), 3.0), 0.5) * step(mod(floor(q.y / px), 3.0), 0.5);
  o = over(o, vec3(1.0, 0.86, 0.2), step(q.y, h - px * 2.0) * win * 0.9);
  o.rgb *= 0.8 + 0.2 * step(0.5, fract(gl_FragCoord.y / 4.0));
  float ty = fract(t / 3.0) * 1.4 - 0.7;
  float band = step(abs(c.y - ty), 0.025);
  o = over(o, vec3(1.0), band * step(0.7, hash(vec2(floor(c.x * 200.0), floor(t * 24.0)))) * 0.6);
