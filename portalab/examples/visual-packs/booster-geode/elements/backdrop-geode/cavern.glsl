// Géode — the booster stage, inside a geode: its walls lined with amethyst facets all round (each facet shaded
  // by its own tilt, its edges catching the light, now and then one flashing), the hollow dark and deep at its
  // heart with a violet glow, slow shafts of light crossing it, mineral dust floating (a stage: gl_FragCoord,
  // u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.03, 0.015, 0.05, 1.0);
  // the hollow: an oval, the walls beyond it (wider on a wide screen)
  vec2 e = c / vec2(0.36 + 0.22 * asp, 0.42);
  float wall = smoothstep(0.82, 1.18, length(e) + 0.06 * sin(atan(e.y, e.x) * 5.0 + 1.3));
  o = over(o, vec3(0.26, 0.08, 0.42), exp(-length(c * vec2(0.9, 1.2)) * 3.0) * 0.55);
  // the crystals' points, seen from in front: the nearest of a jittered grid of points (Voronoi) is a point,
  // three faces meeting at it, each lit by its slant — a druse of amethyst
  vec2 g = c * 9.0;
  vec2 cell = floor(g);
  float near = 9.0;
  float second = 9.0;
  vec2 owner = vec2(0.0);
  vec2 tip = vec2(0.0);
  for (int y = -1; y < 2; y++) {
    for (int x = -1; x < 2; x++) {
      vec2 id = cell + vec2(float(x), float(y));
      vec2 at = id + 0.5 + 0.8 * vec2(hash(id) - 0.5, hash(id + 7.3) - 0.5);
      float d = length(g - at);
      if (d < near) {
        second = near;
        near = d;
        owner = id;
        tip = at;
      } else if (d < second) {
        second = d;
      }
    }
  }
  vec2 from = g - tip;
  float turn = hash(owner + 5.7) * 6.2831853;
  float a3 = (atan(from.y, from.x) - turn) / 2.0943951;
  float face = floor(a3);
  float across = fract(a3);
  float slant = turn + (face + 0.5) * 2.0943951;
  float lightAt = 2.3 + 0.5 * sin(t * 0.2);
  float shade = 0.5 + 0.5 * cos(slant - lightAt);
  float deep = hash(owner + 3.1);
  vec3 facet = mix(vec3(0.12, 0.03, 0.24), mix(vec3(0.58, 0.3, 0.92), vec3(0.88, 0.76, 1.0), deep * deep), pow(shade, 1.4));
  facet *= 0.6 + 0.4 * smoothstep(1.4, 0.9, length(e));
  o = over(o, facet, wall * 0.95);
  // its ridges (where two faces meet) and its edges catching the light
  float ridge = smoothstep(0.07, 0.0, min(across, 1.0 - across) * length(from) * 2.1) * (1.0 - smoothstep(0.0, 0.6, near));
  float edge = smoothstep(0.05, 0.0, second - near);
  float sweep = 0.5 + 0.5 * sin(t * 0.25 + owner.x * 0.35 - owner.y * 0.22);
  o = over(o, vec3(0.95, 0.88, 1.0), wall * (ridge * (0.35 + 0.4 * shade) + edge * 0.3) * (0.5 + 0.5 * sweep));
  // now and then a point flashes
  float flash = pow(max(0.0, sin(t * (0.6 + deep) + hash(owner + 11.0) * 40.0)), 24.0);
  o = over(o, vec3(1.0, 0.96, 1.0), wall * flash * smoothstep(0.35, 0.0, near) * 0.9);
  // the wall's rim darkening into the hollow
  o = over(o, vec3(0.02, 0.0, 0.04), smoothstep(1.25, 0.85, length(e)) * wall * 0.6);
  // shafts of light crossing slowly
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float x = c.x - (fk - 1.0) * 0.45 * asp - 0.08 * sin(t * 0.07 + fk * 2.0) + c.y * 0.35;
    float shaft = exp(-x * x * 40.0) * smoothstep(-0.6, 0.5, c.y);
    o = over(o, vec3(0.75, 0.6, 1.0), shaft * (0.05 + 0.03 * sin(t * 0.3 + fk)));
  }
  // mineral dust floating
  for (int k = 0; k < 24; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    float h2 = hash(vec2(fk, 2.0));
    vec2 sp = vec2((h1 - 0.5) * asp + 0.05 * sin(t * 0.3 + fk), fract(h2 + t * (0.008 + 0.012 * h1)) * 1.2 - 0.6);
    float dm = length(c - sp);
    float glint = 0.5 + 0.5 * sin(t * (1.5 + h2 * 2.0) + fk);
    o = over(o, vec3(0.95, 0.88, 1.0), exp(-dm * 500.0) * glint + exp(-dm * 70.0) * 0.08);
  }
