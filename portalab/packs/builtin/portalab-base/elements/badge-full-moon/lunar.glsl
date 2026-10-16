// Portalab — badge/lunar: the « lunar » effect (spec 028, B2)
  vec2 e = vec2(p.x / max(ax, 1.0), p.y);
  float phase = sin(t * 0.35);
  float seas = smoothstep(0.45, 0.65, fbm(p * 1.4 + 3.0));
  vec3 moon = mix(vec3(0.93, 0.92, 0.88), vec3(0.55, 0.57, 0.62), seas);
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    vec2 cc = (vec2(hash(vec2(fi, 11.0)), hash(vec2(fi, 12.0))) - 0.5) * vec2(1.5 * ax, 1.5);
    float cr = 0.12 + 0.14 * hash(vec2(fi, 13.0));
    float dc = length(p - cc);
    moon *= 1.0 - 0.15 * smoothstep(cr, cr * 0.6, dc) + 0.08 * smoothstep(0.04, 0.0, abs(dc - cr));
  }
  moon *= 0.85 + 0.15 * fbm(p * 6.0);
  float lit = smoothstep(-0.12, 0.12, e.x * sign(phase) + (1.0 - abs(phase)) * 1.1 - 0.15);
  moon = mix(moon * 0.12 + vec3(0.02, 0.03, 0.06), moon, lit);
  moon += vec3(0.8, 0.85, 1.0) * smoothstep(-0.2, 0.0, d) * 0.3;
  o = over(o, vec3(0.75, 0.82, 1.0), exp(-max(d, 0.0) * 3.5) * 0.35 * step(0.0, d));
  vec2 sg = p * 7.0;
  float sh = hash(floor(sg));
  o = over(o, vec3(1.0), step(0.93, sh) * smoothstep(0.3, 0.0, length(fract(sg) - 0.5)) * step(0.15, d) * (0.5 + 0.5 * sin(t * 2.0 + sh * 30.0)));
  o = over(o, moon, smoothstep(0.03, -0.03, d));
