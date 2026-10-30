// Impact — a legendary card turned (u_age: seconds, 3.0 s): a wall of green-yellow binary digits lights up
  // behind it and scrolls, green energy flames rise all round its edges, a lime shockwave rolls away and a huge
  // four-pointed glint flares at its corner — twice.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float fade = smoothstep(0.0, 0.15, age) * smoothstep(3.0, 2.3, age);
  // the binary wall: lime light, bold slanted 0s and 1s scrolling up, inside an ellipse
  float wall = smoothstep(0.0, 0.35, age) * fade * smoothstep(1.0, 0.55, length(c * vec2(1.3, 1.0)));
  o = over(o, vec3(0.86, 0.96, 0.18), wall * 0.85);
  vec2 g = c * vec2(6.5, 4.4) + vec2(0.0, age * 0.7);
  g.x += g.y * 0.22;
  vec2 cell = floor(g);
  vec2 f = fract(g) - 0.5;
  float one = step(0.5, hash(cell + vec2(3.0, 7.0)));
  float bar = step(abs(f.x + f.y * 0.1), 0.14) * step(abs(f.y), 0.38);
  float ell = length(f * vec2(3.4, 2.6));
  float zero = smoothstep(1.0, 0.9, ell) - smoothstep(0.5, 0.4, ell);
  o = over(o, vec3(0.38, 0.55, 0.0), mix(zero, bar, one) * wall);
  // green energy flames licking up round the card's edges (the card hides what is inside)
  vec2 half_size = vec2(0.205, 0.285);
  vec2 out_of = max(abs(c) - half_size, 0.0);
  float dist = length(out_of);
  float flick = fbm(vec2(c.x * 14.0 + c.y * 3.0, c.y * 7.0 - age * 6.0));
  float tongue = max(0.0, flick - 0.42) * 2.4;                // tongues of fire, not a halo
  float flame = smoothstep(0.012 + 0.22 * tongue, 0.0, dist) * step(0.0005, dist);
  float rise = smoothstep(0.1, 0.5, age) * fade;
  o = over(o, vec3(0.05, 0.85, 0.35), flame * rise);
  o = over(o, vec3(0.75, 1.0, 0.85), smoothstep(0.006 + 0.08 * tongue, 0.0, dist) * rise * step(0.0005, dist));
  // the lime shockwave
  float wave = 0.2 + age * 0.45;
  o = over(o, vec3(0.9, 1.0, 0.5), smoothstep(0.01, 0.0, abs(r - wave)) * smoothstep(1.4, 0.4, age));
  // the huge glint, twice: at the top-right corner, then lower left
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float at = 0.45 + fk * 1.25;
    float flare = exp(-pow((age - at) * 3.2, 2.0));
    vec2 gp = c - mix(vec2(0.27, 0.34), vec2(-0.28, -0.3), fk);
    float size = mix(0.6, 0.4, fk) * flare;
    float rays = exp(-abs(gp.x) * 70.0) * exp(-abs(gp.y) / max(size, 0.001) * 2.0) + exp(-abs(gp.y) * 70.0) * exp(-abs(gp.x) / max(size, 0.001) * 2.0);
    o = over(o, vec3(1.0), clamp(rays + exp(-length(gp) * 16.0) * flare * 1.4, 0.0, 1.0) * fade);
  }
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edge));
