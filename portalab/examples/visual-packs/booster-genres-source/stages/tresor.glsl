// Trésor — the booster stage: the sea at sunset, the sun sinking on the horizon, its light trembling on the
  // waves, an island and its palms in silhouette, gold motes drifting (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  float hz = -0.08;
  vec3 sky = mix(vec3(0.98, 0.62, 0.34), vec3(0.42, 0.16, 0.32), smoothstep(hz, 0.5, c.y));
  o = vec4(sky, 1.0);
  float cloud = fbm(c * vec2(1.2, 5.0) + vec2(t * 0.02, 0.0));
  o = over(o, vec3(0.75, 0.3, 0.35), smoothstep(0.55, 0.75, cloud) * smoothstep(hz, 0.3, c.y) * 0.6);
  vec2 sp = vec2(0.25 * asp * 0.4, hz + 0.05);
  o = over(o, vec3(1.0, 0.85, 0.5), exp(-length(c - sp) * 4.0) * 0.6);
  o = over(o, vec3(1.0, 0.82, 0.45), smoothstep(0.1, 0.095, length(c - sp)) * step(hz, c.y));
  // the sea: dark teal, its waves catching the light, the sun's column trembling on it
  float below = step(c.y, hz);
  // waves: bands closer and closer towards the horizon, rippling
  float depth = 1.0 / (hz - c.y + 0.03);
  float wave = sin(depth * 2.2 + t * 1.6 + sin(c.x * 6.0 * depth * 0.1 + t) * 1.5) * 0.5 + 0.5;
  vec3 sea = mix(vec3(0.03, 0.16, 0.2), vec3(0.08, 0.3, 0.34), smoothstep(-0.5, hz, c.y));
  o = over(o, sea, below);
  float column = smoothstep(0.09 + (hz - c.y) * 0.25, 0.0, abs(c.x - sp.x)) * below;
  o = over(o, vec3(1.0, 0.8, 0.45), column * step(0.6, wave) * 0.7);
  o = over(o, vec3(0.9, 0.95, 0.9), below * step(0.93, wave) * 0.12);
  // the island and its palms, left
  float island = step(c.y, hz + 0.06 * exp(-pow((c.x + asp * 0.32) * 4.0, 2.0))) * step(hz, c.y);
  o = over(o, vec3(0.08, 0.04, 0.03), island);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    vec2 base = vec2(-asp * 0.34 + fk * 0.12, hz + 0.03);
    vec2 r = c - base;
    float trunk = smoothstep(0.008, 0.0, abs(r.x - r.y * 0.25 - 0.01 * sin(t + fk))) * step(0.0, r.y) * step(r.y, 0.22 - fk * 0.05);
    vec2 top = vec2(0.055 - fk * 0.01, 0.22 - fk * 0.05);
    float frond = 0.0;
    for (int j = 0; j < 5; j++) { float a = -2.6 + float(j) * 0.55 + 0.05 * sin(t * 1.3 + fk); vec2 d = r - top; float along = dot(d, vec2(cos(a), sin(a))); float across = abs(d.x * sin(a) - d.y * cos(a)); frond = max(frond, smoothstep(0.012, 0.0, across - along * 0.0) * step(0.0, along) * step(along, 0.13) * (1.0 - along * 5.0)); }
    o = over(o, vec3(0.06, 0.03, 0.02), max(trunk, step(0.1, frond)));
  }
  // gold motes drifting up
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 7.0));
    float age = fract(t * 0.07 + h1);
    vec2 mp = vec2((h1 - 0.5) * asp, -0.5 + age);
    o = over(o, vec3(1.0, 0.85, 0.45), exp(-length(c - mp) * 350.0) * (1.0 - age));
  }
