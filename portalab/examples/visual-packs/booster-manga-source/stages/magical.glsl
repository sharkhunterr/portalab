// Magical girl — the booster stage: a pastel sky from lilac to pink and cyan, soft halos of light drifting, a
  // crescent moon, stars twinkling, iridescent bubbles rising (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  vec3 sky = mix(vec3(0.42, 0.3, 0.62), vec3(0.85, 0.5, 0.75), smoothstep(-0.6, 0.6, c.x * 0.4 - c.y));
  sky = mix(sky, vec3(0.45, 0.7, 0.9), smoothstep(0.1, 0.7, c.y + c.x * 0.2) * 0.45);
  o = vec4(sky * 0.62, 1.0);
  // soft halos drifting
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    vec2 hp = vec2(sin(t * 0.05 + fk * 1.7) * asp * 0.4, cos(t * 0.04 + fk * 2.3) * 0.35);
    o = over(o, mix(vec3(1.0, 0.7, 0.9), vec3(0.7, 0.9, 1.0), hash(vec2(fk, 5.0))), exp(-length(c - hp) * 6.0) * 0.18);
  }
  // the crescent moon
  vec2 mp = vec2(asp * 0.3, 0.3);
  float moon = smoothstep(0.082, 0.078, length(c - mp)) * smoothstep(0.066, 0.07, length(c - mp - vec2(0.03, 0.02)));
  o = over(o, vec3(1.0, 0.96, 0.85), moon);
  o = over(o, vec3(1.0, 0.85, 0.95), exp(-length(c - mp) * 14.0) * 0.25);
  // stars twinkling, four-pointed
  for (int k = 0; k < 28; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 7.0)) - 0.5) * asp, (hash(vec2(fk, 8.0)) - 0.5) * 0.95);
    vec2 dd = c - sp;
    float size = 0.008 + 0.018 * hash(vec2(fk, 9.0));
    float tw = pow(0.5 + 0.5 * sin(t * (1.0 + 2.0 * hash(vec2(fk, 10.0))) + fk * 3.1), 4.0);
    float star = exp(-abs(dd.x) * 900.0) * exp(-abs(dd.y) / size * 2.0) + exp(-abs(dd.y) * 900.0) * exp(-abs(dd.x) / size * 2.0) + exp(-length(dd) * 300.0);
    o = over(o, vec3(1.0, 0.97, 1.0), clamp(star, 0.0, 1.0) * tw);
  }
  // bubbles rising, their rims iridescent
  for (int k = 0; k < 14; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    float r = 0.02 + 0.04 * hash(vec2(fk, 2.0));
    vec2 bp = vec2((h1 - 0.5) * asp + 0.03 * sin(t * 0.5 + fk), fract(hash(vec2(fk, 3.0)) + t * (0.015 + 0.02 * h1)) * 1.3 - 0.65);
    float dist = length(c - bp);
    float rim = smoothstep(0.004, 0.0, abs(dist - r));
    vec3 hue = 0.6 + 0.4 * cos(6.2831 * (atan(c.y - bp.y, c.x - bp.x) / 6.2831 + vec3(0.0, 0.33, 0.67)));
    o = over(o, hue, rim * 0.55);
    o = over(o, vec3(1.0), smoothstep(r * 0.3, 0.0, length(c - bp - vec2(-0.4, 0.4) * r)) * 0.6);
  }
