// A rare card turned: two comets sweeping round it on crossed orbits — a blue ion tail and a golden dust tail
  // each — while a shower of meteors streaks behind and the card's corners sparkle (u_age: seconds, 2.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(2.0, 1.4, age) * smoothstep(0.0, 0.1, age);
  // the meteors, streaking diagonally behind
  for (int k = 0; k < 10; k++) {
    float fk = float(k);
    float run = fract(age * (0.8 + 0.6 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 head = vec2(0.7 - run * 1.6 + (hash(vec2(fk, 3.0)) - 0.5) * 0.8, 0.6 - run * 1.0 + (hash(vec2(fk, 4.0)) - 0.5) * 0.4);
    vec2 dir = normalize(vec2(-1.6, -1.0));
    vec2 rel = c - head;
    float along = dot(rel, -dir);
    float across = abs(dot(rel, vec2(-dir.y, dir.x)));
    o = over(o, vec3(0.85, 0.92, 1.0), smoothstep(0.002, 0.0, across) * smoothstep(0.12, 0.0, along) * step(0.0, along) * 0.7 * fade);
  }
  // two comets on crossed, tilted orbits
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float tilt = fk * 1.1 - 0.55;
    vec2 q = vec2(c.x * cos(tilt) - c.y * sin(tilt), c.x * sin(tilt) + c.y * cos(tilt));
    vec2 e = q / vec2(0.42, 0.2);
    float r = length(e);
    float a = atan(e.y, e.x);
    float head = (fk * 3.1416) + 1.4 - age * 4.0;
    float behind = mod(a - head, 6.2832);
    float band = smoothstep(0.16, 0.0, abs(r - 1.0));
    o = over(o, vec3(0.45, 0.8, 1.0), smoothstep(2.6, 0.0, behind) * band * 0.95 * fade);
    o = over(o, vec3(1.0, 0.85, 0.5), smoothstep(1.2, 0.0, behind) * smoothstep(0.2, 0.0, abs(r - 1.06)) * 0.4 * fade);
    vec2 hp = vec2(cos(head) * 0.42, sin(head) * 0.2);
    o = over(o, vec3(1.0), exp(-length(q - hp) * 40.0) * fade);
    o = over(o, vec3(0.6, 0.85, 1.0), exp(-length(q - hp) * 18.0) * 0.4 * fade);
  }
  // the card's corners sparkling: four-pointed glints
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec2 corner = vec2(fk < 1.5 ? -0.19 : 0.19, mod(fk, 2.0) < 0.5 ? 0.28 : -0.28);
    vec2 g = c - corner;
    float tw = pow(max(sin(age * 6.0 + fk * 1.7), 0.0), 3.0);
    float glint = exp(-abs(g.x) * 200.0) * exp(-abs(g.y) * 25.0) + exp(-abs(g.y) * 200.0) * exp(-abs(g.x) * 25.0);
    o = over(o, vec3(0.9, 0.97, 1.0), glint * tw * fade);
  }
  // its edges fade out, narrowly: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.08, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.08, min(edgeuv.y, 1.0 - edgeuv.y));
