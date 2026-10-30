// Impact — the opening (u_age: seconds, 2.6 s): a manga burst of pink and white rays swelling round the
  // spinning pack, two white brush slashes cutting through at 1.2 s and 1.4 s, a white flash at 1.9 s — then
  // the burst blows out as the cards come.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float r = length(c) + 0.0001;
  float a = atan(c.y, c.x);
  float fade = smoothstep(0.0, 0.25, age) * smoothstep(2.6, 2.1, age);
  // the dark closing in
  o = over(o, vec3(0.02, 0.0, 0.03), 0.6 * fade * smoothstep(0.1, 0.5, r));
  // the burst: jagged spikes from the middle, pink then white inside, swelling and flickering
  float grow = smoothstep(0.0, 1.0, age) + 0.6 * smoothstep(1.85, 2.3, age);
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float n = 22.0 + fk * 13.0;
    float s = a / 6.2832 * n + fk * 0.5 + floor(age * 10.0) * 0.07 * (1.0 - fk);
    float id = floor(s);
    float len = (0.35 + 0.75 * hash(vec2(id, 3.0 + fk))) * grow * (1.0 - 0.45 * fk);
    float halfw = 0.42 * clamp(1.0 - r / max(len, 0.001), 0.0, 1.0);
    float spike = smoothstep(halfw, halfw - 0.06, abs(fract(s) - 0.5)) * step(0.06, r);
    vec3 col = mix(vec3(1.0, 0.13, 0.5), vec3(1.0, 0.96, 1.0), fk);
    o = over(o, col, spike * fade * (0.95 - 0.15 * fk));
  }
  // the core glowing white-pink
  o = over(o, vec3(1.0, 0.75, 0.92), exp(-r * mix(14.0, 5.0, smoothstep(0.0, 1.9, age))) * fade);
  // two white brush slashes, each sweeping across on its own slant, ragged, edged with pink
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float start = 1.2 + fk * 0.2;
    float since = age - start;
    float ang = mix(0.42, -0.5, fk);
    vec2 q = vec2(c.x * cos(ang) + c.y * sin(ang), -c.x * sin(ang) + c.y * cos(ang));
    float front = since * 7.0 - 1.4;                       // the stroke's head, crossing the screen
    float drawn = step(q.x, front) * step(0.0, since);
    float thick = 0.07 * (1.0 - smoothstep(-0.9, 0.9, q.x) * 0.55) * (0.75 + 0.5 * noise(vec2(q.x * 9.0, fk * 7.0)));
    float ragged = thick + 0.025 * (noise(vec2(q.x * 40.0, fk * 3.0)) - 0.5);
    float stroke = smoothstep(ragged, ragged - 0.01, abs(q.y + (fk - 0.5) * 0.06));
    float rim = smoothstep(ragged + 0.02, ragged, abs(q.y + (fk - 0.5) * 0.06)) - stroke;
    float life = drawn * smoothstep(0.75, 0.45, since);
    o = over(o, vec3(1.0, 0.2, 0.6), clamp(rim, 0.0, 1.0) * life);
    o = over(o, vec3(1.0), stroke * life);
  }
  // the white flash as the pack bursts
  o = over(o, vec3(1.0, 0.97, 1.0), exp(-pow((age - 1.95) * 6.0, 2.0)) * 0.9 * smoothstep(1.2, 0.0, r));
  // its edges fade out: never the outline of its box
  vec2 edge = gl_FragCoord.xy / u_res * 2.0 - 1.0;
  o *= smoothstep(1.0, 0.72, length(edge));
