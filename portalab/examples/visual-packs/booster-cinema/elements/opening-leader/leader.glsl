// Cinema — the opening (u_age: seconds, 3.4 s): the clap's flash at 0.4 s; the countdown leader 3, 2, 1 (its
  // rings, its cross, its sweeping hand and the shade behind it, a seven-segment figure, grain and flicker); the
  // film racing down through the gate, its sprocket holes; at 2.5 s the frame burns from the middle, its edge
  // glowing, and the projector's white light bursts through.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float frame = floor(age * 24.0);
  float flick = 0.85 + 0.15 * hash(vec2(frame, 1.0));
  o = over(o, vec3(1.0), exp(-abs(age - 0.42) * 22.0) * 0.6);
  // the leader, from 0.5 s to 2.1 s: three seconds of film, one a figure
  float lt = (age - 0.5) / 0.53;
  if (lt > 0.0 && lt < 3.0) {
    float fig = 3.0 - floor(lt);
    float ph = fract(lt);
    float fade = smoothstep(0.0, 0.15, age - 0.5) * smoothstep(2.1, 1.95, age);
    vec2 q = c;
    float r = length(q);
    float a = atan(q.x, q.y);
    float hand = mod(a, 6.2832) / 6.2832;
    vec3 base = vec3(0.62, 0.6, 0.56) * flick;
    base = mix(base, vec3(0.32, 0.31, 0.3) * flick, step(hand, ph) * step(r, 0.34));
    float lines = smoothstep(0.004, 0.0, abs(r - 0.34)) + smoothstep(0.004, 0.0, abs(r - 0.27)) + (smoothstep(0.003, 0.0, abs(q.x)) + smoothstep(0.003, 0.0, abs(q.y))) * step(r, 0.42);
    lines += smoothstep(0.006, 0.0, abs(sin(a - ph * 6.2832) * r)) * step(r, 0.34) * step(0.0, cos(a - ph * 6.2832));
    vec3 col = mix(base, vec3(0.05), clamp(lines, 0.0, 1.0));
    // the figure in seven segments
    vec2 g = q / vec2(0.07, 0.11);
    float seg = 0.0;
    float th = 0.14;
    float sA = step(abs(g.y - 1.0), th) * step(abs(g.x), 0.85);
    float sG = step(abs(g.y), th) * step(abs(g.x), 0.85);
    float sD = step(abs(g.y + 1.0), th) * step(abs(g.x), 0.85);
    float sB = step(abs(g.x - 0.85), th) * step(0.0, g.y) * step(g.y, 1.0);
    float sC = step(abs(g.x - 0.85), th) * step(g.y, 0.0) * step(-1.0, g.y);
    float sE = step(abs(g.x + 0.85), th) * step(g.y, 0.0) * step(-1.0, g.y);
    if (fig > 2.5) seg = sA + sG + sD + sB + sC;
    else if (fig > 1.5) seg = sA + sG + sD + sB + sE;
    else seg = sB + sC;
    col = mix(col, vec3(0.03), clamp(seg, 0.0, 1.0));
    col += (hash(gl_FragCoord.xy + frame) - 0.5) * 0.12;
    float scratch = step(0.99, hash(vec2(floor(c.x * 200.0), frame)));
    col = mix(col, vec3(0.9), scratch * 0.5);
    float box = smoothstep(0.003, 0.0, max(abs(c.x) - 0.5, abs(c.y) - 0.42));
    o = over(o, col, fade * box * smoothstep(0.62, 0.42, length(c * vec2(0.8, 1.0))));
  }
  // the film racing down through the gate
  float run = smoothstep(2.0, 2.1, age) * smoothstep(2.65, 2.5, age);
  if (run > 0.0) {
    float y = c.y + age * 4.0;
    float strip = step(abs(c.x), 0.22);
    float holes = step(0.17, abs(c.x)) * step(abs(c.x), 0.205) * step(0.4, fract(y * 14.0)) * step(fract(y * 14.0), 0.8);
    float framesLine = smoothstep(0.004, 0.0, abs(fract(y * 2.2) - 0.5));
    vec3 film = mix(vec3(0.08, 0.06, 0.05), vec3(0.6, 0.55, 0.48) * flick * (0.7 + 0.3 * fbm(vec2(c.x * 10.0, y * 3.0))), step(abs(c.x), 0.15));
    film = mix(film, vec3(0.9, 0.88, 0.8), holes);
    film = mix(film, vec3(0.05), framesLine * step(abs(c.x), 0.15));
    o = over(o, film, strip * run);
  }
  // the burn: a hole eating the frame from the middle, its edge glowing, the projector's light bursting through
  if (age > 2.45) {
    float s = age - 2.45;
    float fade = smoothstep(0.95, 0.6, s);
    float rad = s * 0.9;
    float edge = length(c * vec2(1.0, 1.2)) - rad - 0.05 * (fbm(c * 9.0 + 3.0) - 0.5);
    vec3 frameCol = vec3(0.6, 0.55, 0.48) * flick;
    o = over(o, frameCol, smoothstep(0.0, 0.01, edge) * step(abs(c.x), 0.3) * step(abs(c.y), 0.4) * smoothstep(0.4, 0.2, s));
    o = over(o, vec3(1.0, 0.55, 0.1), smoothstep(0.035, 0.0, abs(edge)) * fade);
    o = over(o, vec3(1.0, 0.85, 0.4), smoothstep(0.012, 0.0, abs(edge + 0.006)) * fade);
    o = over(o, vec3(1.0, 0.98, 0.92), smoothstep(0.0, -0.02, edge) * fade);
    o = over(o, vec3(1.0, 0.95, 0.85), exp(-length(c) * 3.0) * fade * 0.6);
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: an ellipse inside its box, fading to nothing well before its sides (never a rectangle)
  vec2 edgeuv = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.62, length(edgeuv));
