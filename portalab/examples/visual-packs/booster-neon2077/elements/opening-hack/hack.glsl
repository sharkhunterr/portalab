// Néon 2077 — the hack (u_age: seconds, 2.8 s): code streaming in, a hexagonal ICE grid closing round the
  // shard, a red alert flashing faster; at 1.9 s the ICE shatters, its hexagons flying out in a cyan flash.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float breach = 1.9;
  // code streaming in from the sides
  vec2 g = vec2(c.x * 60.0, c.y * 24.0 - age * 18.0 * sign(c.x));
  float code = step(0.55, hash(floor(g))) * step(0.3, fract(g.x)) * smoothstep(0.1, 0.4, abs(c.x)) * smoothstep(0.0, 0.5, age) * step(age, breach);
  o = over(o, vec3(0.2, 1.0, 0.7), code * 0.55);
  // the ICE: a hexagon grid closing in
  vec2 h = c * 18.0;
  vec2 hr = vec2(h.x + h.y * 0.577, h.y * 1.155);
  vec2 cell = floor(hr);
  vec2 hf = fract(hr) - 0.5;
  float edge = smoothstep(0.4, 0.47, max(abs(hf.x), abs(hf.y)));
  float closing = smoothstep(0.7, 0.1, length(c) - smoothstep(0.2, breach, age) * 0.0 - (1.0 - smoothstep(0.2, 1.5, age)) * 0.6);
  o = over(o, vec3(0.1, 0.9, 1.0), edge * closing * step(age, breach) * 0.6);
  // the alert, flashing faster
  float alert = step(0.5, fract(age * (2.0 + age * 3.0))) * smoothstep(0.8, 1.2, age) * step(age, breach);
  o = over(o, vec3(1.0, 0.05, 0.2), alert * smoothstep(0.15, 0.6, length(c)) * 0.35);
  // the breach: the hexagons flying out, a cyan flash
  if (age > breach) {
    float s = age - breach;
    vec2 dir = normalize(cell + 0.5 - vec2(0.0));
    vec2 moved = c * 18.0 - normalize(c + 0.0001) * s * 14.0 * (0.5 + hash(cell));
    vec2 mr = vec2(moved.x + moved.y * 0.577, moved.y * 1.155);
    vec2 mf = fract(mr) - 0.5;
    float piece = smoothstep(0.38, 0.3, max(abs(mf.x), abs(mf.y))) * step(0.6, hash(floor(mr)));
    float fade = smoothstep(0.9, 0.3, s);
    o = over(o, mix(vec3(0.1, 0.9, 1.0), vec3(1.0, 0.2, 0.7), hash(floor(mr) + 3.0)), piece * fade * 0.8 * smoothstep(0.1, 0.25, length(c)));
    o = over(o, vec3(0.7, 1.0, 1.0), exp(-length(c) * 5.0) * smoothstep(0.4, 0.0, s));
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
