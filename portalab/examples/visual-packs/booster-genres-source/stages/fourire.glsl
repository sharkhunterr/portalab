// Fou rire — the booster stage: a comedy club's backdrop in sunshine yellow, polka dots drifting, a pink
  // spotlight swaying, confetti falling in the party colours (a stage: gl_FragCoord, u_res, t; into o).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float asp = u_res.x / u_res.y;
  o = vec4(mix(vec3(1.0, 0.72, 0.18), vec3(1.0, 0.85, 0.35), smoothstep(-0.5, 0.5, c.y)), 1.0);
  vec2 g = c * 9.0 + vec2(t * 0.3, 0.0);
  vec2 cell = fract(vec2(g.x + 0.5 * mod(floor(g.y), 2.0), g.y)) - 0.5;
  o = over(o, vec3(1.0, 0.93, 0.6), smoothstep(0.2, 0.17, length(cell)));
  vec2 sp = vec2(0.45 * sin(t * 0.5) * asp * 0.5, 0.0);
  o = over(o, vec3(1.0, 0.45, 0.6), exp(-length((c - sp) * vec2(1.0, 0.6)) * 3.0) * 0.35);
  for (int k = 0; k < 40; k++) {
    float fk = float(k);
    float h1 = hash(vec2(fk, 1.0));
    float y = 0.6 - fract(t * (0.12 + 0.1 * h1) + h1) * 1.25;
    float x = (hash(vec2(fk, 2.0)) - 0.5) * asp + 0.04 * sin(t * 2.0 + fk);
    vec2 r = c - vec2(x, y);
    float a = t * 3.0 + fk; mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));
    vec2 q = rot * r;
    float flake = step(abs(q.x), 0.012 * abs(cos(t * 2.0 + fk))) * step(abs(q.y), 0.006);
    vec3 col = mod(fk, 5.0) < 1.0 ? vec3(1.0, 0.31, 0.55) : mod(fk, 5.0) < 2.0 ? vec3(0.24, 0.78, 1.0) : mod(fk, 5.0) < 3.0 ? vec3(0.3, 0.85, 0.45) : mod(fk, 5.0) < 4.0 ? vec3(0.6, 0.4, 1.0) : vec3(1.0, 1.0, 1.0);
    o = over(o, col, flake);
  }
  o.rgb *= smoothstep(1.4, 0.5, length(c));
