// Tuiles — the booster stage: flat design, a mosaic of flat tiles in eight colours turning over in a wave,
  // a flat sun pulsing with its long shadow (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  o = vec4(0.1, 0.1, 0.12, 1.0);
  vec2 g = c * 7.0;
  vec2 id = floor(g), f = fract(g) - 0.5;
  float wave = t * 0.6 - (id.x + id.y) * 0.18;
  float k = floor(wave), ph = fract(wave);
  float w = ph < 0.2 ? abs(cos(ph / 0.2 * 3.14159)) : 1.0;
  float ci = mod(hash(id) * 8.0 + k + step(0.1, ph) * step(ph, 0.2), 8.0);
  vec3 col = ci < 1.0 ? vec3(0.0, 0.67, 0.66) : ci < 2.0 ? vec3(0.97, 0.58, 0.1) : ci < 3.0 ? vec3(0.88, 0.3, 0.24) : ci < 4.0 ? vec3(0.13, 0.5, 0.78) : ci < 5.0 ? vec3(0.55, 0.76, 0.2) : ci < 6.0 ? vec3(0.6, 0.33, 0.72) : ci < 7.0 ? vec3(0.9, 0.2, 0.55) : vec3(0.95, 0.95, 0.95);
  o = over(o, col, step(abs(f.x), 0.45 * w) * step(abs(f.y), 0.45));
  vec2 s = c - vec2(-0.25, 0.12);
  float r = 0.13 + 0.008 * sin(t * 2.0);
  float shadow = step(abs(s.x + s.y) * 0.7071, r) * step(0.0, s.x - s.y);
  o.rgb *= 1.0 - 0.35 * shadow;
  o = over(o, vec3(0.97, 0.58, 0.1), step(length(s), r));
