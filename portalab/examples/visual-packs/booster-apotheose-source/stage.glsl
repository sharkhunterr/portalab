// Apothéose — the booster stage: deep violet, neon bands in pink, cyan and gold sliding slowly on a slant,
  // halftone dots swelling into two corners, a pink glow at its heart, glints twinkling (a stage: gl_FragCoord,
  // u_res, t; into o).
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(0.04, 0.015, 0.09, 1.0);
  o = over(o, vec3(0.45, 0.06, 0.4), exp(-length(c * vec2(0.8, 1.1)) * 2.4) * 0.55);
  // neon bands on a slant, each its colour, sliding, a soft glow round each
  float s = c.x * 0.8 - c.y * 0.6;
  for (int k = 0; k < 5; k++) {
    float fk = float(k);
    float at = fract(hash(vec2(fk, 1.0)) + t * (0.01 + 0.006 * fk)) * 3.0 - 1.5;
    float d = abs(s - at);
    vec3 col = k == 0 || k == 3 ? vec3(1.0, 0.18, 0.5) : (k == 1 || k == 4 ? vec3(0.2, 0.85, 1.0) : vec3(1.0, 0.78, 0.2));
    float width = 0.004 + 0.008 * hash(vec2(fk, 2.0));
    o = over(o, col, smoothstep(width, 0.0, d) * 0.85 + exp(-d * 30.0) * 0.18);
  }
  // halftone dots into the top-left and bottom-right corners
  vec2 g = gl_FragCoord.xy / (u_res.y * 0.02);
  g = vec2(g.x + g.y, g.y - g.x) * 0.7071;
  vec2 cell = fract(g) - 0.5;
  float near = max(smoothstep(0.7, 0.0, length((uv - vec2(0.0, 1.0)) * vec2(asp, 1.0))), smoothstep(0.6, 0.0, length((uv - vec2(1.0, 0.0)) * vec2(asp, 1.0))));
  float radius = 0.42 * near;
  o = over(o, vec3(0.75, 0.12, 0.6), smoothstep(radius, radius - 0.08, length(cell)) * step(0.04, near) * 0.6);
  // glints twinkling
  for (int k = 0; k < 18; k++) {
    float fk = float(k);
    vec2 sp = vec2((hash(vec2(fk, 7.0)) - 0.5) * asp * 0.96, (hash(vec2(fk, 8.0)) - 0.5) * 0.92);
    vec2 dd = c - sp;
    float size = 0.01 + 0.022 * hash(vec2(fk, 10.0));
    float tw = pow(0.5 + 0.5 * sin(t * (1.2 + 2.0 * hash(vec2(fk, 9.0))) + fk * 3.1), 5.0);
    float star = exp(-abs(dd.x) * 900.0) * exp(-abs(dd.y) / size * 2.2) + exp(-abs(dd.y) * 900.0) * exp(-abs(dd.x) / size * 2.2) + exp(-length(dd) * 260.0);
    o = over(o, vec3(1.0, 0.92, 1.0), clamp(star, 0.0, 1.0) * tw);
  }
