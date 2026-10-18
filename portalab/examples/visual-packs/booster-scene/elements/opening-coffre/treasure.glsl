  // Marée — the cursed chest's opening (u_age: seconds): bubbles breathed out of the seam while it shudders, then
  // at 1.15 s the lid swings — a ghostly flash, a spray of bubbles, shafts of green light fanning up, coins thrown and
  // glittering, a column of bubbles rising.
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  vec2 seam = vec2(0.0, 0.055);
  vec2 dv = c - seam;
  float age = u_age;
  float open = 1.15;
  // before: thin light and small bubbles escaping from the seam, faster as it strains
  float strain = smoothstep(0.0, open, age);
  float leak = exp(-dv.y * dv.y * 1400.0) * smoothstep(0.3, 0.1, abs(dv.x)) * strain;
  o = over(o, vec3(0.5, 1.0, 0.75), leak * (0.5 + 0.3 * sin(age * 40.0)));
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float life = fract(age * (0.9 + 0.6 * hash(vec2(fk, 1.0))) + hash(vec2(fk, 2.0)));
    vec2 b = seam + vec2((hash(vec2(fk, 3.0)) - 0.5) * 0.55, life * 0.32);
    b.x += 0.02 * sin(life * 20.0 + fk);
    float rad = 0.004 + 0.007 * hash(vec2(fk, 4.0));
    float dd = length(c - b);
    float ring = smoothstep(rad, rad * 0.7, dd) * (1.0 - smoothstep(rad * 0.8, rad * 0.35, dd) * 0.7);
    o = over(o, vec3(0.85, 1.0, 1.0), ring * smoothstep(1.0, 0.6, life) * step(age, open + 0.2) * strain);
  }
  if (age > open) {
    float s = age - open;
    // the flash at the seam
    o = over(o, vec3(0.85, 1.0, 0.92), exp(-dot(dv * vec2(1.0, 2.2), dv * vec2(1.0, 2.2)) * 18.0) * smoothstep(0.5, 0.0, s));
    // shafts of green light fanning up from the open chest, slowly turning
    float a = atan(dv.x, max(dv.y, 0.001));
    float up = step(0.0, dv.y);
    float rays = 0.0;
    for (int k = 0; k < 7; k++) {
      float fk = float(k);
      float dir = (fk - 3.0) * 0.21 + 0.05 * sin(age * 0.8 + fk);
      rays += smoothstep(0.07 + 0.03 * hash(vec2(fk, 7.0)), 0.0, abs(a - dir)) * (0.6 + 0.4 * sin(age * 3.0 + fk * 2.0));
    }
    float reach = smoothstep(0.0, 0.5, s);
    o = over(o, vec3(0.45, 1.0, 0.72), clamp(rays, 0.0, 1.0) * up * reach * 0.5 * exp(-length(dv) * 2.4) * smoothstep(0.0, 0.05, dv.y));
    o = over(o, vec3(0.3, 0.95, 0.6), up * exp(-length(dv * vec2(1.4, 1.0)) * 5.0) * 0.45 * reach);
    // coins thrown up, spinning (their width breathing) and falling back
    for (int k = 0; k < 14; k++) {
      float fk = float(k);
      float ang = (hash(vec2(fk, 11.0)) - 0.5) * 1.6;
      float speed = 0.55 + 0.45 * hash(vec2(fk, 12.0));
      float ts = max(s - 0.05 * hash(vec2(fk, 13.0)), 0.0);
      vec2 p = seam + vec2(sin(ang), cos(ang)) * speed * ts - vec2(0.0, 0.55 * ts * ts);
      vec2 q = c - p;
      float spin = abs(sin(age * (7.0 + 5.0 * hash(vec2(fk, 14.0))) + fk));
      q.x /= max(spin, 0.15);
      float coin = smoothstep(0.014, 0.01, length(q));
      vec3 gold = mix(vec3(0.75, 0.5, 0.12), vec3(1.0, 0.88, 0.45), spin);
      float shine = smoothstep(0.006, 0.0, length(q - vec2(-0.004, 0.004))) * spin;
      o = over(o, gold, coin * smoothstep(1.4, 1.0, s) * step(0.001, ts));
      o = over(o, vec3(1.0, 1.0, 0.9), shine * smoothstep(1.4, 1.0, s));
    }
    // the spray of bubbles, then a column of them rising
    for (int k = 0; k < 26; k++) {
      float fk = float(k);
      float speed = 0.25 + 0.5 * hash(vec2(fk, 21.0));
      float life = s * speed + 0.15 * hash(vec2(fk, 22.0));
      vec2 b = seam + vec2((hash(vec2(fk, 23.0)) - 0.5) * (0.12 + 0.6 * life), life * 1.1);
      b.x += 0.03 * sin(life * 12.0 + fk * 1.3);
      float rad = 0.006 + 0.016 * hash(vec2(fk, 24.0));
      float dd = length(c - b);
      float ring = smoothstep(rad, rad * 0.75, dd) * (1.0 - smoothstep(rad * 0.85, rad * 0.4, dd) * 0.75);
      float glint = smoothstep(rad * 0.35, 0.0, length(c - b - vec2(-0.35, 0.35) * rad));
      o = over(o, vec3(0.88, 1.0, 1.0), (ring * 0.8 + glint) * smoothstep(0.7, 0.45, life));
    }
    // glitter: gold dust drifting in the light
    vec2 g = c * 34.0 + vec2(0.0, -age * 2.0);
    float id = hash(floor(g));
    float tw = 0.5 + 0.5 * sin(age * 9.0 + id * 40.0);
    o = over(o, vec3(1.0, 0.9, 0.55), step(0.95, id) * smoothstep(0.25, 0.0, length(fract(g) - 0.5)) * tw * up * exp(-length(dv) * 3.0) * reach);
  }
  // tension: before it gives way, the dark closes in round it and its beats quicken
  vec2 dc = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float dread = smoothstep(0.0, 1.0, u_age) * smoothstep(1.35, 1.0, u_age);
  float quick = pow(0.5 + 0.5 * sin(u_age * u_age * 14.0), 8.0);
  o = over(o, vec3(0.0), smoothstep(0.12, 0.6, length(dc * vec2(0.8, 1.0))) * dread * 0.6);
  o = over(o, vec3(1.0, 0.95, 0.9), exp(-length(dc) * 9.0) * quick * dread * 0.25);
  // its edges fade out: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.2, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.2, min(edgeuv.y, 1.0 - edgeuv.y));
