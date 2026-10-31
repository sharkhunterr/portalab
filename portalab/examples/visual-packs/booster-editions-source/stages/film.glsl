// Pellicule — the booster stage: a 1970s poster's sunset, a sun in bands sinking behind a halftone sky, the
  // paper's grain, strips of film running across the top and the foot (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.93, 0.86, 0.72, 1.0);
  // halftone sky: dots growing towards the horizon
  vec2 g = c * 70.0;
  vec2 cell = fract(g) - 0.5;
  float size = 0.12 + 0.3 * smoothstep(0.4, -0.1, c.y);
  o = over(o, vec3(0.92, 0.33, 0.18), step(length(cell), size) * 0.55 * step(-0.1, c.y));
  // the sun in bands, gaps widening towards its foot
  vec2 s = c - vec2(0.0, -0.02 - 0.02 * sin(t * 0.3));
  float k = (s.y + 0.3) / 0.6;
  vec3 sun = mix(vec3(0.6, 0.16, 0.24), vec3(1.0, 0.8, 0.3), clamp(k, 0.0, 1.0));
  float gaps = step(0.5, k) + step(fract(k * 8.0 + t * 0.1), 0.25 + 0.6 * (0.5 - k));
  o = over(o, sun, step(length(s), 0.3) * clamp(gaps, 0.0, 1.0));
  // the ground in stripes
  float gy = -0.2 - c.y;
  o = over(o, mix(vec3(1.0, 0.58, 0.18), vec3(0.6, 0.16, 0.24), step(0.5, fract(gy * 12.0))), step(0.0, gy));
  // the film: dark bands with holes, running
  float fy = abs(c.y) - 0.44;
  float holes = step(abs(fract(c.x * 14.0 + t * 0.4 * sign(c.y)) - 0.5), 0.18) * step(abs(fy), 0.015);
  o = over(o, vec3(0.14, 0.1, 0.08), step(abs(fy), 0.04) * (1.0 - holes));
  o.rgb *= 0.95 + 0.05 * noise(c * 300.0 + floor(t * 12.0));
