// Impact — the opening (u_age: seconds, 2.6 s), drawn like an anime's impact frame, hard-edged: inked pink and
  // white rays shooting out round the spinning pack, white speed lines streaking outwards; at 1.85 s a white
  // comic explosion, inked, that dissolves into shrinking halftone dots — the cards come out of it.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float a = atan(c.y, c.x);
  float on = step(0.08, age) * step(age, 1.9);
  vec3 ink = vec3(0.07, 0.02, 0.11);
  // rays, in two inked layers: pink, then white inside — redrawn on each beat (twelve a second)
  float beat = floor(age * 12.0);
  float grow = smoothstep(0.0, 1.2, age);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float n = 18.0 + fk * 9.0;
    float s = a / 6.2832 * n + fk * 0.37 + hash(vec2(beat, fk)) * 0.15;
    float id = floor(s);
    float len = (0.3 + 0.7 * hash(vec2(id, 3.0 + fk + beat * 0.0))) * grow * (1.0 - 0.42 * fk) * 0.9;
    float halfw = 0.44 * clamp(1.0 - r / max(len, 0.001), 0.0, 1.0);
    float across = abs(fract(s) - 0.5);
    float fill = step(across, halfw - 0.035) * step(0.05, r);
    float inked = step(across, halfw) * step(0.04, r);
    o = over(o, ink, inked * on);
    o = over(o, mix(vec3(1.0, 0.18, 0.56), vec3(1.0), fk), fill * on);
  }
  // white speed lines streaking outwards beyond the rays, hard
  float lanes = a / 6.2832 * 64.0;
  float lid = floor(lanes);
  float head = 0.35 + fract(age * (0.9 + hash(vec2(lid, 2.0))) + hash(vec2(lid, 3.0))) * 0.9;
  float streak = step(head - 0.16 - 0.1 * hash(vec2(lid, 6.0)), r) * step(r, head);
  float thin = step(abs(fract(lanes) - 0.5), 0.07);
  o = over(o, vec3(1.0), thin * streak * step(0.55, hash(vec2(lid, 4.0))) * on);
  // the flash: a white comic explosion, jagged and inked, swelling over everything, then dissolving into
  // halftone dots shrinking away
  float since = age - 1.85;
  float spikes = a / 6.2832 * 14.0;
  float jag = abs(fract(spikes) - 0.5) * 2.0;
  float reach = (0.42 + 0.16 * hash(vec2(floor(spikes), 9.0))) * (0.55 + 0.45 * jag) * (1.0 + 2.2 * smoothstep(0.0, 0.25, since));
  vec2 g = gl_FragCoord.xy / (u_res.y * 0.04);
  g = vec2(g.x + g.y, g.y - g.x) * 0.7071;
  float dotr = 0.75 * (1.0 - smoothstep(0.15, 0.6, since));
  float dots = mix(1.0, step(length(fract(g) - 0.5), dotr), step(0.15, since));
  float live = step(0.0, since) * step(since, 0.6);
  o = over(o, ink, step(r, reach + 0.02) * live * step(since, 0.15));
  o = over(o, vec3(1.0, 0.97, 1.0), step(r, reach) * dots * live);
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.8, length(edge));
