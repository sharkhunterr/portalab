// Bulle — the booster stage: translucent Y2K, a deep candy-blue under fine stripes, a rain of green code, glossy
  // bubbles rising and swaying (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(0.02, 0.07, 0.2), vec3(0.06, 0.3, 0.55), smoothstep(-0.6, 0.6, c.y)), 1.0);
  o.rgb += 0.025 * step(0.5, fract(gl_FragCoord.y / 6.0));
  float col = floor(c.x * 45.0);
  float speed = 0.3 + 0.4 * hash(vec2(col, 1.0));
  float y = fract(c.y * 0.6 + t * speed + hash(vec2(col, 2.0)));
  float dash = step(0.3, fract(c.y * 40.0)) * step(abs(fract(c.x * 45.0) - 0.5), 0.12);
  o = over(o, vec3(0.3, 1.0, 0.55), dash * pow(y, 4.0) * 0.8 * step(0.4, hash(vec2(col, 3.0))));
  for (int k = 0; k < 22; k++) {
    float fk = float(k);
    float r = 0.02 + 0.05 * hash(vec2(fk, 1.0));
    vec2 bp = vec2((hash(vec2(fk, 2.0)) - 0.5) * asp + 0.02 * sin(t + fk), fract(hash(vec2(fk, 3.0)) + t * (0.04 + 0.05 * hash(vec2(fk, 4.0)))) * 1.3 - 0.65);
    vec2 q = c - bp;
    float l = length(q);
    o = over(o, vec3(0.5, 0.86, 1.0), step(l, r) * 0.15 + smoothstep(0.004, 0.0, abs(l - r)) * 0.8);
    o = over(o, vec3(1.0), step(length((q - vec2(-r * 0.4, r * 0.45)) * vec2(1.0, 1.8)), r * 0.22) * 0.9);
  }
  vec2 orb = c - vec2(0.0, 0.0);
  o = over(o, vec3(0.2, 0.68, 1.0), exp(-length(orb) * 3.0) * 0.25);
