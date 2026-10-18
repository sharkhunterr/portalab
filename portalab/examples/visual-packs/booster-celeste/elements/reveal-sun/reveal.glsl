// A legendary card turned: a star's birth seen as a cosmic event — a glowing accretion disc wheeling round
  // the card (brighter on the side coming at you), a ring of bent light, a wide anamorphic flare, three planets
  // on their orbits, constellations drawing themselves between the stars, golden dust (u_age: seconds, 3.0 s).
  vec2 c = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
  float age = u_age;
  float fade = smoothstep(3.0, 2.2, age) * smoothstep(0.0, 0.2, age);
  float grow = smoothstep(0.0, 0.8, age);
  // the accretion disc: a tilted ring of hot gas, wheeling
  vec2 dk = vec2(c.x, c.y * 3.4);
  float rr = length(dk);
  float aa = atan(dk.y, dk.x);
  float gas = fbm(vec2(aa * 4.0 - age * 3.0, rr * 10.0));
  float disc = smoothstep(0.2, 0.32, rr) * smoothstep(0.62, 0.38, rr);
  float doppler = 0.55 + 0.45 * cos(aa);
  o = over(o, mix(vec3(1.0, 0.5, 0.15), vec3(1.0, 0.92, 0.7), doppler), disc * (0.35 + 0.65 * gas) * doppler * grow * fade);
  // the ring of bent light round the middle
  o = over(o, vec3(1.0, 0.9, 0.75), smoothstep(0.012, 0.0, abs(length(c * vec2(1.0, 0.82)) - 0.3)) * 0.8 * grow * fade);
  // the core's light and its wide anamorphic flare
  o = over(o, vec3(1.0, 0.95, 0.85), exp(-length(c) * 7.0) * 0.8 * fade);
  o = over(o, vec3(0.7, 0.85, 1.0), exp(-abs(c.y) * 160.0) * exp(-abs(c.x) * 2.2) * 0.9 * fade);
  // rays turning slowly
  float a = atan(c.y, c.x);
  o = over(o, vec3(1.0, 0.85, 0.5), pow(0.5 + 0.5 * sin(a * 12.0 + age * 0.5), 10.0) * smoothstep(0.9, 0.2, length(c)) * 0.35 * fade);
  // three planets on their orbits
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float orbit = 0.48 + fk * 0.12;
    float ang = age * (0.9 - fk * 0.2) + fk * 2.2;
    vec2 pp = vec2(cos(ang) * orbit, sin(ang) * orbit * 0.3);
    float size = 0.018 + 0.008 * fk;
    vec2 pq = c - pp;
    float body = smoothstep(size, size * 0.85, length(pq));
    float lit = clamp(dot(normalize(vec3(pq, sqrt(max(size * size - dot(pq, pq), 0.0)))), normalize(vec3(-pp, 0.2))), 0.0, 1.0);
    vec3 tint = fk < 0.5 ? vec3(0.9, 0.6, 0.4) : fk < 1.5 ? vec3(0.5, 0.75, 1.0) : vec3(0.95, 0.85, 0.6);
    o = over(o, tint * (0.15 + 0.9 * lit), body * grow * fade);
    o = over(o, vec3(1.0, 0.9, 0.8), smoothstep(0.004, 0.0, abs(length(vec2(c.x, c.y / 0.3)) - orbit)) * 0.12 * fade);
  }
  // constellations drawing themselves: stars linked one after the other
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    vec2 p1 = vec2(hash(vec2(fk, 1.0)) - 0.5, hash(vec2(fk, 2.0)) - 0.5) * vec2(1.6, 0.9);
    vec2 p2 = vec2(hash(vec2(fk + 1.0, 1.0)) - 0.5, hash(vec2(fk + 1.0, 2.0)) - 0.5) * vec2(1.6, 0.9);
    float drawn = clamp((age - 0.6 - fk * 0.18) / 0.25, 0.0, 1.0);
    vec2 pa = c - p1;
    vec2 ba = p2 - p1;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, drawn);
    o = over(o, vec3(0.75, 0.85, 1.0), smoothstep(0.0025, 0.0, length(pa - ba * h)) * 0.6 * step(0.001, drawn) * fade);
    o = over(o, vec3(1.0), exp(-length(c - p1) * 130.0) * step(0.6 + fk * 0.18, age) * fade);
  }
  // golden dust drifting down
  for (int k = 0; k < 26; k++) {
    float fk = float(k);
    float x = (hash(vec2(fk, 1.0)) - 0.5) * 1.4;
    float y = 0.6 - fract(age * (0.25 + 0.2 * hash(vec2(fk, 2.0))) + hash(vec2(fk, 3.0))) * 1.3;
    o = over(o, vec3(1.0, 0.85, 0.4), smoothstep(0.004, 0.0, length(c - vec2(x + 0.02 * sin(age * 3.0 + fk), y))) * step(0.5, age) * fade);
  }
  // its edges fade out, narrowly: never the outline of its box
  vec2 edgeuv = gl_FragCoord.xy / u_res;
  o *= smoothstep(0.0, 0.08, min(edgeuv.x, 1.0 - edgeuv.x)) * smoothstep(0.0, 0.08, min(edgeuv.y, 1.0 - edgeuv.y));
