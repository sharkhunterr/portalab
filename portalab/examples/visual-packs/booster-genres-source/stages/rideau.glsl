// Rideau — the booster stage: a theatre in the dark, red velvet curtains at the sides swaying slightly, the
  // footlights glowing, a beam of light from above where dust dances (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.04, 0.015, 0.02, 1.0);
  float beam = smoothstep(0.32 + (0.5 - c.y) * 0.25, 0.0, abs(c.x)) * smoothstep(-0.55, 0.5, c.y);
  o = over(o, vec3(1.0, 0.92, 0.75), beam * 0.12);
  for (int k = 0; k < 30; k++) {
    float fk = float(k);
    vec2 dp = vec2((hash(vec2(fk, 1.0)) - 0.5) * 0.5, fract(hash(vec2(fk, 2.0)) - t * 0.01 * (1.0 + hash(vec2(fk, 3.0)))) * 1.1 - 0.55);
    o = over(o, vec3(1.0, 0.9, 0.7), exp(-length(c - dp) * 600.0) * beam * 2.0);
  }
  // the curtains: velvet folds, swaying, on both sides
  float side = abs(c.x) - asp * 0.32 - 0.02 * sin(c.y * 3.0 + t * 0.4);
  float folds = 0.5 + 0.5 * sin((abs(c.x)) * 70.0 + 0.6 * sin(c.y * 2.0 + t * 0.3));
  vec3 velvet = mix(vec3(0.25, 0.01, 0.04), vec3(0.62, 0.05, 0.1), folds * folds);
  o = over(o, velvet, smoothstep(-0.005, 0.005, side));
  o = over(o, vec3(0.95, 0.75, 0.3), smoothstep(0.006, 0.0, abs(side)) * 0.8);
  // the valance on top, gold-fringed
  float top = 0.42 - 0.02 * sin(c.x * 18.0);
  o = over(o, mix(vec3(0.3, 0.01, 0.04), vec3(0.6, 0.04, 0.09), 0.5 + 0.5 * sin(c.x * 40.0)), step(top, c.y));
  o = over(o, vec3(0.95, 0.75, 0.3), smoothstep(0.008, 0.0, abs(c.y - top)));
  // the footlights
  for (int k = 0; k < 9; k++) {
    float fk = float(k);
    vec2 fp = vec2((fk / 8.0 - 0.5) * asp * 0.6, -0.5);
    o = over(o, vec3(1.0, 0.85, 0.5), exp(-length((c - fp) * vec2(1.0, 2.5)) * 18.0) * 0.6);
  }
