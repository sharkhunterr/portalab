// Halloween — the haunted pumpkin opening (u_age: seconds, 2.8 s): its glow racing while it giggles, the dive
  // into it (1.4 s to 2.0 s: the light inside swallowing all), then out of the dark a violet flash, ghosts
  // spiralling out and a cloud of bats bursting up.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float pop = 2.0;
  float race = smoothstep(0.0, 1.4, age) * step(age, pop);
  o = over(o, vec3(1.0, 0.55, 0.1), exp(-dot(c, c) * 14.0) * race * (0.4 + 0.3 * sin(age * age * 25.0)));
  // the dive: the light inside swallowing everything, its fibrous walls rushing past
  float into = smoothstep(1.4, 2.0, age) * smoothstep(2.4, 2.0, age);
  float walls = fbm(vec2(atan(c.y, c.x) * 3.0, 1.0 / (length(c) + 0.05) + age * 6.0));
  o = over(o, mix(vec3(1.0, 0.45, 0.05), vec3(1.0, 0.85, 0.5), walls), into * (0.6 + 0.3 * walls));
  if (age > pop) {
    float s = age - pop;
    float fade = smoothstep(1.35, 0.8, s);
    o = over(o, vec3(0.75, 0.45, 1.0), exp(-length(c) * 5.0) * smoothstep(0.45, 0.0, s));
    // ghosts: pale wisps spiralling out
    for (int k = 0; k < 5; k++) {
      float fk = float(k);
      float ang = fk * 1.2566 + s * 2.2;
      float rr = s * 0.42;
      vec2 g = vec2(cos(ang), sin(ang) * 0.7 + 0.25) * rr;
      vec2 q = (c - g) * 18.0;
      float head = smoothstep(1.0, 0.7, length(q - vec2(0.0, 0.4)));
      float sheet = step(abs(q.x), 1.0 - 0.0 * q.y) * step(-1.6, q.y) * step(q.y, 0.4) * smoothstep(-1.6, -1.2, q.y + 0.25 * sin(q.x * 6.0 + s * 10.0));
      float ghost = clamp(head + sheet, 0.0, 1.0);
      float eyes = smoothstep(0.22, 0.12, length(q - vec2(-0.35, 0.45))) + smoothstep(0.22, 0.12, length(q - vec2(0.35, 0.45)));
      o = over(o, vec3(0.9, 0.92, 1.0), ghost * 0.75 * fade);
      o = over(o, vec3(0.05, 0.0, 0.1), eyes * ghost * fade);
    }
    // bats bursting up
    for (int k = 0; k < 14; k++) {
      float fk = float(k);
      float ang = 1.5708 + (hash(vec2(fk, 1.0)) - 0.5) * 2.2;
      vec2 b = vec2(cos(ang), sin(ang)) * s * (0.5 + 0.4 * hash(vec2(fk, 2.0)));
      vec2 q = (c - b) * 70.0;
      float flap = sin(s * 30.0 + fk * 2.0);
      float wing = step(abs(q.x), 2.2) * smoothstep(0.4, 0.0, abs(q.y - abs(q.x) * 0.45 * flap - 0.25 * sin(abs(q.x) * 3.0)));
      float body = smoothstep(0.5, 0.3, length(q * vec2(1.4, 0.9)));
      o = over(o, vec3(0.03, 0.0, 0.05), clamp(wing + body, 0.0, 1.0) * fade);
    }
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.25, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.25, min(edgeuv.y, 1.0 - edgeuv.y));
