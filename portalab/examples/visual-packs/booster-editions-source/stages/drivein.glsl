// Drive-in — the booster stage: an atomic-age night, stars and Googie starbursts twinkling, the drive-in's big
  // screen lit by the projector's beam, finned cars in front, a sign's arrow of chasing bulbs (a stage:
  // gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.03, 0.05, 0.15), vec3(0.08, 0.16, 0.36), smoothstep(0.5, -0.4, c.y)), 1.0);
  for (int k = 0; k < 50; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 7.0)) - 0.5) * asp, hash(vec2(fk, 8.0)) * 0.5);
    vec2 sd = abs(c - sp);
    float tw = 0.5 + 0.5 * sin(t * (1.0 + 2.0 * hash(vec2(fk, 9.0))) + fk);
    float star = exp(-length(sd) * 500.0) + exp(-sd.x * 2000.0 - sd.y * 120.0) * 0.4 * step(0.8, hash(vec2(fk, 3.0))) + exp(-sd.y * 2000.0 - sd.x * 120.0) * 0.4 * step(0.8, hash(vec2(fk, 3.0)));
    o = over(o, vec3(1.0, 0.95, 0.84), star * tw);
  }
  // the screen, the beam
  vec2 sc = c - vec2(0.0, 0.08);
  float screen = step(abs(sc.x), 0.42) * step(abs(sc.y), 0.24);
  float beam = smoothstep(0.02 + (c.y + 0.5) * 0.5, 0.0, abs(c.x)) * step(c.y, 0.32);
  o = over(o, vec3(1.0, 0.95, 0.84), beam * 0.12);
  o = over(o, mix(vec3(0.75, 0.82, 0.9), vec3(0.95, 0.95, 0.9), 0.5 + 0.5 * sin(t * 3.0) * 0.2), screen * (0.75 + 0.05 * sin(t * 17.0)));
  o = over(o, vec3(0.8, 0.86, 0.92), smoothstep(0.004, 0.0, abs(max(abs(sc.x) - 0.42, abs(sc.y) - 0.24))));
  // the cars: rounded humps with fins, red taillights
  float cx = fract(c.x * 2.2) - 0.5;
  float car = step(c.y, -0.38 + 0.06 * smoothstep(0.35, 0.1, abs(cx)) + 0.05 * smoothstep(0.03, 0.0, abs(cx - 0.33)));
  o = over(o, vec3(0.015, 0.02, 0.06), max(car, step(c.y, -0.42)));
  o = over(o, vec3(0.9, 0.1, 0.22), exp(-length(vec2(cx - 0.3, c.y + 0.4)) * 120.0) * 1.5);
  // the arrow of bulbs, chasing
  vec2 ar = c - vec2(-asp * 0.36, 0.2);
  float on = step(0.66, fract(ar.x * 18.0 - t * 2.0));
  float path = smoothstep(0.012, 0.0, abs(ar.y + 0.12 * ar.x)) * step(-0.05, ar.x) * step(ar.x, 0.32);
  o = over(o, vec3(0.9, 0.1, 0.22), path * 0.9);
  o = over(o, vec3(1.0, 0.86, 0.45), path * on);
