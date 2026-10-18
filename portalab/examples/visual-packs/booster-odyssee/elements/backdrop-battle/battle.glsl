// Odyssée — the booster stage in deep space, at war: stars in three depths drifting past, a cruiser far off
  // trading laser fire with a swarm, explosions blooming, asteroids tumbling near, fighters weaving between them
  // with their engine trails (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = over(o, mix(vec3(0.0, 0.0, 0.02), vec3(0.02, 0.03, 0.08), smoothstep(-0.6, 0.6, c.y)), 1.0);
  float neb = smoothstep(0.5, 0.9, fbm(c * 1.8 + vec2(t * 0.004, 0.0)));
  o = over(o, vec3(0.1, 0.25, 0.45), neb * 0.35);
  // stars in three depths, drifting left, the nearer the faster
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    vec2 g = (c + vec2(t * (0.004 + fk * 0.012), 0.0)) * (40.0 - fk * 12.0) + fk * 11.0;
    vec2 cell = floor(g);
    float star = step(0.94, hash(cell + fk)) * smoothstep(0.1 + fk * 0.04, 0.0, length(fract(g) - 0.5 - (vec2(hash(cell + 2.0), hash(cell + 5.0)) - 0.5) * 0.6));
    o = over(o, vec3(0.8, 0.88, 1.0), star * (0.4 + fk * 0.25));
  }
  // the cruiser, far off: a long wedge, its running lights
  vec2 cr = c - vec2(0.45, 0.27);
  float hull = smoothstep(0.003, 0.0, max(abs(cr.y) - 0.012 - cr.x * 0.06, abs(cr.x) - 0.2)) * step(-0.2, cr.x);
  o = over(o, vec3(0.08, 0.09, 0.12), hull);
  o = over(o, vec3(0.4, 0.75, 1.0), smoothstep(0.004, 0.0, length(cr - vec2(0.19, 0.0))) * (0.6 + 0.4 * sin(t * 6.0)));
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    o = over(o, vec3(1.0, 0.6, 0.3), smoothstep(0.0025, 0.0, length(cr - vec2(-0.16 + fk * 0.07, -0.016 + fk * 0.004))) * step(0.5, fract(t * 1.3 + fk * 0.37)));
  }
  // laser fire across the battle: bolts flying, red one way, green the other
  for (int k = 0; k < 9; k++) {
    float fk = float(k);
    float life = fract(t * (0.5 + 0.4 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    float side = step(0.5, hash(vec2(fk, 3.0)));
    vec2 from = vec2(0.3 + 0.2 * hash(vec2(fk, 4.0)), 0.2 + 0.15 * hash(vec2(fk, 5.0)));
    vec2 to = vec2(-0.2 + 0.5 * hash(vec2(fk, 6.0)), 0.05 + 0.35 * hash(vec2(fk, 7.0)));
    vec2 a0 = mix(from, to, side);
    vec2 a1 = mix(to, from, side);
    vec2 pos = mix(a0, a1, life);
    vec2 dir = normalize(a1 - a0);
    vec2 rel = c - pos;
    float along = dot(rel, -dir);
    float bolt = smoothstep(0.0025, 0.0, abs(dot(rel, vec2(-dir.y, dir.x)))) * step(0.0, along) * step(along, 0.05);
    o = over(o, mix(vec3(1.0, 0.25, 0.2), vec3(0.3, 1.0, 0.4), side), bolt);
  }
  // explosions blooming among them
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float cyc = t * 0.33 + fk * 0.41;
    float age = fract(cyc);
    float id = floor(cyc);
    vec2 ep = vec2(-0.1 + 0.6 * hash(vec2(id, fk)), 0.08 + 0.32 * hash(vec2(id, fk + 9.0)));
    float rr = length(c - ep);
    float ball = smoothstep(0.004 + age * 0.05, 0.0, rr - age * 0.02) * smoothstep(0.5, 0.0, age);
    float ring = smoothstep(0.004, 0.0, abs(rr - age * 0.08)) * smoothstep(0.6, 0.0, age);
    o = over(o, mix(vec3(1.0, 0.95, 0.7), vec3(1.0, 0.45, 0.1), age * 2.0), ball);
    o = over(o, vec3(1.0, 0.7, 0.4), ring * 0.7);
  }
  // asteroids tumbling near the edges: lumpy, lit from one side, slowly turning
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    vec2 ap = vec2(mod(0.9 - t * (0.012 + 0.008 * fk) + fk * 0.43, 2.2) - 1.1, -0.4 + 0.2 * fk + 0.05 * sin(t * 0.1 + fk));
    if (fk > 2.5) ap.y = 0.42 - 0.1 * (fk - 3.0);
    vec2 q = c - ap;
    float spin = t * (0.2 + 0.1 * fk) + fk;
    vec2 rq = vec2(q.x * cos(spin) - q.y * sin(spin), q.x * sin(spin) + q.y * cos(spin));
    float size = 0.035 + 0.03 * hash(vec2(fk, 8.0));
    float lump = size * (0.8 + 0.3 * noise(vec2(atan(rq.y, rq.x) * 2.0 + fk * 3.0, fk)));
    float rock = smoothstep(0.003, 0.0, length(rq) - lump);
    float lit = clamp(dot(normalize(q + 0.0001), normalize(vec2(0.7, 0.5))) * 0.8 + 0.3, 0.0, 1.0);
    float craters = noise(rq * 60.0) * 0.4;
    o = over(o, vec3(0.32, 0.28, 0.25) * (0.3 + lit) - craters * 0.15, rock);
  }
  // fighters weaving through: small darts with engine trails, swerving
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    float run = fract(t * (0.07 + 0.03 * fk) + fk * 0.27);
    vec2 fp = vec2(-1.0 + run * 2.0, -0.25 + fk * 0.16 + 0.07 * sin(run * 12.0 + fk * 2.0));
    vec2 vel = normalize(vec2(1.0, 0.07 * 12.0 * cos(run * 12.0 + fk * 2.0) * 2.0 / 2.0));
    vec2 rel = c - fp;
    vec2 lr = vec2(dot(rel, vel), dot(rel, vec2(-vel.y, vel.x)));
    float dart = step(-0.02, lr.x) * step(lr.x, 0.0) * step(abs(lr.y), (lr.x + 0.02) * 0.4);
    float trail = smoothstep(0.003, 0.0, abs(lr.y)) * step(lr.x, -0.02) * smoothstep(-0.16, -0.02, lr.x);
    o = over(o, vec3(0.75, 0.8, 0.9), dart);
    o = over(o, vec3(0.4, 0.75, 1.0), trail * 0.8);
  }
  o.rgb *= mix(0.4, 1.0, smoothstep(1.1, 0.3, length(c * vec2(0.7, 1.0))));
